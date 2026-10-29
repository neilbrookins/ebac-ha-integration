"""Adding a translation by voice, after "Do you agree?" and yes.

Adding takes longer than Assist waits for an answer (the download, then
the concordance index), so ebac-admin does it in the background and the
integration asks how it is going every few seconds. When it is done:

  - the translation becomes the integration's (its option: EBaC is set
    up again with it), not the app's default;
  - whoever asked is told: announced on the voice speaker it was asked on
    (an Assist satellite), or a notification to the phone (the Home
    Assistant app) of the user who asked;
  - if it failed: a repair in Home Assistant (Settings > Repairs), saying
    which translation, why, and who asked; removed when it is next added.

See "Adding by voice" in EBaC's readme.architecture.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import intent
from homeassistant.helpers import issue_registry as ir
from homeassistant.util import slugify

from .api import EbacError
from .const import (
    ADD_MAX_SECONDS,
    ADD_POLL_SECONDS,
    CONF_TRANSLATION,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class Asker:
    """Who asked, to tell them when it's done."""

    satellite_id: str | None  # an Assist satellite's entity
    device_id: str | None
    user_id: str | None
    name: str  # for the license file: "Kitchen", "Neil"


async def asker(intent_obj: intent.Intent) -> Asker:
    """Who said it: the voice device and its name, or the user."""
    hass = intent_obj.hass
    satellite_id = getattr(intent_obj, "satellite_id", None)
    device_id = getattr(intent_obj, "device_id", None)
    user_id = intent_obj.context.user_id if intent_obj.context else None
    name = ""
    if device_id and (device := dr.async_get(hass).async_get(device_id)):
        name = device.name_by_user or device.name or ""
    if not name and satellite_id and (state := hass.states.get(satellite_id)):
        name = state.name
    if not name and user_id:
        # (the user's name: asked in the Home Assistant app)
        if user := await hass.auth.async_get_user(user_id):
            name = user.name or ""
    return Asker(satellite_id, device_id, user_id, name or "Assist")


def agreed_text(who: Asker) -> str:
    """How the license was agreed to, for its license file (ASCII)."""
    text = f"by voice, from {who.name}"
    return text.encode("ascii", "replace").decode().replace("?", "_")


def issue_id(name: str) -> str:
    return f"add_failed_{name.lower()}"


async def tell(hass: HomeAssistant, who: Asker, message: str) -> None:
    """Tell whoever asked: an announcement on the speaker, or a
    notification to the user's phones."""
    satellite = who.satellite_id
    if not satellite and who.device_id:
        # (a satellite's device: its assist_satellite entity)
        for entry in er.async_entries_for_device(er.async_get(hass), who.device_id):
            if entry.domain == "assist_satellite":
                satellite = entry.entity_id
                break
    try:
        if satellite:
            await hass.services.async_call(
                "assist_satellite",
                "announce",
                {"message": message},
                target={"entity_id": satellite},
                blocking=True,
            )
            return
        # Phones: the Home Assistant app on the device asked from, or every
        # phone of the user who asked
        for entry in hass.config_entries.async_entries("mobile_app"):
            data = entry.data
            this_device = who.device_id and any(
                device.id == who.device_id
                for device in dr.async_entries_for_config_entry(
                    dr.async_get(hass), entry.entry_id
                )
            )
            if not (this_device or (who.user_id and data.get("user_id") == who.user_id)):
                continue
            service = f"mobile_app_{slugify(data.get('device_name', ''))}"
            if hass.services.has_service("notify", service):
                await hass.services.async_call(
                    "notify",
                    service,
                    {"title": "EBaC", "message": message},
                    blocking=True,
                )
    except Exception:  # noqa: BLE001 (telling is a courtesy; the repair stays)
        _LOGGER.warning("Couldn't tell %s: %s", who.name, message, exc_info=True)


async def watch_add(hass: HomeAssistant, name: str, title: str, who: Asker) -> None:
    """Wait for an add to end; then make it the integration's translation,
    and tell whoever asked (or make a repair, if it failed)."""
    started = time.monotonic()
    state = "running"
    message = ""
    while time.monotonic() - started < ADD_MAX_SECONDS:
        await asyncio.sleep(ADD_POLL_SECONDS)
        data = hass.data.get(DOMAIN)
        if data is None:
            continue  # (being set up again: ask next time)
        try:
            status = await data.api.status(name)
        except EbacError as err:
            _LOGGER.warning("Asking how adding %s goes: %s", name, err)
            continue
        state = status.get("state", "")
        message = status.get("message", "")
        if state != "running":
            break
    spoken = f"{title} ({name})"
    if state == "done":
        ir.async_delete_issue(hass, DOMAIN, issue_id(name))
        entries = hass.config_entries.async_entries(DOMAIN)
        if entries:
            entry = entries[0]
            # (EBaC is then set up again, with its books)
            hass.config_entries.async_update_entry(
                entry, options={**entry.options, CONF_TRANSLATION: name}
            )
        await tell(hass, who, f"{spoken} is added. Now reading from it.")
        return
    if state == "running":
        message = "it was still going after an hour"
    elif not message:
        message = "it stopped without saying why"
    _LOGGER.warning("Adding %s by voice (from %s) failed: %s", name, who.name, message)
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id(name),
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="add_failed",
        translation_placeholders={"translation": spoken, "why": message, "who": who.name},
    )
    await tell(hass, who, f"Adding {spoken} failed: {message}")
