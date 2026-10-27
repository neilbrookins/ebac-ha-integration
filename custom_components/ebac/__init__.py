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
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from . import intents as ebac_intents
from . import sentences
from .api import EbacApi, EbacError
from .const import (
    CONF_READ_ON,
    CONF_TRANSLATION,
    CONF_URL,
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


type EbacConfigEntry = ConfigEntry[EbacData]


async def async_setup_entry(hass: HomeAssistant, entry: EbacConfigEntry) -> bool:
    """Set up EBaC: the sentences, the intents."""
    api = EbacApi(async_get_clientsession(hass), entry.data[CONF_URL])
    translation = entry.options.get(CONF_TRANSLATION) or None
    try:
        books = await api.books(translation)
        numbers = await api.numbers(translation)
    except EbacError as err:
        raise ConfigEntryNotReady(str(err)) from err

    places = Places(hass)
    await places.async_load()
    entry.runtime_data = EbacData(
        api=api,
        translation=translation,
        read_on=int(entry.options.get(CONF_READ_ON, DEFAULT_READ_ON)),
        places=places,
    )
    hass.data[DOMAIN] = entry.runtime_data

    changed = await hass.async_add_executor_job(
        sentences.write, hass.config.config_dir, sentences.build(books, numbers)
    )
    ebac_intents.async_register(hass)
    if changed:
        await _reload_assist(hass)

    entry.async_on_unload(entry.add_update_listener(_options_changed))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EbacConfigEntry) -> bool:
    """Unload EBaC: its intents (its sentence file stays, for the restart)."""
    ebac_intents.async_remove(hass)
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
