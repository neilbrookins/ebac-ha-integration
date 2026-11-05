"""Telling when the EBaC app can't be reached for a while: a repair.

Uninstalling the EBaC app leaves this integration behind, retrying (at
setup) or answering "EBaC can't be reached" (by voice). So when EBaC hasn't
answered for UNREACHABLE_AFTER, a repair in Home Assistant (Settings >
Repairs) says so: the app may have been removed; reinstall it (restoring a
backup that includes it brings its translations back), or remove this
integration.

  - Asked at each setup try (Home Assistant retries a setup that wasn't
    ready), and every CHECK_EVERY once set up.
  - Removed as soon as EBaC answers again.
  - Told once a time: Submit clears it, and it isn't raised again until
    EBaC has answered and then stopped again. When it stopped, and whether
    it was told, are kept in Home Assistant's storage, so a restart doesn't
    start the wait again or tell it twice.

See "Removing EBaC" in the EBaC app's documentation.
"""

from __future__ import annotations

import time
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store

from .const import DOMAIN

UNREACHABLE_AFTER = 15 * 60  # seconds
CHECK_EVERY = timedelta(minutes=5)
ISSUE_ID = "app_unreachable"
_STORE_KEY = "ebac.unreachable"
_DATA_KEY = f"{DOMAIN}_unreachable"


async def _store(hass: HomeAssistant) -> tuple[Store[dict], dict]:
    """The store, and what it holds: {"since": time, "told": bool}, or {}
    while EBaC answers (loaded once)."""
    if _DATA_KEY not in hass.data:
        store: Store[dict] = Store(hass, 1, _STORE_KEY)
        hass.data[_DATA_KEY] = (store, (await store.async_load()) or {})
    return hass.data[_DATA_KEY]


async def async_answered(hass: HomeAssistant) -> None:
    """EBaC answered: no repair (until it stops again)."""
    store, state = await _store(hass)
    if state:
        state.clear()
        await store.async_save(state)
    ir.async_delete_issue(hass, DOMAIN, ISSUE_ID)


async def async_forget(hass: HomeAssistant) -> None:
    """The integration removed: nothing kept, no repair."""
    store, _ = await _store(hass)
    await store.async_remove()
    hass.data.pop(_DATA_KEY, None)
    ir.async_delete_issue(hass, DOMAIN, ISSUE_ID)


async def async_unanswered(hass: HomeAssistant, url: str) -> None:
    """EBaC didn't answer: after UNREACHABLE_AFTER of that, the repair."""
    store, state = await _store(hass)
    now = time.time()
    if "since" not in state:
        state["since"] = now
        state["told"] = False
        await store.async_save(state)
        return
    if state.get("told") or now - state["since"] < UNREACHABLE_AFTER:
        return
    state["told"] = True
    await store.async_save(state)
    ir.async_create_issue(
        hass,
        DOMAIN,
        ISSUE_ID,
        # (fixable, with nothing to fix but to acknowledge it: Submit
        # clears it; the steps to take are in its text)
        is_fixable=True,
        # (kept over a restart, as "told" is; removed with the integration)
        is_persistent=True,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_ID,
        translation_placeholders={"url": url},
    )
