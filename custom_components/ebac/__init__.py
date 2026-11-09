"""EBaC (Electronic Bible and Concordance): Bible verses read aloud by Assist.

"Genesis one colon one", then "next verse". EBaC itself runs elsewhere:
in the EBaC app (ebac-ha-app), or any web server running ebac-api, which
this integration asks for each verse (see api.py).

At setup the integration
  - asks ebac-api for the translation's books and numbers, and writes the
    sentences Assist matches from them (sentences.py), then has Assist
    load them again;
  - registers the intents those sentences name (intents.py), whose
    handlers keep each voice device's place, so "next verse" goes on
    from the verse it last heard;
  - asks for the words to say another way aloud, and sets up EBaC voice
    (tts.py), which says them so on the way to another voice.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from . import intents as ebac_intents
from . import reachable, sentences
from .api import EbacApi, EbacError, EbacUnreachable
from .const import (
    CONF_ALLOW_ADD,
    CONF_ALLOW_CHANGE,
    CONF_ALLOW_REMOVE,
    CONF_LANGUAGE,
    CONF_READ_ON,
    CONF_SOURCE,
    CONF_TRANSLATION,
    CONF_URL,
    DEFAULT_LANGUAGE,
    DEFAULT_READ_ON,
    DEFAULT_SOURCE,
    DOMAIN,
    SOURCES,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.TTS]


@dataclass
class EbacData:
    """What the intent handlers need: ebac-api, the options, the places."""

    api: EbacApi
    translation: str | None
    read_on: int
    places: Places
    # the full names of the books of the translation in use ("1 Samuel"),
    # and its title: to say which book it lacks ("The Westminster
    # Leningrad Codex has no John")
    books: set[str] = field(default_factory=set)
    title: str = ""
    # its books in order, with their chapters (/books): for "next chapter"
    book_list: list[dict[str, Any]] = field(default_factory=list)
    # what Assist may do beyond reading (the checkboxes), and the language
    # group "add translation" looks in
    allow_change: bool = False
    allow_add: bool = False
    allow_remove: bool = False
    language: str = DEFAULT_LANGUAGE
    # and the source it looks in (one of SOURCES)
    source: str = DEFAULT_SOURCE
    # questions waiting for a yes, by place key: {"action": "add" or
    # "remove", "name", "title", "source" (adding), "until": time}
    pending: dict[str, dict] = field(default_factory=dict)
    # ebac-admin's catalogs, kept a few minutes: {source: (time, catalog)}
    catalog: dict[str, tuple[float, dict]] = field(default_factory=dict)
    # words to say another way aloud, for EBaC voice (tts.py): [{"word":
    # "יהוה", "say": "Adonai"}], asked for again with the regular check
    said: list[dict[str, str]] = field(default_factory=list)


class Places:
    """Each voice device's place: the verses it last heard, and in which
    translation. Kept in Home Assistant's storage, so that "next verse"
    still works after a restart."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._places: dict[str, dict] = {}

    async def async_load(self) -> None:
        """Read the places kept."""
        self._places = (await self._store.async_load()) or {}

    def get(self, key: str) -> dict | None:
        """The place of a device (or conversation, or user)."""
        return self._places.get(key)

    def set(self, key: str, place: dict) -> None:
        """Keep a device's place (written a little later, together)."""
        self._places[key] = place
        self._store.async_delay_save(lambda: self._places, 5)

    async def async_save(self) -> None:
        """Write the places now (before EBaC is set up again, as when the
        translation changes, so that the place just read isn't lost)."""
        await self._store.async_save(self._places)


type EbacConfigEntry = ConfigEntry[EbacData]


async def async_setup_entry(hass: HomeAssistant, entry: EbacConfigEntry) -> bool:
    """Set up EBaC: the sentences, the intents, EBaC voice."""
    try:
        await _async_set_up_reading(hass, entry)
    except EbacError as err:
        raise ConfigEntryNotReady(str(err)) from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_options_changed))

    async def check(_now: Any) -> None:
        """Does EBaC still answer? (removed, the repair: reachable.py)"""
        data = entry.runtime_data
        try:
            await data.api.translations()
            data.said = await data.api.said()
        except EbacUnreachable:
            await reachable.async_unanswered(hass, entry.data[CONF_URL])
        except EbacError:
            pass  # (it answered: wrongly, but it's there)
        else:
            await reachable.async_answered(hass)

    entry.async_on_unload(async_track_time_interval(hass, check, reachable.CHECK_EVERY))
    return True


async def _async_set_up_reading(hass: HomeAssistant, entry: EbacConfigEntry) -> None:
    """What reading needs, from the options and EBaC's answers: the books,
    the sentences, the intents, the words said another way. Done again
    when the options change (another translation), without EBaC voice
    going away: it may be speaking the answer to that very change."""
    api = EbacApi(async_get_clientsession(hass), entry.data[CONF_URL])
    translation = entry.options.get(CONF_TRANSLATION) or None
    try:
        translations = await api.translations()
        if translation and translation not in {t["name"] for t in translations}:
            # Removed since it was chosen (in EBaC, or by voice): EBaC's
            # first is used, as when none is chosen, and the option is
            # cleared to say so. Refusing to start instead would leave
            # every sentence unanswered, even "use translation …", the
            # one that would set it right (November 9, 2026: CNVS-TB).
            _LOGGER.warning(
                "The translation %s is no longer in EBaC: using its first", translation
            )
            translation = None
            options = dict(entry.options)
            options.pop(CONF_TRANSLATION, None)
            hass.config_entries.async_update_entry(entry, options=options)
        books = await api.books(translation)
        numbers = await api.numbers(translation)
        said = await api.said()
        # The sentences know the books of every translation installed, not
        # only of the one in use: so "John 3:16" said while reading the
        # Hebrew Bible (no New Testament) is understood, and answered that
        # it has no John, rather than not understood at all.
        all_books = list(books)
        known = {book["full_name"] for book in books}
        for other in translations:
            if other["name"] == (translation or translations[0]["name"]):
                continue
            for book in await api.books(other["name"]):
                if book["full_name"] not in known:
                    known.add(book["full_name"])
                    all_books.append(book)
    except EbacError as err:
        if isinstance(err, EbacUnreachable):
            # (removed? after a while, a repair says so: reachable.py)
            await reachable.async_unanswered(hass, entry.data[CONF_URL])
        raise
    await reachable.async_answered(hass)
    in_use = translation or (translations[0]["name"] if translations else "")
    title = next((t["title"] for t in translations if t["name"] == in_use), in_use)

    places = Places(hass)
    await places.async_load()
    options = entry.options
    allow_change = bool(options.get(CONF_ALLOW_CHANGE, False))
    allow_add = allow_change and bool(options.get(CONF_ALLOW_ADD, False))
    entry.runtime_data = EbacData(
        api=api,
        translation=translation,
        read_on=int(options.get(CONF_READ_ON, DEFAULT_READ_ON)),
        places=places,
        books={book["full_name"] for book in books},
        title=title,
        book_list=books,
        allow_change=allow_change,
        allow_add=allow_add,
        allow_remove=allow_add and bool(options.get(CONF_ALLOW_REMOVE, False)),
        language=options.get(CONF_LANGUAGE) or DEFAULT_LANGUAGE,
        source=options.get(CONF_SOURCE) if options.get(CONF_SOURCE) in SOURCES else DEFAULT_SOURCE,
        said=said,
    )
    hass.data[DOMAIN] = entry.runtime_data

    # Repairs from 0.5.0's first builds, which could only be ignored, not
    # cleared: a failed add leaves nothing behind (see adding.py)
    issues = ir.async_get(hass)
    for (domain, issue_id), issue in list(issues.issues.items()):
        if domain == DOMAIN and issue_id.startswith("add_failed_") and not issue.is_fixable:
            ir.async_delete_issue(hass, DOMAIN, issue_id)

    changed = await hass.async_add_executor_job(
        sentences.write, hass.config.config_dir, sentences.build(all_books, numbers)
    )
    ebac_intents.async_register(hass)
    if changed:
        await _reload_assist(hass)


async def async_unload_entry(hass: HomeAssistant, entry: EbacConfigEntry) -> bool:
    """Unload EBaC: its voice and intents (its sentence file stays, for the
    restart)."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    ebac_intents.async_remove(hass)
    await entry.runtime_data.places.async_save()
    hass.data.pop(DOMAIN, None)
    return True


async def async_remove_entry(hass: HomeAssistant, entry: EbacConfigEntry) -> None:
    """EBaC removed: its sentence file too, and any repair saying it can't
    be reached."""
    await reachable.async_forget(hass)
    if await hass.async_add_executor_job(sentences.remove, hass.config.config_dir):
        await _reload_assist(hass)


async def _options_changed(hass: HomeAssistant, entry: EbacConfigEntry) -> None:
    """Another translation, how much "read on" reads, or the voice EBaC
    voice speaks with: reading set up again (the books' names may differ).
    EBaC voice stays: it reads its voice from the options each time, and
    an answer ("Now reading from ...") may be on its way through it. If
    EBaC can't answer just now, everything is set up again, and retried
    as at a start."""
    # (the intents stay registered, and are registered again: no moment
    # without them)
    await entry.runtime_data.places.async_save()
    try:
        await _async_set_up_reading(hass, entry)
    except EbacError:
        await hass.config_entries.async_reload(entry.entry_id)


async def _reload_assist(hass: HomeAssistant) -> None:
    """Have Assist read its sentence files again."""
    try:
        await hass.services.async_call("conversation", "reload", {}, blocking=True)
    except Exception:  # noqa: BLE001 (Assist goes on with the old ones)
        _LOGGER.warning(
            "Couldn't reload Assist's sentences; EBaC's will be used after a restart"
        )
