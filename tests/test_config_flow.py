"""Setting EBaC up (config_flow.py): by the EBaC app's announcement, or an
address typed; and its options (Configure)."""

from __future__ import annotations

from homeassistant.config_entries import SOURCE_HASSIO, SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

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

from .conftest import setup_ebac
from .fake_ebac import URL, FakeEbac

NONE_ALLOWED = {CONF_ALLOW_CHANGE: False, CONF_ALLOW_ADD: False, CONF_ALLOW_REMOVE: False}

DISCOVERY = HassioServiceInfo(
    config={"host": "ebac.test", "port": 8080, "path": "/cgi-bin/ebac"},
    name="EBaC",
    slug="bda2b308_ebac",
    uuid="1234",
)


def default(result, key: str):
    """The value a form's field starts with."""
    for field in result["data_schema"].schema:
        if field == key:
            return field.default()
    raise KeyError(key)


async def test_user_setup(hass: HomeAssistant, ebac: FakeEbac) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # (typed with a "/" at the end, and spaces)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: f"  {URL}/ "}
    )
    assert result["step_id"] == "translation"
    # the King James Version is offered first
    assert default(result, CONF_TRANSLATION) == "AV"
    assert default(result, CONF_SOURCE) == "scrollmapper"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TRANSLATION: "WLC", CONF_SOURCE: "gutenberg", CONF_LANGUAGE: "es", **NONE_ALLOWED},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_URL: URL}
    assert result["options"] == {
        CONF_TRANSLATION: "WLC",
        CONF_READ_ON: 5,
        CONF_SOURCE: "gutenberg",
        CONF_LANGUAGE: "es",
        **NONE_ALLOWED,
    }
    await hass.async_block_till_done()


async def test_first_translation_offered_without_the_av(
    hass: HomeAssistant, ebac: FakeEbac
) -> None:
    ebac.installed = ["WLC", "KJVA-SM"]
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: URL})
    assert default(result, CONF_TRANSLATION) == "WLC"


async def test_user_cannot_connect(hass: HomeAssistant, ebac: FakeEbac) -> None:
    ebac.down = True
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: URL})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # and once EBaC answers, it goes on
    ebac.down = False
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: URL})
    assert result["step_id"] == "translation"


async def test_user_no_translations(hass: HomeAssistant, ebac: FakeEbac) -> None:
    ebac.installed = []
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: URL})
    assert result["errors"] == {"base": "no_translations"}


async def test_permissions_each_need_the_one_above(
    hass: HomeAssistant, ebac: FakeEbac
) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: URL})
    given = {CONF_TRANSLATION: "AV", CONF_SOURCE: "scrollmapper", CONF_LANGUAGE: "en"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**given, CONF_ALLOW_CHANGE: False, CONF_ALLOW_ADD: True, CONF_ALLOW_REMOVE: False},
    )
    assert result["errors"] == {CONF_ALLOW_ADD: "add_needs_change"}
    # (what was checked stays checked, to be put right)
    assert default(result, CONF_ALLOW_ADD) is True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**given, CONF_ALLOW_CHANGE: True, CONF_ALLOW_ADD: False, CONF_ALLOW_REMOVE: True},
    )
    assert result["errors"] == {CONF_ALLOW_REMOVE: "remove_needs_add"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {**given, CONF_ALLOW_CHANGE: True, CONF_ALLOW_ADD: True, CONF_ALLOW_REMOVE: True},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()


async def test_only_one(hass: HomeAssistant, ebac: FakeEbac) -> None:
    await setup_ebac(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_found_by_the_app(hass: HomeAssistant, ebac: FakeEbac) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=DISCOVERY
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "hassio_confirm"
    assert result["description_placeholders"] == {"app": "EBaC"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "translation"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TRANSLATION: "AV", CONF_SOURCE: "scrollmapper", CONF_LANGUAGE: "en", **NONE_ALLOWED},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_URL: URL}
    await hass.async_block_till_done()


async def test_found_by_the_app_not_answering(hass: HomeAssistant, ebac: FakeEbac) -> None:
    ebac.down = True
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=DISCOVERY
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["step_id"] == "hassio_confirm"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_app_moved(hass: HomeAssistant, ebac: FakeEbac) -> None:
    """Already set up: the app's announcement of a new address is followed."""
    entry = await setup_ebac(hass)
    moved = HassioServiceInfo(
        config={"host": "ebac.test", "port": 8080, "path": "/cgi-bin/ebac2"},
        name="EBaC",
        slug="bda2b308_ebac",
        uuid="1234",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=moved
    )
    await hass.async_block_till_done()
    # not offered again; the new address followed, and EBaC set up with it
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_URL] == "http://ebac.test:8080/cgi-bin/ebac2"
    assert entry.state is ConfigEntryState.LOADED


async def test_app_announced_again(hass: HomeAssistant, ebac: FakeEbac) -> None:
    """Already set up, at the same address (each restart of the app): not
    offered again, and nothing changes."""
    entry = await setup_ebac(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_HASSIO}, data=DISCOVERY
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_URL] == URL
    assert not hass.config_entries.flow.async_progress()


async def test_options(hass: HomeAssistant, ebac: FakeEbac) -> None:
    entry = await setup_ebac(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert default(result, CONF_TRANSLATION) == "AV"
    assert default(result, CONF_READ_ON) == 5

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_TRANSLATION: "KJVA-SM",
            # (a number box gives a float)
            CONF_READ_ON: 8.0,
            CONF_SOURCE: "thiagobodruk",
            CONF_LANGUAGE: "en",
            CONF_ALLOW_CHANGE: True,
            CONF_ALLOW_ADD: False,
            CONF_ALLOW_REMOVE: False,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options[CONF_READ_ON] == 8
    assert isinstance(entry.options[CONF_READ_ON], int)
    # and EBaC reads from the new translation, and as much as asked
    data = entry.runtime_data
    assert (data.translation, data.read_on, data.source) == ("KJVA-SM", 8, "thiagobodruk")
    assert data.allow_change


async def test_options_permissions(hass: HomeAssistant, ebac: FakeEbac) -> None:
    entry = await setup_ebac(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_TRANSLATION: "AV",
            CONF_READ_ON: 5,
            CONF_SOURCE: "scrollmapper",
            CONF_LANGUAGE: "en",
            CONF_ALLOW_CHANGE: False,
            CONF_ALLOW_ADD: True,
            CONF_ALLOW_REMOVE: False,
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_ALLOW_ADD: "add_needs_change"}


async def test_options_translation_gone(hass: HomeAssistant, ebac: FakeEbac) -> None:
    """The translation in use removed in the app: the first installed is
    offered, not one that isn't there."""
    entry = await setup_ebac(hass, **{CONF_TRANSLATION: "KJVA-SM"})
    ebac.installed = ["AV", "WLC"]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert default(result, CONF_TRANSLATION) == "AV"


async def test_options_cannot_connect(hass: HomeAssistant, ebac: FakeEbac) -> None:
    entry = await setup_ebac(hass)
    ebac.down = True
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
