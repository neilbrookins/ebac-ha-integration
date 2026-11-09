"""What EBaC answers to each intent (intents.py), its handlers alone:
reading, moving through the text, searches, translations, the language
group and source, adding and removing, and what each checkbox allows.
(test_assist.py goes through Assist's sentences to the same handlers.)"""

from __future__ import annotations

import re
import time
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant.common import MockConfigEntry

from custom_components.ebac.const import (
    CONF_ALLOW_ADD,
    CONF_ALLOW_CHANGE,
    CONF_LANGUAGE,
    CONF_SOURCE,
    CONF_TRANSLATION,
    DOMAIN,
    INTENT_ADD,
    INTENT_BACK_TO_RESULTS,
    INTENT_EARLIER_LIST,
    INTENT_EARLIER_RESULTS,
    INTENT_LICENSE,
    INTENT_LIST_ADDED,
    INTENT_LIST_AVAILABLE,
    INTENT_LIST_LANGUAGES,
    INTENT_MORE_LIST,
    INTENT_MORE_RESULTS,
    INTENT_NEXT,
    INTENT_NEXT_BOOK,
    INTENT_NEXT_CHAPTER,
    INTENT_NEXT_RESULT,
    INTENT_NO,
    INTENT_PREVIOUS,
    INTENT_PREVIOUS_BOOK,
    INTENT_PREVIOUS_CHAPTER,
    INTENT_PREVIOUS_RESULT,
    INTENT_READ,
    INTENT_READ_BACK,
    INTENT_READ_ON,
    INTENT_REMOVE,
    INTENT_REPEAT,
    INTENT_RESULT,
    INTENT_SEARCH,
    INTENT_START_BOOK,
    INTENT_START_CHAPTER,
    INTENT_TRANSLATION,
    INTENT_USE_LANGUAGE,
    INTENT_VERSION,
    INTENT_WHICH_TRANSLATION,
    INTENT_YES,
)
from custom_components.ebac.intents import NO_PLACE, NO_RESULTS

from .conftest import ALLOW_ALL, say, setup_ebac
from .fake_ebac import FakeEbac

CHANGE_ONLY = {CONF_ALLOW_CHANGE: True}


def refs(speech: str) -> list[str]:
    """The verses read in an answer: ["John 3:16", "John 3:17"]."""
    return [
        f"{book} {chapter}:{verse}"
        for book, chapter, verse in re.findall(
            r"((?:\d )?[A-Z][a-z]+) chapter (\d+), verse (\d+)\.", speech
        )
    ]


async def read(hass: HomeAssistant, book: str, chapter=None, verse=None, to=None,
               device: str = "kitchen") -> str:
    slots = {"book": book}
    for name, value in (("chapter", chapter), ("verse", verse), ("to", to)):
        if value is not None:
            slots[name] = value
    return await say(hass, INTENT_READ, device=device, **slots)


# ---- reading


async def test_read_verse(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    speech = await read(hass, "John", 3, 16)
    assert speech == "John chapter 3, verse 16. John 3:16 text."


async def test_read_range(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert refs(await read(hass, "John", 3, 16, 18)) == ["John 3:16", "John 3:17", "John 3:18"]


@pytest.mark.parametrize(
    ("chapter", "verse"),
    # numbers as Assist may give them: whole, a float, text
    [(3, 16), (3.0, 16.0), ("3", "16")],
)
async def test_numbers_however_given(
    hass: HomeAssistant, entry: MockConfigEntry, chapter, verse
) -> None:
    assert refs(await read(hass, "John", chapter, verse)) == ["John 3:16"]


async def test_chapter_alone_reads_on(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """"Psalm 23": its first verses, as many as "read on" (5)."""
    assert refs(await read(hass, "Psalms", 23)) == [f"Psalms 23:{v}" for v in range(1, 6)]


async def test_book_alone(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert refs(await read(hass, "Genesis")) == [f"Genesis 1:{v}" for v in range(1, 6)]


async def test_one_chapter_book(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """"Jude 3 to 5": the reference is EBaC's to read (Jude 1:3-5)."""
    speech = await read(hass, "Jude", 3, to=5)
    assert refs(speech) == ["Jude 1:3", "Jude 1:4", "Jude 1:5"]


async def test_book_of_another_translation(hass: HomeAssistant, ebac: FakeEbac) -> None:
    """"John 3:16" while reading the Hebrew Bible: said it has no John (and
    no "The The")."""
    await setup_ebac(hass, **{CONF_TRANSLATION: "WLC"})
    assert await read(hass, "John", 3, 16) == "The Westminster Leningrad Codex has no John."


async def test_ebac_error_spoken(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """EBaC's message is said, ending as a sentence."""
    assert await read(hass, "John", 3, 40) == "There is no John 3:40."


async def test_ebac_unreachable_spoken(
    hass: HomeAssistant, entry: MockConfigEntry, ebac: FakeEbac
) -> None:
    ebac.down = True
    speech = await read(hass, "John", 3, 16)
    assert speech == "EBaC can't be reached at http://ebac.test:8080/cgi-bin/ebac."


async def test_next_previous_repeat(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert await say(hass, INTENT_NEXT) == NO_PLACE

    await read(hass, "John", 3, 16, 18)
    assert refs(await say(hass, INTENT_NEXT)) == ["John 3:19"]
    assert refs(await say(hass, INTENT_PREVIOUS)) == ["John 3:18"]
    assert refs(await say(hass, INTENT_PREVIOUS)) == ["John 3:17"]
    assert refs(await say(hass, INTENT_REPEAT)) == ["John 3:17"]


async def test_repeat_a_range(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await read(hass, "John", 3, 16, 18)
    assert refs(await say(hass, INTENT_REPEAT)) == ["John 3:16", "John 3:17", "John 3:18"]


async def test_read_on(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await read(hass, "John", 3, 16)
    assert refs(await say(hass, INTENT_READ_ON)) == [f"John 3:{v}" for v in range(17, 22)]


async def test_next_across_chapters(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await read(hass, "John", 3, 30)
    assert refs(await say(hass, INTENT_NEXT)) == ["John 4:1"]


async def test_each_device_its_own_place(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await read(hass, "John", 3, 16, device="kitchen")
    await read(hass, "Genesis", 1, 1, device="bedroom")
    assert refs(await say(hass, INTENT_NEXT, device="kitchen")) == ["John 3:17"]
    assert refs(await say(hass, INTENT_NEXT, device="bedroom")) == ["Genesis 1:2"]
    # and a device that read nothing has no place
    assert await say(hass, INTENT_NEXT, device="garage") == NO_PLACE


async def test_place_follows_a_changed_translation(
    hass: HomeAssistant, ebac: FakeEbac
) -> None:
    """Changed to the KJVA (the Apocrypha before John: John 3:16 is another
    verse number there): "next verse" goes on by reference."""
    entry = await setup_ebac(hass)
    await read(hass, "John", 3, 16)
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_TRANSLATION: "KJVA"}
    )
    await hass.async_block_till_done()
    assert refs(await say(hass, INTENT_NEXT)) == ["John 3:17"]
    assert refs(await say(hass, INTENT_PREVIOUS)) == ["John 3:16"]


# ---- moving through the text


async def test_next_chapter(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await read(hass, "John", 3, 16)
    assert refs(await say(hass, INTENT_NEXT_CHAPTER))[0] == "John 4:1"


async def test_next_chapter_into_next_book(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await read(hass, "John", 21, 25)
    assert refs(await say(hass, INTENT_NEXT_CHAPTER))[0] == "Jude 1:1"


async def test_previous_chapter_into_book_before(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    await read(hass, "John", 1, 1)
    assert refs(await say(hass, INTENT_PREVIOUS_CHAPTER))[0] == "Psalms 150:1"


async def test_ends_of_the_bible(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await read(hass, "Revelation", 22, 21)
    assert await say(hass, INTENT_NEXT_CHAPTER) == "That's the end of the King James Version."
    assert await say(hass, INTENT_NEXT_BOOK) == "That's the end of the King James Version."
    await read(hass, "Genesis", 1, 1)
    assert await say(hass, INTENT_PREVIOUS_CHAPTER) == (
        "That's the beginning of the King James Version."
    )
    assert await say(hass, INTENT_PREVIOUS_BOOK) == (
        "That's the beginning of the King James Version."
    )
    assert await say(hass, INTENT_READ_BACK) == "That's the beginning of the King James Version."


async def test_ends_with_a_title_starting_the(hass: HomeAssistant, ebac: FakeEbac) -> None:
    await setup_ebac(hass, **{CONF_TRANSLATION: "WLC"})
    await read(hass, "Psalms", 150, 6)
    assert await say(hass, INTENT_NEXT_BOOK) == (
        "That's the end of The Westminster Leningrad Codex."
    )


async def test_books(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await read(hass, "John", 3, 16)
    assert refs(await say(hass, INTENT_NEXT_BOOK))[0] == "Jude 1:1"
    assert refs(await say(hass, INTENT_PREVIOUS_BOOK))[0] == "John 1:1"
    assert refs(await say(hass, INTENT_PREVIOUS_BOOK))[0] == "Psalms 1:1"


async def test_starts(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await read(hass, "John", 3, 16)
    assert refs(await say(hass, INTENT_START_CHAPTER)) == [f"John 3:{v}" for v in range(1, 6)]
    await read(hass, "John", 3, 16)
    assert refs(await say(hass, INTENT_START_BOOK))[0] == "John 1:1"


async def test_read_back(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await read(hass, "John", 3, 16)
    assert refs(await say(hass, INTENT_READ_BACK)) == [f"John 3:{v}" for v in range(11, 16)]


async def test_moving_without_a_place(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    for intent_type in (INTENT_NEXT_CHAPTER, INTENT_PREVIOUS_BOOK, INTENT_START_CHAPTER,
                        INTENT_READ_BACK, INTENT_READ_ON, INTENT_REPEAT, INTENT_PREVIOUS):
        assert await say(hass, intent_type) == NO_PLACE, intent_type


# ---- searches


async def test_search_one_verse(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    speech = await say(hass, INTENT_SEARCH, words="Jesus wept.")
    assert speech.startswith('One verse has "Jesus wept": John chapter 11, verse 35.')
    # and it is the place
    assert refs(await say(hass, INTENT_NEXT)) == ["John 11:36"]


async def test_search_nothing(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert await say(hass, INTENT_SEARCH, words="zzz") == 'No verse has "zzz".'
    assert await say(hass, INTENT_NEXT_RESULT) == NO_RESULTS


async def test_search_results(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    speech = await say(hass, INTENT_SEARCH, words="love")
    assert speech == (
        '12 verses have "love": 1, John 3:1; 2, John 3:2; 3, John 3:3; '
        "4, John 13:1; 5, John 13:2. Say a result's number, or more results (5 of 12)."
    )
    assert (await say(hass, INTENT_RESULT, number=2)).startswith(
        "Result 2 of 12. John chapter 3, verse 2."
    )
    assert (await say(hass, INTENT_NEXT_RESULT)).startswith("Result 3 of 12.")
    assert (await say(hass, INTENT_PREVIOUS_RESULT)).startswith("Result 2 of 12.")
    # a result read is the place, for "next verse"
    assert refs(await say(hass, INTENT_NEXT)) == ["John 3:3"]

    assert await say(hass, INTENT_RESULT, number=13) == "That was the last result: there are 12."
    await say(hass, INTENT_RESULT, number=1)
    assert await say(hass, INTENT_PREVIOUS_RESULT) == "That was the first result."


async def test_search_lists(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await say(hass, INTENT_SEARCH, words="love")
    assert (await say(hass, INTENT_MORE_RESULTS)).startswith("6, John 13:3; 7, John 14:1")
    assert await say(hass, INTENT_MORE_RESULTS) == (
        "11, John 15:2; 12, John 15:3. Say a result's number."
    )
    assert await say(hass, INTENT_MORE_RESULTS) == (
        "That's all 12 results. Say a result's number."
    )
    assert (await say(hass, INTENT_EARLIER_RESULTS)).startswith("6, John 13:3")
    assert (await say(hass, INTENT_EARLIER_RESULTS)).startswith("1, John 3:1")
    assert (await say(hass, INTENT_EARLIER_RESULTS)).startswith("1, John 3:1")


async def test_back_to_the_results(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await say(hass, INTENT_SEARCH, words="love")
    await say(hass, INTENT_RESULT, number=7)
    await say(hass, INTENT_NEXT)
    assert (await say(hass, INTENT_BACK_TO_RESULTS)).startswith(
        '12 verses have "love", and you were at result 7: 6, John 13:3;'
    )


async def test_results_need_a_search(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    for intent_type in (INTENT_NEXT_RESULT, INTENT_PREVIOUS_RESULT, INTENT_MORE_RESULTS,
                        INTENT_EARLIER_RESULTS, INTENT_BACK_TO_RESULTS):
        assert await say(hass, intent_type) == NO_RESULTS, intent_type
    assert await say(hass, INTENT_RESULT, number=1) == NO_RESULTS


async def test_each_device_its_own_search(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await say(hass, INTENT_SEARCH, words="love", device="kitchen")
    assert await say(hass, INTENT_NEXT_RESULT, device="bedroom") == NO_RESULTS


async def test_results_in_a_changed_translation(hass: HomeAssistant, ebac: FakeEbac) -> None:
    """Searched again in the translation changed to, from its first result."""
    entry = await setup_ebac(hass)
    await say(hass, INTENT_SEARCH, words="love")
    await say(hass, INTENT_RESULT, number=4)
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_TRANSLATION: "KJVA"}
    )
    await hass.async_block_till_done()
    assert (await say(hass, INTENT_NEXT_RESULT)).startswith("Result 1 of 12.")


async def test_results_gone_in_the_hebrew_bible(hass: HomeAssistant, ebac: FakeEbac) -> None:
    """Every result in John: none in the translation changed to."""
    entry = await setup_ebac(hass)
    await say(hass, INTENT_SEARCH, words="love")
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_TRANSLATION: "WLC"}
    )
    await hass.async_block_till_done()
    assert await say(hass, INTENT_NEXT_RESULT) == NO_RESULTS


# ---- the translation


async def test_change_not_allowed(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    speech = await say(hass, INTENT_TRANSLATION, name="WLC")
    assert speech == (
        "Changing the translation by voice isn't allowed. It can be allowed under "
        "Configure, in the EBaC integration's settings."
    )
    assert entry.options[CONF_TRANSLATION] == "AV"


@pytest.mark.parametrize("said", ["KJVA", "K J V A", "kjva.", "K.J.V.A"])
async def test_change_by_short_name(hass: HomeAssistant, ebac: FakeEbac, said: str) -> None:
    entry = await setup_ebac(hass, **CHANGE_ONLY)
    speech = await say(hass, INTENT_TRANSLATION, name=said)
    assert speech == "Now reading from King James Version with Apocrypha (KJVA)."
    await hass.async_block_till_done()
    assert entry.options[CONF_TRANSLATION] == "KJVA"
    assert entry.runtime_data.translation == "KJVA"


async def test_change_by_title(hass: HomeAssistant, ebac: FakeEbac) -> None:
    await setup_ebac(hass, **CHANGE_ONLY)
    assert await say(hass, INTENT_TRANSLATION, name="Westminster Leningrad") == (
        "Now reading from The Westminster Leningrad Codex (WLC)."
    )


async def test_change_ambiguous(hass: HomeAssistant, ebac: FakeEbac) -> None:
    entry = await setup_ebac(hass, **CHANGE_ONLY)
    assert await say(hass, INTENT_TRANSLATION, name="King James") == (
        "Which one: King James Version (AV); or King James Version with Apocrypha (KJVA)?"
    )
    assert entry.options[CONF_TRANSLATION] == "AV"


async def test_change_to_exact_title(hass: HomeAssistant, ebac: FakeEbac) -> None:
    """A title that is just the words said wins over longer ones."""
    await setup_ebac(hass, **CHANGE_ONLY)
    assert await say(hass, INTENT_TRANSLATION, name="King James Version") == (
        "Already reading from King James Version (AV)."
    )


async def test_change_to_unknown(hass: HomeAssistant, ebac: FakeEbac) -> None:
    await setup_ebac(hass, **CHANGE_ONLY)
    assert await say(hass, INTENT_TRANSLATION, name="Klingon") == (
        'No translation installed is called "Klingon". Installed: King James Version (AV); '
        "The Westminster Leningrad Codex (WLC); King James Version with Apocrypha (KJVA)."
    )


async def test_which_translation_keeps_others_private(
    hass: HomeAssistant, entry: MockConfigEntry
) -> None:
    """With changing not allowed, the others aren't named (a translation
    may be private: a diary imported as one)."""
    assert await say(hass, INTENT_WHICH_TRANSLATION) == "Reading from King James Version (AV)."
    assert await say(hass, INTENT_LIST_ADDED) == "Reading from King James Version (AV)."


async def test_which_translation(hass: HomeAssistant, ebac: FakeEbac) -> None:
    await setup_ebac(hass, **CHANGE_ONLY)
    assert await say(hass, INTENT_WHICH_TRANSLATION) == (
        "Reading from King James Version (AV). Also installed: The Westminster "
        "Leningrad Codex (WLC); King James Version with Apocrypha (KJVA)."
    )
    assert (await say(hass, INTENT_LIST_ADDED)).startswith(
        "3 added: 1, King James Version (AV); 2, The Westminster Leningrad Codex (WLC)"
    )


# ---- information


async def test_version(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert (await say(hass, INTENT_VERSION)).startswith(
        "This is EBaC 1.3.0, built from commit abc1234, in the EBaC app 2.14.0. For help"
    )


async def test_license(hass: HomeAssistant, entry: MockConfigEntry, ebac: FakeEbac) -> None:
    assert (await say(hass, INTENT_LICENSE)).startswith(
        "No license was recorded for King James Version (AV)"
    )
    ebac.licenses["AV"] = {"license": "Public domain", "agreed": "2026-11-01"}
    assert await say(hass, INTENT_LICENSE) == (
        "King James Version (AV): its license is Public domain. Agreed to on 2026-11-01."
    )


# ---- the language group and source


@pytest.mark.parametrize(
    "intent_type", [INTENT_LIST_LANGUAGES, INTENT_LIST_AVAILABLE, INTENT_ADD, INTENT_USE_LANGUAGE]
)
async def test_adding_not_allowed(
    hass: HomeAssistant, ebac: FakeEbac, intent_type: str
) -> None:
    await setup_ebac(hass, **CHANGE_ONLY)
    slots = {"name": "LITV"} if intent_type == INTENT_ADD else {}
    if intent_type == INTENT_USE_LANGUAGE:
        slots = {"language": "Spanish"}
    assert (await say(hass, intent_type, **slots)).startswith(
        "Adding translations by voice isn't allowed."
    )
    # and the app's list wasn't even asked for
    assert not [r for r in ebac.requests if r[0].startswith("admin/")]


async def test_list_languages(hass: HomeAssistant, ebac: FakeEbac) -> None:
    await setup_ebac(hass, **ALLOW_ALL)
    assert await say(hass, INTENT_LIST_LANGUAGES) == (
        "3 languages in scrollmapper's bible databases, with how many translations each; "
        "now adding in English: 1, English, 3; 2, Spanish, 1; 3, Ancient Greek, 1."
    )


async def test_list_paging(hass: HomeAssistant, ebac: FakeEbac) -> None:
    await setup_ebac(hass, **ALLOW_ALL)
    assert await say(hass, INTENT_MORE_LIST) == (
        'Ask for a list first, such as "which languages are there?".'
    )
    with patch("custom_components.ebac.intents.ITEMS_PER_LIST", 2):
        assert (await say(hass, INTENT_LIST_LANGUAGES)).endswith(
            "1, English, 3; 2, Spanish, 1. Say more languages (2 of 3)."
        )
        assert await say(hass, INTENT_MORE_LIST) == "3, Ancient Greek, 1."
        assert await say(hass, INTENT_MORE_LIST) == "That's all 3."
        assert await say(hass, INTENT_EARLIER_LIST) == (
            "1, English, 3; 2, Spanish, 1. Say more languages (2 of 3)."
        )


async def test_list_available(hass: HomeAssistant, ebac: FakeEbac) -> None:
    await setup_ebac(hass, **ALLOW_ALL)
    assert await say(hass, INTENT_LIST_AVAILABLE) == (
        "3 in English from scrollmapper's bible databases: 1, LITV: Literal Translation "
        "of the Holy Bible; 2, ASV: American Standard Version; 3, KJVA: King James "
        "Version with Apocrypha, added."
    )
    assert await say(hass, INTENT_LIST_AVAILABLE, language="Español") == (
        "1 in Spanish from scrollmapper's bible databases: 1, RVG: Reina Valera Gómez."
    )
    assert await say(hass, INTENT_LIST_AVAILABLE, language="Klingon") == (
        'Which language is "Klingon"? Say "which languages are there?" to hear them.'
    )


async def test_list_available_by_ebook(hass: HomeAssistant, ebac: FakeEbac) -> None:
    await setup_ebac(hass, **ALLOW_ALL, **{CONF_SOURCE: "gutenberg"})
    assert await say(hass, INTENT_LIST_AVAILABLE) == (
        "1 in English from Project Gutenberg: 1, WEB-PG: World English Bible, ebook 8294."
    )


async def test_catalog_kept_a_while(hass: HomeAssistant, ebac: FakeEbac) -> None:
    """The app downloads its list for each catalog: asked once for a few
    minutes, not at each question."""
    await setup_ebac(hass, **ALLOW_ALL)
    await say(hass, INTENT_LIST_LANGUAGES)
    await say(hass, INTENT_LIST_AVAILABLE)
    assert len([r for r in ebac.requests if r[0] == "admin/catalog"]) == 1


async def test_use_language(hass: HomeAssistant, ebac: FakeEbac) -> None:
    entry = await setup_ebac(hass, **ALLOW_ALL)
    assert await say(hass, INTENT_USE_LANGUAGE, language="Spanish") == (
        "Translations in Spanish from now on: 1 translation from scrollmapper's bible "
        'databases. Say "what translations are there?" to hear them.'
    )
    await hass.async_block_till_done()
    assert entry.options[CONF_LANGUAGE] == "es"
    assert await say(hass, INTENT_USE_LANGUAGE, language="es") == (
        "Already adding translations in Spanish."
    )


@pytest.mark.parametrize(
    ("said", "source"),
    [
        ("Gutenberg", "gutenberg"),
        ("Project Gutenberg", "gutenberg"),
        ("Thiago Bodruk", "thiagobodruk"),
        ("SM", "scrollmapper"),
        # heard nearly right
        ("Thiago Bodruck", "thiagobodruk"),
        ("Gutenburg", "gutenberg"),
    ],
)
async def test_use_source(hass: HomeAssistant, ebac: FakeEbac, said: str, source: str) -> None:
    entry = await setup_ebac(hass, **ALLOW_ALL, **{CONF_SOURCE: "thiagobodruk"
                                                 if source == "scrollmapper" else "scrollmapper"})
    speech = await say(hass, INTENT_USE_LANGUAGE, language=said)
    assert "from now on" in speech, speech
    await hass.async_block_till_done()
    assert entry.options[CONF_SOURCE] == source


async def test_use_source_none_in_the_language(hass: HomeAssistant, ebac: FakeEbac) -> None:
    await setup_ebac(hass, **ALLOW_ALL, **{CONF_LANGUAGE: "es"})
    speech = await say(hass, INTENT_USE_LANGUAGE, language="Gutenberg")
    assert speech.startswith("Translations from Project Gutenberg from now on; it has none in")
    assert speech.endswith('It has some in English: say "use English translations", for one.')


async def test_use_translation_by_name(hass: HomeAssistant, ebac: FakeEbac) -> None:
    """"Use translation KJVA": a translation added, read from (as "change
    translation to KJVA"), when it isn't a language or source."""
    entry = await setup_ebac(hass, **CHANGE_ONLY)
    assert await say(hass, INTENT_USE_LANGUAGE, language="KJVA") == (
        "Now reading from King James Version with Apocrypha (KJVA)."
    )
    await hass.async_block_till_done()
    assert entry.options[CONF_TRANSLATION] == "KJVA"


async def test_use_unknown(hass: HomeAssistant, ebac: FakeEbac) -> None:
    await setup_ebac(hass, **ALLOW_ALL)
    assert (await say(hass, INTENT_USE_LANGUAGE, language="Klingon")).startswith(
        'No language or source called "Klingon".'
    )


# ---- adding and removing


@pytest.fixture
def watch_add():
    """Adding's watch (adding.py, tested there): not left running here."""
    with patch("custom_components.ebac.adding.watch_add", new=AsyncMock()) as watch:
        yield watch


async def test_add(hass: HomeAssistant, ebac: FakeEbac, watch_add: AsyncMock) -> None:
    await setup_ebac(hass, **ALLOW_ALL)
    assert await say(hass, INTENT_ADD, name="LITV") == (
        "Literal Translation of the Holy Bible (LITV). Its license: Copyright Jay P. "
        "Green, used by permission. The details are on CrossWire's page for it. "
        "Say yes or no: do you agree to its license?"
    )
    assert "LITV" not in ebac.adds  # (not before the yes)

    assert await say(hass, INTENT_YES) == (
        "Adding Literal Translation of the Holy Bible (LITV). It takes a minute or two; "
        "you'll be told when it's done."
    )
    assert ebac.adds["LITV"]["agreed"] == "by voice, from Assist"
    await hass.async_block_till_done()
    watch_add.assert_called_once()
    assert watch_add.call_args.args[1:3] == ("LITV", "Literal Translation of the Holy Bible")

    # the question is answered: another yes is to nothing
    assert await say(hass, INTENT_YES) == "There's no question waiting for a yes."


async def test_add_no(hass: HomeAssistant, ebac: FakeEbac, watch_add: AsyncMock) -> None:
    await setup_ebac(hass, **ALLOW_ALL)
    await say(hass, INTENT_ADD, name="LITV")
    assert await say(hass, INTENT_NO) == (
        "All right: Literal Translation of the Holy Bible (LITV) isn't added."
    )
    assert await say(hass, INTENT_YES) == "There's no question waiting for a yes."
    assert not ebac.adds


async def test_yes_too_late(hass: HomeAssistant, ebac: FakeEbac, watch_add: AsyncMock) -> None:
    entry = await setup_ebac(hass, **ALLOW_ALL)
    await say(hass, INTENT_ADD, name="LITV")
    entry.runtime_data.pending["device_id:kitchen"]["until"] = time.monotonic() - 1
    assert await say(hass, INTENT_YES) == "There's no question waiting for a yes."
    assert not ebac.adds


async def test_yes_on_another_device(
    hass: HomeAssistant, ebac: FakeEbac, watch_add: AsyncMock
) -> None:
    """Only the device asked on answers the question."""
    await setup_ebac(hass, **ALLOW_ALL)
    await say(hass, INTENT_ADD, name="LITV", device="kitchen")
    assert await say(hass, INTENT_YES, device="bedroom") == (
        "There's no question waiting for a yes."
    )
    assert not ebac.adds


async def test_add_from_another_language(hass: HomeAssistant, ebac: FakeEbac) -> None:
    await setup_ebac(hass, **ALLOW_ALL)
    assert await say(hass, INTENT_ADD, name="RVG") == (
        'No translation in English from scrollmapper\'s bible databases is called "RVG". '
        'There is one in Spanish: say "use Spanish translations" first.'
    )


async def test_add_same_version_again(hass: HomeAssistant, ebac: FakeEbac) -> None:
    await setup_ebac(hass, **ALLOW_ALL)
    assert (await say(hass, INTENT_ADD, name="KJVA")).startswith(
        "You already have this version of King James Version with Apocrypha (KJVA), "
        "downloaded 2026-10-01."
    )


async def test_add_without_source_suffix(
    hass: HomeAssistant, ebac: FakeEbac, watch_add: AsyncMock
) -> None:
    """"NIV" is NIV-TB, in thiagobodruk's source."""
    await setup_ebac(hass, **ALLOW_ALL, **{CONF_SOURCE: "thiagobodruk"})
    assert (await say(hass, INTENT_ADD, name="NIV")).startswith(
        "New International Version (NIV-TB). Its license: Copyright Biblica. "
        "The details are on the source's page about its licenses."
    )


@pytest.mark.parametrize("said", ["WEB", "8294"])
async def test_add_ebook(
    hass: HomeAssistant, ebac: FakeEbac, watch_add: AsyncMock, said: str
) -> None:
    """A Project Gutenberg ebook: by its number or its text's name, asked
    for by number, named (and read from) by WEB-PG."""
    await setup_ebac(hass, **ALLOW_ALL, **{CONF_SOURCE: "gutenberg"})
    assert (await say(hass, INTENT_ADD, name=said)).startswith(
        "World English Bible (WEB-PG, ebook 8294). Its license"
    )
    assert await say(hass, INTENT_YES) == (
        "Adding World English Bible (WEB-PG). It takes a minute or two; you'll be told "
        "when it's done."
    )
    assert "8294" in ebac.adds
    await hass.async_block_till_done()
    assert watch_add.call_args.args[4:] == ("gutenberg", "WEB-PG")


async def test_add_refused_by_the_app(
    hass: HomeAssistant, ebac: FakeEbac, watch_add: AsyncMock
) -> None:
    """Another add under way (HTTP 409): EBaC's reason, said."""
    await setup_ebac(hass, **ALLOW_ALL)
    ebac.adds["ASV"] = {"state": "running", "message": ""}
    await say(hass, INTENT_ADD, name="LITV")
    assert await say(hass, INTENT_YES) == "Another translation is being added."
    watch_add.assert_not_called()


async def test_remove_not_allowed(hass: HomeAssistant, ebac: FakeEbac) -> None:
    await setup_ebac(hass, **{CONF_ALLOW_CHANGE: True, CONF_ALLOW_ADD: True})
    assert (await say(hass, INTENT_REMOVE, name="WLC")).startswith(
        "Removing translations by voice isn't allowed."
    )
    assert "WLC" in ebac.installed


async def test_remove(hass: HomeAssistant, ebac: FakeEbac) -> None:
    entry = await setup_ebac(hass, **ALLOW_ALL)
    ir.async_create_issue(
        hass, DOMAIN, "add_failed_wlc", is_fixable=True,
        severity=ir.IssueSeverity.ERROR, translation_key="add_failed",
    )
    assert await say(hass, INTENT_REMOVE, name="WLC") == (
        "Say yes or no: are you sure you want to remove The Westminster Leningrad Codex (WLC)?"
    )
    assert "WLC" in ebac.installed
    assert await say(hass, INTENT_YES) == "Removed The Westminster Leningrad Codex (WLC)."
    await hass.async_block_till_done()
    assert ebac.installed == ["AV", "KJVA"]
    # a failed add's repair of it: gone with it
    assert ir.async_get(hass).async_get_issue(DOMAIN, "add_failed_wlc") is None
    # still reading from the AV
    assert entry.runtime_data.translation == "AV"


async def test_remove_the_one_in_use(hass: HomeAssistant, ebac: FakeEbac) -> None:
    entry = await setup_ebac(hass, **ALLOW_ALL)
    await say(hass, INTENT_REMOVE, name="AV")
    assert await say(hass, INTENT_YES) == (
        "Removed King James Version (AV). Now reading from The Westminster "
        "Leningrad Codex (WLC)."
    )
    await hass.async_block_till_done()
    assert entry.options[CONF_TRANSLATION] == "WLC"
    assert entry.runtime_data.translation == "WLC"


async def test_remove_no(hass: HomeAssistant, ebac: FakeEbac) -> None:
    await setup_ebac(hass, **ALLOW_ALL)
    await say(hass, INTENT_REMOVE, name="WLC")
    assert await say(hass, INTENT_NO) == (
        "All right: The Westminster Leningrad Codex (WLC) isn't removed."
    )
    assert "WLC" in ebac.installed


async def test_no_without_a_question(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert await say(hass, INTENT_NO) == "There's no question waiting."
