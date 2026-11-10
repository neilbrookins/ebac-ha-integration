"""Through Assist, as when spoken: Home Assistant's own conversation agent
reads the sentence file the integration writes (sentences.py), matches
the words, and calls EBaC's intents.

These are the tests most likely to fail first when a Home Assistant
release changes how custom sentences are read or matched."""

from __future__ import annotations

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.ebac.const import CONF_TRANSLATION

from .conftest import ALLOW_ALL, ask, setup_ebac
from .fake_ebac import FakeEbac
from .test_intents import refs


@pytest.fixture
async def assist(hass: HomeAssistant, ebac: FakeEbac) -> None:
    """Assist, and EBaC reading the AV."""
    assert await async_setup_component(hass, "conversation", {})
    await setup_ebac(hass)


@pytest.mark.usefixtures("assist")
@pytest.mark.parametrize(
    ("said", "verses"),
    [
        ("John 3:16", ["John 3:16"]),
        ("John 3:16-18", ["John 3:16", "John 3:17", "John 3:18"]),
        ("John three sixteen", ["John 3:16"]),
        ("john chapter 3 verse 16", ["John 3:16"]),
        ("John 3 colon 16 to 18", ["John 3:16", "John 3:17", "John 3:18"]),
        ("John three sixteen through eighteen", ["John 3:16", "John 3:17", "John 3:18"]),
        ("Read the book of John chapter 3 verse 16", ["John 3:16"]),
        ("Genesis I colon I", ["Genesis 1:1"]),
        ("Psalm one hundred nineteen verse one", ["Psalms 119:1"]),
        ("Psalms 119:15", ["Psalms 119:15"]),
        ("1 Samuel 3:4", ["1 Samuel 3:4"]),
        ("First Samuel 3:4", ["1 Samuel 3:4"]),
        ("I Samuel 3:4", ["1 Samuel 3:4"]),
        ("Revelations 22:21", ["Revelation 22:21"]),
        ("Jude 3 to 5", ["Jude 1:3", "Jude 1:4", "Jude 1:5"]),
        # a chapter alone, or a book: as many as "read on" (5)
        ("Psalm 23", [f"Psalms 23:{v}" for v in range(1, 6)]),
        ("John chapter 3", [f"John 3:{v}" for v in range(1, 6)]),
        ("read Genesis", [f"Genesis 1:{v}" for v in range(1, 6)]),
    ],
)
async def test_references(hass: HomeAssistant, said: str, verses: list[str]) -> None:
    assert refs(await ask(hass, said)) == verses


@pytest.mark.usefixtures("assist")
async def test_two_digits_are_one_number(hass: HomeAssistant) -> None:
    """"John 23" is chapter 23 (which John hasn't), not John 2:3."""
    assert await ask(hass, "John 23") == "John has 21 chapters."


@pytest.mark.usefixtures("assist")
async def test_reading_on(hass: HomeAssistant) -> None:
    await ask(hass, "John 3:16")
    assert refs(await ask(hass, "next verse")) == ["John 3:17"]
    assert refs(await ask(hass, "go back a verse")) == ["John 3:16"]
    assert refs(await ask(hass, "read that again")) == ["John 3:16"]
    assert refs(await ask(hass, "again")) == ["John 3:16"]
    assert refs(await ask(hass, "read on")) == [f"John 3:{v}" for v in range(17, 22)]
    assert refs(await ask(hass, "next chapter"))[0] == "John 4:1"
    assert refs(await ask(hass, "previous book"))[0] == "Psalms 1:1"
    assert refs(await ask(hass, "go to the start of the book"))[0] == "Psalms 1:1"


@pytest.mark.usefixtures("assist")
async def test_each_speaker_its_own_place(hass: HomeAssistant) -> None:
    await ask(hass, "John 3:16", device="kitchen")
    await ask(hass, "Genesis 1:1", device="bedroom")
    assert refs(await ask(hass, "next verse", device="kitchen")) == ["John 3:17"]
    assert refs(await ask(hass, "next verse", device="bedroom")) == ["Genesis 1:2"]


@pytest.mark.usefixtures("assist")
async def test_search(hass: HomeAssistant) -> None:
    assert (await ask(hass, "search the Bible for love")).startswith('12 verses have "love": 1,')
    assert (await ask(hass, "result two")).startswith("Result 2 of 12.")
    assert (await ask(hass, "the third result")).startswith("Result 3 of 12.")
    assert (await ask(hass, "next result")).startswith("Result 4 of 12.")
    assert (await ask(hass, "more results")).startswith("6, John 13:3")
    assert (await ask(hass, "go back to the results")).startswith('12 verses have "love", and')
    assert (await ask(hass, "find jesus wept in the bible")).startswith(
        'One verse has "jesus wept"'
    )


@pytest.mark.usefixtures("assist")
async def test_information(hass: HomeAssistant) -> None:
    assert await ask(hass, "which translation is this") == "Reading from King James Version (AV)."
    assert (await ask(hass, "what version of EBaC is this")).startswith("This is EBaC 1.3.0")
    assert (await ask(hass, "what is the license of this translation")).startswith(
        "No license was recorded"
    )


@pytest.mark.usefixtures("assist")
async def test_other_sentences_left_alone(hass: HomeAssistant, ebac: FakeEbac) -> None:
    """Sentences that aren't EBaC's are Home Assistant's: EBaC isn't asked."""
    asked = len(ebac.requests)
    for said in ("turn on the kitchen light", "what time is it", "Mark the door closed"):
        await ask(hass, said)
    assert len(ebac.requests) == asked


async def test_book_of_another_translation(hass: HomeAssistant, ebac: FakeEbac) -> None:
    """Reading the Hebrew Bible, "John 3:16" is understood (the sentences
    have every translation's books), and answered that it has no John."""
    assert await async_setup_component(hass, "conversation", {})
    await setup_ebac(hass, **{CONF_TRANSLATION: "WLC"})
    assert await ask(hass, "John 3:16") == "The Westminster Leningrad Codex has no John."


async def test_by_voice_with_everything_allowed(hass: HomeAssistant, ebac: FakeEbac) -> None:
    assert await async_setup_component(hass, "conversation", {})
    entry = await setup_ebac(hass, **ALLOW_ALL)
    assert await ask(hass, "change the translation to K J V A") == (
        "Now reading from King James Version with Apocrypha (KJVA-SM)."
    )
    await hass.async_block_till_done()
    assert entry.options[CONF_TRANSLATION] == "KJVA-SM"

    assert (await ask(hass, "use Spanish translations")).startswith(
        "Translations in Spanish from now on"
    )
    await hass.async_block_till_done()
    assert (await ask(hass, "use translation scrollmapper")).startswith(
        "Already adding translations from scrollmapper/bible_databases"
    )
    assert (await ask(hass, "what translations can I add")).startswith("1 in Spanish")
    assert (await ask(hass, "add translation RVG")).endswith(
        "Say yes or no: do you agree to its license?"
    )
    assert await ask(hass, "no thanks") == "All right: Reina Valera Gómez (RVG-SM) isn't added."
    assert (await ask(hass, "remove the translation WLC")).startswith("Say yes or no")
    assert await ask(hass, "yes please") == "Removed The Westminster Leningrad Codex (WLC)."
    await hass.async_block_till_done()
