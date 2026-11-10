"""Setting EBaC up, setting it up again, unloading and removing it
(__init__.py), and the repair when the EBaC app can't be reached
(reachable.py)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

import yaml
from freezegun.api import FrozenDateTimeFactory

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant.common import async_fire_time_changed

from custom_components.ebac import sentences
from custom_components.ebac.const import (
    CONF_ALLOW_ADD,
    CONF_ALLOW_REMOVE,
    CONF_TRANSLATION,
    DOMAIN,
    INTENT_NEXT,
    INTENT_READ,
    STORAGE_KEY,
)
from custom_components.ebac.reachable import ISSUE_ID

from .conftest import make_entry, say, setup_ebac
from .fake_ebac import FakeEbac


def sentence_file(hass: HomeAssistant) -> Path:
    return Path(hass.config.config_dir) / "custom_sentences" / "en" / "ebac.yaml"


def book_list(hass: HomeAssistant) -> set[str]:
    """The books named in the sentence file."""
    data = yaml.safe_load(sentence_file(hass).read_text(encoding="utf-8"))
    return {value["out"] for value in data["lists"]["ebac_book"]["values"]}


async def test_setup(hass: HomeAssistant, ebac: FakeEbac) -> None:
    entry = await setup_ebac(hass)
    assert entry.state is ConfigEntryState.LOADED
    data = entry.runtime_data
    assert data.translation == "AV"
    assert data.title == "King James Version"
    assert "John" in data.books
    assert data.said == [{"word": "יהוה", "say": "Adonai"}]
    # its intents, and EBaC voice
    assert INTENT_READ in {h.intent_type for h in intent.async_get(hass)}
    assert hass.states.get("tts.ebac_voice") is not None


async def test_sentence_file(hass: HomeAssistant, ebac: FakeEbac) -> None:
    await setup_ebac(hass, **{CONF_TRANSLATION: "WLC"})
    text = sentence_file(hass).read_text(encoding="utf-8")
    assert text.startswith("# Written by the EBaC integration")
    # the books of every translation installed, not only of the Hebrew
    # Bible in use: so "John 3:16" is understood, and answered that it
    # has no John
    assert {"Genesis", "1 Samuel", "Psalms", "John", "Jude", "Revelation"} <= book_list(hass)


async def test_sentence_file_not_rewritten_unchanged(
    hass: HomeAssistant, ebac: FakeEbac
) -> None:
    """Set up again with the same books: the file isn't written again, so
    Assist isn't made to load its sentences again for nothing."""
    entry = await setup_ebac(hass)
    written = sentence_file(hass).stat().st_mtime_ns
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert sentence_file(hass).stat().st_mtime_ns == written


async def test_not_ready_while_unreachable(hass: HomeAssistant, ebac: FakeEbac) -> None:
    """The app not started yet: retried, as Home Assistant retries."""
    ebac.down = True
    entry = make_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY

    ebac.down = False
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


async def test_translation_missing_until_back(
    hass: HomeAssistant, ebac: FakeEbac, freezer: FrozenDateTimeFactory
) -> None:
    """The translation chosen removed in the app (perhaps to be added
    again): EBaC's first is read from meanwhile, the option kept, and the
    regular check reads from it again when it is back. (It once refused to
    start, leaving every sentence unanswered.)"""
    ebac.installed = ["AV"]
    entry = await setup_ebac(hass, **{CONF_TRANSLATION: "WLC"})
    assert entry.state is ConfigEntryState.LOADED
    data = entry.runtime_data
    assert data.translation is None
    assert data.missing == "WLC"
    assert data.title == "King James Version"
    assert entry.options[CONF_TRANSLATION] == "WLC"
    assert "John 3:16" in await say(hass, INTENT_READ, book="John", chapter=3, verse=16)

    ebac.installed = ["AV", "WLC"]
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    data = entry.runtime_data
    assert data.translation == "WLC"
    assert data.missing is None


async def test_permissions_need_the_one_above(hass: HomeAssistant, ebac: FakeEbac) -> None:
    """Options set some other way (by hand, or an older version): adding
    without changing allowed is not allowed, nor removing without adding."""
    entry = await setup_ebac(hass, **{CONF_ALLOW_ADD: True, CONF_ALLOW_REMOVE: True})
    data = entry.runtime_data
    assert not data.allow_change
    assert not data.allow_add
    assert not data.allow_remove


async def test_unknown_source_is_the_default(hass: HomeAssistant, ebac: FakeEbac) -> None:
    entry = await setup_ebac(hass, source="nowhere")
    assert entry.runtime_data.source == "scrollmapper"


async def test_translation_changed(hass: HomeAssistant, ebac: FakeEbac) -> None:
    """Another translation in the options: its title and books, without
    unloading (EBaC voice stays, and the intents have no gap)."""
    entry = await setup_ebac(hass)
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_TRANSLATION: "WLC"}
    )
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.translation == "WLC"
    assert "John" not in entry.runtime_data.books
    assert hass.data[DOMAIN] is entry.runtime_data


async def test_options_changed_while_unreachable(
    hass: HomeAssistant, ebac: FakeEbac
) -> None:
    """EBaC not answering just then: everything set up again, retried."""
    entry = await setup_ebac(hass)
    ebac.down = True
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_TRANSLATION: "WLC"}
    )
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload(hass: HomeAssistant, ebac: FakeEbac) -> None:
    entry = await setup_ebac(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert DOMAIN not in hass.data
    assert INTENT_READ not in {h.intent_type for h in intent.async_get(hass)}
    # (the sentence file stays, for the restart)
    assert sentence_file(hass).exists()


async def test_remove(hass: HomeAssistant, ebac: FakeEbac) -> None:
    entry = await setup_ebac(hass)
    assert sentence_file(hass).exists()
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert not sentence_file(hass).exists()


async def test_places_kept_over_a_restart(
    hass: HomeAssistant, ebac: FakeEbac, hass_storage: dict[str, Any]
) -> None:
    """"Next verse" after a restart goes on from where it was."""
    entry = await setup_ebac(hass)
    await say(hass, INTENT_READ, book="John", chapter=3, verse=16)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass_storage[STORAGE_KEY]["data"]["device_id:kitchen"]["ref"] == "John 3:16"

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert (await say(hass, INTENT_NEXT)).startswith("John chapter 3, verse 17.")


# ---- the repair, when EBaC can't be reached (reachable.py)


def unreachable_issue(hass: HomeAssistant) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, ISSUE_ID)


async def check_now(hass: HomeAssistant, freezer: FrozenDateTimeFactory, minutes: int) -> None:
    """Minutes go by: the regular check of whether EBaC answers."""
    for _ in range(minutes // 5):
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()


async def test_repair_after_a_while_unreachable(
    hass: HomeAssistant, ebac: FakeEbac, freezer: FrozenDateTimeFactory
) -> None:
    await setup_ebac(hass)
    ebac.down = True
    # not at once (a restart of the app)
    await check_now(hass, freezer, 10)
    assert unreachable_issue(hass) is None
    # after 15 minutes
    await check_now(hass, freezer, 10)
    issue = unreachable_issue(hass)
    assert issue is not None
    assert issue.translation_placeholders == {"url": "http://ebac.test:8080/cgi-bin/ebac"}

    # answering again: gone
    ebac.down = False
    await check_now(hass, freezer, 5)
    assert unreachable_issue(hass) is None


async def test_repair_told_once(
    hass: HomeAssistant, ebac: FakeEbac, freezer: FrozenDateTimeFactory
) -> None:
    """Submitted (cleared) while EBaC still doesn't answer: not raised again
    until EBaC has answered and then stopped again."""
    await setup_ebac(hass)
    ebac.down = True
    await check_now(hass, freezer, 20)
    assert unreachable_issue(hass) is not None
    ir.async_delete_issue(hass, DOMAIN, ISSUE_ID)  # (as Submit does)
    await check_now(hass, freezer, 60)
    assert unreachable_issue(hass) is None

    ebac.down = False
    await check_now(hass, freezer, 5)
    ebac.down = True
    await check_now(hass, freezer, 20)
    assert unreachable_issue(hass) is not None


async def test_repair_while_setup_retries(
    hass: HomeAssistant, ebac: FakeEbac, freezer: FrozenDateTimeFactory
) -> None:
    """The app removed before a restart: the setup's retries raise it."""
    ebac.down = True
    entry = make_entry()
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert unreachable_issue(hass) is None
    freezer.tick(timedelta(minutes=16))
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert unreachable_issue(hass) is not None


async def test_repair_can_be_submitted(
    hass: HomeAssistant, ebac: FakeEbac, freezer: FrozenDateTimeFactory, hass_client
) -> None:
    """It is fixable with nothing to fix: Submit clears it (Home Assistant's
    plain confirm, as the integration has no repairs platform)."""
    from homeassistant.setup import async_setup_component
    from pytest_homeassistant.components.repairs import (
        process_repair_fix_flow,
        start_repair_fix_flow,
    )

    assert await async_setup_component(hass, "repairs", {})
    await setup_ebac(hass)
    ebac.down = True
    await check_now(hass, freezer, 20)
    client = await hass_client()
    flow = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
    result = await process_repair_fix_flow(client, flow["flow_id"], json={})
    assert result["type"] == "create_entry"
    assert unreachable_issue(hass) is None


async def test_repair_removed_with_integration(
    hass: HomeAssistant, ebac: FakeEbac, freezer: FrozenDateTimeFactory
) -> None:
    entry = await setup_ebac(hass)
    ebac.down = True
    await check_now(hass, freezer, 20)
    assert unreachable_issue(hass) is not None
    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()
    assert unreachable_issue(hass) is None


async def test_old_unfixable_add_repairs_cleared(hass: HomeAssistant, ebac: FakeEbac) -> None:
    """0.5.0's first builds made add repairs that could only be ignored."""
    ir.async_create_issue(
        hass, DOMAIN, "add_failed_litv", is_fixable=False,
        severity=ir.IssueSeverity.ERROR, translation_key="add_failed",
    )
    await setup_ebac(hass)
    assert ir.async_get(hass).async_get_issue(DOMAIN, "add_failed_litv") is None


def test_sentence_file_helpers(tmp_path: Path) -> None:
    data = sentences.build(
        [{"full_name": "John", "spoken": ["John"]}],
        [{"number": 3, "spoken": ["3", "three"]}],
    )
    assert sentences.write(str(tmp_path), data) is True
    assert sentences.write(str(tmp_path), data) is False  # (unchanged)
    assert sentences.remove(str(tmp_path)) is True
    assert sentences.remove(str(tmp_path)) is False  # (already gone)



async def test_translation_gone_while_reading(
    hass: HomeAssistant, ebac: FakeEbac, freezer: FrozenDateTimeFactory
) -> None:
    """The translation read from removed in the app after reading was set up
    (perhaps to be added again): asked for a verse, voice says so and reads
    from EBaC's first; the option is kept, and it is read from again when
    back. (It answered "There is no translation NLT-TB." until the app was
    set up again.)"""
    entry = await setup_ebac(hass, **{CONF_TRANSLATION: "WLC"})
    assert entry.runtime_data.translation == "WLC"
    ebac.installed = ["AV", "KJVA-SM"]
    speech = await say(hass, INTENT_READ, book="Genesis", chapter=1, verse=1)
    assert speech.startswith("WLC isn't in EBaC just now, so this is from King James Version. ")
    assert "Genesis 1:1" in speech
    data = entry.runtime_data
    assert (data.translation, data.missing) == (None, "WLC")
    assert entry.options[CONF_TRANSLATION] == "WLC"

    ebac.installed = ["AV", "WLC", "KJVA-SM"]
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert entry.runtime_data.translation == "WLC"


async def test_translation_gone_found_by_the_check(
    hass: HomeAssistant, ebac: FakeEbac, freezer: FrozenDateTimeFactory
) -> None:
    """Gone, with no one asking: the regular check sets reading up again
    from EBaC's first."""
    entry = await setup_ebac(hass, **{CONF_TRANSLATION: "WLC"})
    ebac.installed = ["AV"]
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    data = entry.runtime_data
    assert (data.translation, data.missing) == (None, "WLC")
