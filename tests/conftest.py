"""What the tests share: the fake EBaC (fake_ebac.py), answering the
integration's HTTP requests, and EBaC set up with it."""

from __future__ import annotations

import re
from typing import Any

import aiohttp
import pytest

from homeassistant.components import conversation
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import (
    AiohttpClientMocker,
    AiohttpClientMockResponse,
)

from custom_components.ebac.const import (
    CONF_ALLOW_ADD,
    CONF_ALLOW_CHANGE,
    CONF_ALLOW_REMOVE,
    CONF_LANGUAGE,
    CONF_READ_ON,
    CONF_SOURCE,
    CONF_TRANSLATION,
    CONF_URL,
    DOMAIN,
)

from .fake_ebac import URL, Answer, FakeEbac

# Each permission checkbox, as Configure sets them all
ALLOW_ALL = {CONF_ALLOW_CHANGE: True, CONF_ALLOW_ADD: True, CONF_ALLOW_REMOVE: True}


@pytest.fixture(autouse=True)
def no_deprecation_reports(caplog: pytest.LogCaptureFixture):
    """Home Assistant tells of what it will stop supporting months before
    it does: "Detected that custom integration 'ebac' ... This will stop
    working in Home Assistant 2027.5". Any such report fails the test, so
    it is seen here, in time to change, not in someone's log."""
    yield
    reports = [
        record.getMessage()
        for record in caplog.records
        if "custom integration 'ebac'" in record.getMessage()
    ]
    assert not reports, reports


@pytest.fixture
def hass_config_dir(hass_tmp_config_dir: str) -> str:
    """A config directory of each test's own: the integration writes its
    sentence file in it (custom_sentences/en/ebac.yaml)."""
    return hass_tmp_config_dir


@pytest.fixture
async def ebac(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> FakeEbac:
    """The fake EBaC, answering at fake_ebac.URL (and ebac-admin beside it);
    and Home Assistant's core integration, always set up in a home (Assist
    needs it: its exposed entities)."""
    assert await async_setup_component(hass, "homeassistant", {})
    fake = FakeEbac()

    async def respond(method: str, url: Any, data: Any) -> AiohttpClientMockResponse:
        # /cgi-bin/ebac/verse or /cgi-bin/ebac-admin/add
        program, _, request = url.path.removeprefix("/cgi-bin/").partition("/")
        params = dict(url.query)
        path = f"admin/{request}" if program == "ebac-admin" else request
        fake.requests.append((path, params))
        if fake.down:
            return AiohttpClientMockResponse(
                method, url, exc=aiohttp.ClientConnectionError("refused")
            )
        if fake.broken:
            return AiohttpClientMockResponse(method, url, status=502, text="<html>Bad gateway</html>")
        try:
            answer = fake.answer(path, params)
        except Answer as err:
            return AiohttpClientMockResponse(method, url, status=err.status, json={"error": str(err)})
        return AiohttpClientMockResponse(method, url, json=answer)

    aioclient_mock.get(re.compile(r"^http://ebac\.test:8080/"), side_effect=respond)
    return fake


def make_entry(**options: Any) -> MockConfigEntry:
    """EBaC's config entry, as the setup makes it, with options changed."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="EBaC",
        unique_id=DOMAIN,
        data={CONF_URL: URL},
        options={
            CONF_TRANSLATION: "AV",
            CONF_READ_ON: 5,
            CONF_SOURCE: "scrollmapper",
            CONF_LANGUAGE: "en",
            CONF_ALLOW_CHANGE: False,
            CONF_ALLOW_ADD: False,
            CONF_ALLOW_REMOVE: False,
            **options,
        },
    )


async def setup_ebac(hass: HomeAssistant, **options: Any) -> MockConfigEntry:
    """EBaC set up (the fake EBaC must be answering)."""
    entry = make_entry(**options)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
async def entry(hass: HomeAssistant, ebac: FakeEbac) -> MockConfigEntry:
    """EBaC set up as by default: reading the AV, nothing more allowed."""
    return await setup_ebac(hass)


async def say(
    hass: HomeAssistant,
    intent_type: str,
    device: str | None = "kitchen",
    **slots: Any,
) -> str:
    """What EBaC answers to an intent, said on a voice device (its handler
    alone: test_assist.py goes through Assist's sentences)."""
    response = await intent.async_handle(
        hass,
        "test",
        intent_type,
        {name: {"value": value} for name, value in slots.items()},
        context=Context(),
        device_id=device,
    )
    return response.speech["plain"]["speech"]


async def ask(hass: HomeAssistant, text: str, device: str | None = "kitchen") -> str:
    """What Assist answers to words said, as from a voice device."""
    result = await conversation.async_converse(
        hass, text, None, Context(), language="en", device_id=device
    )
    return result.response.speech["plain"]["speech"]
