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
    from the verse it last heard.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from . import intents as ebac_intents
from . import sentences
from .api import EbacApi, EbacError
from .const import (
    CONF_ALLOW_ADD,
    CONF_ALLOW_CHANGE,
    CONF_ALLOW_REMOVE,
    CONF_LANGUAGE,
    CONF_READ_ON,
    CONF_TRANSLATION,
    CONF_URL,
    DEFAULT_LANGUAGE,
    DEFAULT_READ_ON,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
)

_LOGGER = logging.getLogger(__name__)


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
    # questions waiting for a yes, by place key: {"action": "add" or
    # "remove", "name", "title", "until": time}
    pending: dict[str, dict] = field(default_factory=dict)
    # ebac-admin's catalog, kept a few minutes: (time, catalog)
    catalog: tuple[float, dict] | None = None


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
    """Set up EBaC: the sentences, the intents."""
    api = EbacApi(async_get_clientsession(hass), entry.data[CONF_URL])
    translation = entry.options.get(CONF_TRANSLATION) or None
    try:
        books = await api.books(translation)
        numbers = await api.numbers(translation)
        translations = await api.translations()
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
        raise ConfigEntryNotReady(str(err)) from err
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

    entry.async_on_unload(entry.add_update_listener(_options_changed))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EbacConfigEntry) -> bool:
    """Unload EBaC: its intents (its sentence file stays, for the restart)."""
    ebac_intents.async_remove(hass)
    await entry.runtime_data.places.async_save()
    hass.data.pop(DOMAIN, None)
    return True


async def async_remove_entry(hass: HomeAssistant, entry: EbacConfigEntry) -> None:
    """EBaC removed: its sentence file too."""
    if await hass.async_add_executor_job(sentences.remove, hass.config.config_dir):
        await _reload_assist(hass)


async def _options_changed(hass: HomeAssistant, entry: EbacConfigEntry) -> None:
    """Another translation, or how much "read on" reads: set up again (the
    books' names may differ)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _reload_assist(hass: HomeAssistant) -> None:
    """Have Assist read its sentence files again."""
    try:
        await hass.services.async_call("conversation", "reload", {}, blocking=True)
    except Exception:  # noqa: BLE001 (Assist goes on with the old ones)
        _LOGGER.warning(
            "Couldn't reload Assist's sentences; EBaC's will be used after a restart"
        )
