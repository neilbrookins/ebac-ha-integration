"""Adding a translation by voice, after the yes (adding.py): who asked,
waiting for ebac-admin to finish, then reading from it and telling them,
or a repair if it failed."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant.common import MockConfigEntry, async_mock_service

from custom_components.ebac import adding
from custom_components.ebac.const import CONF_TRANSLATION, DOMAIN

from .conftest import ALLOW_ALL, setup_ebac
from .fake_ebac import FakeEbac

SATELLITE = "assist_satellite.kitchen"


@pytest.fixture(autouse=True)
def no_waiting():
    """Asked how it goes at once, not every 10 seconds."""
    with patch.object(adding, "ADD_POLL_SECONDS", 0):
        yield


@pytest.fixture
def announce(hass: HomeAssistant):
    return async_mock_service(hass, "assist_satellite", "announce")


def kitchen() -> adding.Asker:
    return adding.Asker(SATELLITE, None, None, "Kitchen")


def target(call) -> list[str]:
    """The entities a service call was for."""
    entity_id = call.data["entity_id"]
    return [entity_id] if isinstance(entity_id, str) else list(entity_id)


async def test_added(hass: HomeAssistant, ebac: FakeEbac, announce) -> None:
    entry = await setup_ebac(hass, **ALLOW_ALL)
    ir.async_create_issue(  # (an earlier try that failed)
        hass, DOMAIN, "add_failed_litv", is_fixable=True,
        severity=ir.IssueSeverity.ERROR, translation_key="add_failed",
    )
    ebac.adds["LITV-SM"] = {"state": "done", "message": ""}

    await adding.watch_add(hass, "LITV-SM", "Literal Translation of the Holy Bible", kitchen())
    await hass.async_block_till_done()

    # read from now on, by everyone
    assert entry.options[CONF_TRANSLATION] == "LITV-SM"
    assert entry.runtime_data.translation == "LITV-SM"
    # the one who asked is told, on the speaker asked on
    assert len(announce) == 1
    assert target(announce[0]) == [SATELLITE]
    assert announce[0].data["message"] == (
        "Literal Translation of the Holy Bible (LITV-SM) is added. Now reading from it."
    )
    assert ir.async_get(hass).async_get_issue(DOMAIN, "add_failed_litv") is None


async def test_added_ebook(hass: HomeAssistant, ebac: FakeEbac, announce) -> None:
    """A Project Gutenberg ebook: asked for by number, read from by name."""
    entry = await setup_ebac(hass, **ALLOW_ALL)
    ebac.adds["8294"] = {"state": "done", "message": ""}
    await adding.watch_add(
        hass, "8294", "World English Bible", kitchen(), "gutenberg", "WEB-PG"
    )
    await hass.async_block_till_done()
    assert entry.options[CONF_TRANSLATION] == "WEB-PG"
    assert entry.runtime_data.title == "World English Bible"
    assert announce[0].data["message"] == (
        "World English Bible (WEB-PG) is added. Now reading from it."
    )


async def test_failed(hass: HomeAssistant, ebac: FakeEbac, announce) -> None:
    entry = await setup_ebac(hass, **ALLOW_ALL)
    ebac.adds["LITV-SM"] = {"state": "failed", "message": "the download was cut off"}
    await adding.watch_add(hass, "LITV-SM", "Literal Translation of the Holy Bible", kitchen())
    await hass.async_block_till_done()

    assert entry.options[CONF_TRANSLATION] == "AV"
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "add_failed_litv")
    assert issue is not None
    assert issue.is_fixable  # (Submit clears it: a failed add leaves nothing)
    assert issue.translation_placeholders == {
        "translation": "Literal Translation of the Holy Bible (LITV-SM)",
        "why": "the download was cut off",
        "who": "Kitchen",
    }
    assert announce[0].data["message"] == (
        "Adding Literal Translation of the Holy Bible (LITV-SM) failed: the download was cut off"
    )


async def test_failed_without_a_reason(hass: HomeAssistant, ebac: FakeEbac, announce) -> None:
    await setup_ebac(hass, **ALLOW_ALL)
    ebac.adds["LITV-SM"] = {"state": "failed", "message": ""}
    await adding.watch_add(hass, "LITV-SM", "Literal", kitchen())
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "add_failed_litv")
    assert issue.translation_placeholders["why"] == "it stopped without saying why"


async def test_still_going_after_an_hour(hass: HomeAssistant, ebac: FakeEbac, announce) -> None:
    await setup_ebac(hass, **ALLOW_ALL)
    ebac.adds["LITV-SM"] = {"state": "running", "message": ""}
    with patch.object(adding, "ADD_MAX_SECONDS", 0):
        await adding.watch_add(hass, "LITV-SM", "Literal", kitchen())
    issue = ir.async_get(hass).async_get_issue(DOMAIN, "add_failed_litv")
    assert issue.translation_placeholders["why"] == "it was still going after an hour"


async def test_status_unanswered_is_asked_again(
    hass: HomeAssistant, ebac: FakeEbac, announce
) -> None:
    """EBaC not answering for a moment while it adds: asked again."""
    await setup_ebac(hass, **ALLOW_ALL)
    ebac.adds["LITV-SM"] = {"state": "running", "message": ""}
    answers = iter([True, False])

    real = ebac.admin_status

    def status(params):
        if next(answers, False):
            ebac.adds["LITV-SM"] = {"state": "done", "message": ""}
            from .fake_ebac import Answer

            raise Answer("busy", 503)
        return real(params)

    ebac.admin_status = status
    await adding.watch_add(hass, "LITV-SM", "Literal", kitchen())
    await hass.async_block_till_done()
    assert announce[0].data["message"] == "Literal (LITV-SM) is added. Now reading from it."


async def test_told_on_the_users_phone(hass: HomeAssistant, ebac: FakeEbac) -> None:
    """Asked in the Home Assistant app: a notification to that user's phones
    (not to anyone else's)."""
    await setup_ebac(hass, **ALLOW_ALL)
    neil = await hass.auth.async_create_user("Neil")
    other = await hass.auth.async_create_user("Guest")
    for user, phone in ((neil, "Neil's Pixel"), (other, "Guest phone")):
        MockConfigEntry(
            domain="mobile_app", data={"user_id": user.id, "device_name": phone}
        ).add_to_hass(hass)
    pixel = async_mock_service(hass, "notify", "mobile_app_neil_s_pixel")
    guest = async_mock_service(hass, "notify", "mobile_app_guest_phone")

    await adding.tell(hass, adding.Asker(None, None, neil.id, "Neil"), "Done.")
    assert [c.data for c in pixel] == [{"title": "EBaC", "message": "Done."}]
    assert not guest


async def test_telling_fails_quietly(hass: HomeAssistant, ebac: FakeEbac) -> None:
    """The speaker gone: telling is a courtesy; nothing breaks."""
    await adding.tell(hass, kitchen(), "Done.")  # (no announce service at all)


async def test_satellite_of_the_device(hass: HomeAssistant, announce) -> None:
    """Only the device known: its Assist satellite is told."""
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("test", "kitchen")}, name="Kitchen"
    )
    satellite = er.async_get(hass).async_get_or_create(
        "assist_satellite", "test", "kitchen", device_id=device.id
    )
    await adding.tell(hass, adding.Asker(None, device.id, None, "Kitchen"), "Done.")
    assert target(announce[0]) == [satellite.entity_id]


# ---- who asked


async def test_asker_device(hass: HomeAssistant) -> None:
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    registry = dr.async_get(hass)
    device = registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={("test", "k")}, name="Speaker 1"
    )
    asked = SimpleNamespace(hass=hass, satellite_id=None, device_id=device.id, context=Context())
    assert (await adding.asker(asked)).name == "Speaker 1"
    # its name as the user named it, if they did
    registry.async_update_device(device.id, name_by_user="Kitchen")
    assert (await adding.asker(asked)).name == "Kitchen"


async def test_asker_satellite_and_user(hass: HomeAssistant) -> None:
    hass.states.async_set(SATELLITE, "idle", {"friendly_name": "Kitchen satellite"})
    asked = SimpleNamespace(hass=hass, satellite_id=SATELLITE, device_id=None, context=Context())
    assert (await adding.asker(asked)).name == "Kitchen satellite"

    neil = await hass.auth.async_create_user("Neil")
    asked = SimpleNamespace(
        hass=hass, satellite_id=None, device_id=None, context=Context(user_id=neil.id)
    )
    who = await adding.asker(asked)
    assert (who.name, who.user_id) == ("Neil", neil.id)

    asked = SimpleNamespace(hass=hass, satellite_id=None, device_id=None, context=Context())
    assert (await adding.asker(asked)).name == "Assist"


def test_agreed_text_is_ascii() -> None:
    """For the license file (ASCII): letters it can't hold become "_"."""
    who = adding.Asker(None, None, None, "Cocina de José")
    assert adding.agreed_text(who) == "by voice, from Cocina de Jos_"
