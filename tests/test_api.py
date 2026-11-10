"""The client of ebac-api and ebac-admin (api.py)."""

from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.ebac.api import EbacApi, EbacError, EbacUnreachable

from .fake_ebac import URL, FakeEbac


@pytest.fixture
def api(hass: HomeAssistant, ebac: FakeEbac) -> EbacApi:
    return EbacApi(async_get_clientsession(hass), URL)


@pytest.mark.parametrize(
    ("url", "admin"),
    [
        # the app's address, and with a "/" typed after it
        (URL, "http://ebac.test:8080/cgi-bin/ebac-admin"),
        (URL + "/", "http://ebac.test:8080/cgi-bin/ebac-admin"),
        # a web server's own name for ebac-api: ebac-admin beside it
        ("http://web.test/cgi-bin/bible", "http://web.test/cgi-bin/ebac-admin"),
    ],
)
async def test_admin_beside_api(hass: HomeAssistant, url: str, admin: str) -> None:
    api = EbacApi(async_get_clientsession(hass), url)
    assert api._admin == admin


async def test_verse(api: EbacApi, ebac: FakeEbac) -> None:
    answer = await api.verse("AV", "John 3:16")
    assert [v["ref"] for v in answer["verses"]] == ["John 3:16"]
    # the translation and reference are sent; a count not given isn't
    assert ebac.requests[-1] == ("verse", {"t": "AV", "ref": "John 3:16"})


async def test_no_translation_given_is_not_sent(api: EbacApi, ebac: FakeEbac) -> None:
    """None means EBaC's own default: the parameter is left out, not "None"."""
    await api.books(None)
    assert ebac.requests[-1] == ("books", {})


async def test_error_answer_is_spoken_message(api: EbacApi) -> None:
    """ebac-api's {"error": ...} becomes the message Assist says."""
    with pytest.raises(EbacError, match="There is no John 3:41") as err:
        await api.verse("AV", "John 3:41")
    assert not isinstance(err.value, EbacUnreachable)


async def test_unreachable(api: EbacApi, ebac: FakeEbac) -> None:
    ebac.down = True
    with pytest.raises(EbacUnreachable, match="can't be reached"):
        await api.translations()


async def test_not_json(api: EbacApi, ebac: FakeEbac) -> None:
    """A web server's error page: answered, but not understood."""
    ebac.broken = True
    with pytest.raises(EbacError, match="wasn't understood") as err:
        await api.translations()
    assert not isinstance(err.value, EbacUnreachable)


async def test_said(api: EbacApi) -> None:
    assert await api.said() == [{"word": "יהוה", "say": "Adonai"}]


async def test_said_from_older_ebac(api: EbacApi, ebac: FakeEbac) -> None:
    """An EBaC from before "said": no words to say another way, no error."""
    ebac.api_said = None  # (no such request: HTTP 404, {"error": ...})
    assert await api.said() == []


async def test_said_unreachable_is_still_an_error(api: EbacApi, ebac: FakeEbac) -> None:
    """Unreachable isn't mistaken for an older EBaC (the repair needs it)."""
    ebac.down = True
    with pytest.raises(EbacUnreachable):
        await api.said()


async def test_admin_requests(api: EbacApi, ebac: FakeEbac) -> None:
    await api.catalog("gutenberg")
    assert ebac.requests[-1] == ("admin/catalog", {"source": "gutenberg"})
    await api.add("LITV-SM", "by voice, from Kitchen", "scrollmapper")
    assert ebac.requests[-1] == (
        "admin/add",
        {"name": "LITV-SM", "agreed": "by voice, from Kitchen", "source": "scrollmapper"},
    )


async def test_admin_refusal(api: EbacApi, ebac: FakeEbac) -> None:
    """The app's options not allowing it: HTTP 403, said as EBaC says it."""
    ebac.allow_remove = False
    with pytest.raises(EbacError, match="don't allow voice to remove"):
        await api.remove("WLC")
