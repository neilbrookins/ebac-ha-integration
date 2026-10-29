"""The intents that EBaC's sentences name (see sentences.py), and their handlers.

Each answer is spoken by Assist: the verses' "spoken" text from ebac-api
("John chapter 3, verse 16. For God so loved the world, ..."). The place
(the verses last read) is kept for each voice device, so that "next
verse" on the kitchen speaker goes on from what the kitchen heard.
"""

from __future__ import annotations

import re
import time
import unicodedata
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import intent
from homeassistant.helpers import issue_registry as ir

from . import adding
from .api import EbacError
from .const import (
    CONF_LANGUAGE,
    CONFIRM_SECONDS,
    ITEMS_PER_LIST,
    INTENT_USE_LANGUAGE,
    INTENT_LIST_LANGUAGES,
    INTENT_LIST_AVAILABLE,
    INTENT_LIST_ADDED,
    INTENT_MORE_LIST,
    INTENT_EARLIER_LIST,
    INTENT_ADD,
    INTENT_REMOVE,
    INTENT_YES,
    INTENT_NO,
    INTENT_NEXT_CHAPTER,
    INTENT_PREVIOUS_CHAPTER,
    INTENT_START_CHAPTER,
    INTENT_READ_BACK,
    INTENT_NEXT_BOOK,
    INTENT_PREVIOUS_BOOK,
    INTENT_START_BOOK,
    INTENT_VERSION,
    INTENT_LICENSE,
    DOMAIN,
    INTENT_NEXT,
    INTENT_PREVIOUS,
    INTENT_READ,
    INTENT_READ_ON,
    INTENT_REPEAT,
    INTENT_SEARCH,
    INTENT_RESULT,
    INTENT_NEXT_RESULT,
    INTENT_PREVIOUS_RESULT,
    INTENT_MORE_RESULTS,
    INTENT_EARLIER_RESULTS,
    INTENT_BACK_TO_RESULTS,
    RESULTS_PER_LIST,
    INTENT_TRANSLATION,
    INTENT_WHICH_TRANSLATION,
    CONF_TRANSLATION,
)

if TYPE_CHECKING:
    from . import EbacData

NO_PLACE = "Say a verse first, such as John 3:16."
NOT_SET_UP = "EBaC isn't set up."


def not_allowed(what: str) -> str:
    """The answer when a checkbox is off."""
    return (
        f"{what} by voice isn't allowed. It can be allowed under Configure, "
        "in the EBaC integration's settings."
    )


def place_key(intent_obj: intent.Intent) -> str:
    """Whose place: the voice device's (a speaker, a phone), else the
    user's, else everyone's."""
    for name in ("satellite_id", "device_id"):
        value = getattr(intent_obj, name, None)
        if value:
            return f"{name}:{value}"
    context = intent_obj.context
    if context is not None and context.user_id:
        return f"user:{context.user_id}"
    return "default"


def number(slots: dict[str, Any], name: str) -> int | None:
    """A number slot's value, as a whole number ("3" or 3.0 is 3)."""
    if name not in slots:
        return None
    try:
        return int(float(slots[name]["value"]))
    except (TypeError, ValueError):
        return None


class EbacHandler(intent.IntentHandler):
    """What every EBaC intent does: ask ebac-api, speak the verses, and
    keep the place."""

    description = ""

    def __init__(self, intent_type: str) -> None:
        self.intent_type = intent_type

    async def async_handle(self, intent_obj: intent.Intent) -> intent.IntentResponse:
        response = intent_obj.create_response()
        data: EbacData | None = intent_obj.hass.data.get(DOMAIN)
        if data is None:
            response.async_set_speech(NOT_SET_UP)
            return response
        key = place_key(intent_obj)
        try:
            speech = await self.answer(intent_obj, data, key)
        except EbacError as err:
            speech = str(err)
            if not speech.endswith((".", "?", "!")):
                speech += "."
        response.async_set_speech(speech)
        return response

    async def answer(self, intent_obj: intent.Intent, data: EbacData, key: str) -> str:
        """What to say."""
        raise NotImplementedError

    @staticmethod
    def speak(data: EbacData, key: str, answer: dict[str, Any]) -> str:
        """The verses of an answer, spoken; and they become the place."""
        verses = answer.get("verses") or []
        if not verses:
            return "There is no verse there."
        data.places.set(
            key,
            {
                "translation": answer.get("translation"),
                "ref": verses[0]["ref"],
                "last_ref": verses[-1]["ref"],
                "first": verses[0]["svn"],
                "last": verses[-1]["svn"],
                "count": len(verses),
                # (for "next chapter": where the last verse read is)
                "book": verses[-1].get("book"),
                "chapter": verses[-1].get("chapter"),
            },
        )
        return " ".join(verse["spoken"] for verse in verses)

    @staticmethod
    async def place(data: EbacData, key: str) -> dict | None:
        """The place, in the translation in use. After the translation is
        changed, the same references, looked up in the new one: verses are
        numbered differently (KJVA has the Apocrypha), so not by SVN."""
        place = data.places.get(key)
        if place is None:
            return None
        if not data.translation or place.get("translation") == data.translation:
            return place
        if "last_ref" not in place:
            return None  # (kept before references were)
        first = await data.api.verse(data.translation, place["ref"], 1)
        last = await data.api.verse(data.translation, place["last_ref"], 1)
        return {
            **place,
            "translation": data.translation,
            "first": first["verses"][0]["svn"],
            "last": last["verses"][0]["svn"],
        }


class ReadHandler(EbacHandler):
    """ "John 3:16", "Psalm one hundred nineteen verse one", "read Genesis"."""

    slot_schema = {
        vol.Required("book"): cv.string,
        vol.Optional("chapter"): vol.Any(int, float, cv.string),
        vol.Optional("verse"): vol.Any(int, float, cv.string),
        vol.Optional("to"): vol.Any(int, float, cv.string),
    }

    async def answer(self, intent_obj, data, key):
        slots = self.async_validate_slots(intent_obj.slots)
        book = slots["book"]["value"]
        if data.books and book not in data.books:
            # (a book of another translation installed, as John is to the
            # Hebrew Bible)
            the = "" if data.title.lower().startswith("the ") else "The "
            return f"{the}{data.title} has no {book}."
        chapter, verse, to = (number(slots, n) for n in ("chapter", "verse", "to"))
        # The reference as text, for ebac-api to read ("Jude 3 to 5" is
        # Jude 1:3-5: its rules are in one place, EBaC's parser).
        ref = book
        if chapter:
            ref += f" {chapter}"
        if verse:
            ref += f":{verse}"
        if to:
            ref += f" to {to}"
        # A chapter or book alone: its first verses, as many as "read on"
        count = None if (to or verse) else data.read_on
        return self.speak(data, key, await data.api.verse(data.translation, ref, count))


class NextHandler(EbacHandler):
    """ "Next verse"."""

    async def answer(self, intent_obj, data, key):
        if (place := await self.place(data, key)) is None:
            return NO_PLACE
        return self.speak(
            data, key, await data.api.next(data.translation, place["last"])
        )


class PreviousHandler(EbacHandler):
    """ "Previous verse"."""

    async def answer(self, intent_obj, data, key):
        if (place := await self.place(data, key)) is None:
            return NO_PLACE
        return self.speak(
            data, key, await data.api.previous(data.translation, place["first"])
        )


class RepeatHandler(EbacHandler):
    """ "Read that again"."""

    async def answer(self, intent_obj, data, key):
        if (place := await self.place(data, key)) is None:
            return NO_PLACE
        return self.speak(
            data,
            key,
            await data.api.verse(data.translation, place["ref"], place["count"]),
        )


class ReadOnHandler(EbacHandler):
    """ "Read on": the next few verses (as many as the options say)."""

    async def answer(self, intent_obj, data, key):
        if (place := await self.place(data, key)) is None:
            return NO_PLACE
        return self.speak(
            data,
            key,
            await data.api.next(data.translation, place["last"], data.read_on),
        )


class SearchHandler(EbacHandler):
    """ "Search the Bible for jesus wept": one verse is read; several are
    listed, five at a time (their references), as on EBaC's list screen,
    to choose from ("result two"). See "A search's results" in EBaC's
    readme.architecture."""

    slot_schema = {vol.Required("words"): cv.string}

    async def answer(self, intent_obj, data, key):
        slots = self.async_validate_slots(intent_obj.slots)
        words = " ".join(slots["words"]["value"].split()).strip(" .?!")
        answer = await data.api.search(
            data.translation, words.lower(), RESULTS_PER_LIST
        )
        count = answer.get("count", 0)
        search = {
            "words": words,
            "translation": answer.get("translation"),
            "count": count,
            "at": 0,  # (the result at: none yet)
            "listed": 1,  # (the first of the five last listed)
        }
        data.places.set(search_key(key), search)
        if count == 0:
            return f'No verse has "{words}".'
        if count == 1:
            search["at"] = 1
            data.places.set(search_key(key), search)
            return f'One verse has "{words}": {self.speak(data, key, answer)}'
        return f'{count} verses have "{words}": ' + listing(answer, search)


def search_key(key: str) -> str:
    """Where a device's last search is kept, beside its place."""
    return f"{key}|search"


def listing(answer: dict[str, Any], search: dict) -> str:
    """Results, as their numbers and references: "1, Matthew 26:75; 2,
    Mark 14:72"; and what can be said next."""
    start = answer.get("start", 1)
    refs = [f"{start + i}, {v['ref']}" for i, v in enumerate(answer.get("verses", []))]
    last = start + len(refs) - 1
    text = "; ".join(refs) + "."
    if last < search["count"]:
        text += f" Say a result's number, or more results ({last} of {search['count']})."
    else:
        text += " Say a result's number."
    return text


class ResultsHandler(EbacHandler):
    """What the handlers of a search's results share: the last search, in
    the translation in use (searched again in it, from its first result,
    if the translation was changed since)."""

    async def results(self, data: EbacData, key: str) -> dict | None:
        search = data.places.get(search_key(key))
        if search is None or not search.get("count"):
            return None
        if data.translation and search.get("translation") != data.translation:
            answer = await data.api.search(data.translation, search["words"].lower(), 0)
            search = {
                **search,
                "translation": data.translation,
                "count": answer.get("count", 0),
                "at": 0,
                "listed": 1,
            }
            data.places.set(search_key(key), search)
            if not search["count"]:
                return None
        return search

    async def read_result(self, data: EbacData, key: str, search: dict, n: int) -> str:
        """Result n: read, and it becomes the place (for "next verse")."""
        if n < 1:
            return "That was the first result."
        if n > search["count"]:
            return f"That was the last result: there are {search['count']}."
        answer = await data.api.search(data.translation, search["words"].lower(), 1, n)
        search = {**search, "at": n}
        data.places.set(search_key(key), search)
        return f"Result {n} of {search['count']}. {self.speak(data, key, answer)}"

    async def list_from(self, data: EbacData, key: str, search: dict, start: int) -> str:
        """Five results' references, from result start."""
        answer = await data.api.search(
            data.translation, search["words"].lower(), RESULTS_PER_LIST, start
        )
        data.places.set(search_key(key), {**search, "listed": start})
        return listing(answer, search)


NO_RESULTS = 'Search first, such as "search the Bible for jesus wept".'


class ResultHandler(ResultsHandler):
    """ "Result two", "the second result": that result."""

    slot_schema = {vol.Required("number"): vol.Any(int, float, cv.string)}

    async def answer(self, intent_obj, data, key):
        if (search := await self.results(data, key)) is None:
            return NO_RESULTS
        n = number(self.async_validate_slots(intent_obj.slots), "number") or 0
        return await self.read_result(data, key, search, n)


class NextResultHandler(ResultsHandler):
    """ "Next result": the result after the one at (the first, if none)."""

    async def answer(self, intent_obj, data, key):
        if (search := await self.results(data, key)) is None:
            return NO_RESULTS
        return await self.read_result(data, key, search, search["at"] + 1)


class PreviousResultHandler(ResultsHandler):
    """ "Previous result"."""

    async def answer(self, intent_obj, data, key):
        if (search := await self.results(data, key)) is None:
            return NO_RESULTS
        return await self.read_result(data, key, search, search["at"] - 1)


class MoreResultsHandler(ResultsHandler):
    """ "More results": the next five references."""

    async def answer(self, intent_obj, data, key):
        if (search := await self.results(data, key)) is None:
            return NO_RESULTS
        start = search["listed"] + RESULTS_PER_LIST
        if start > search["count"]:
            return f"That's all {search['count']} results. Say a result's number."
        return await self.list_from(data, key, search, start)


class EarlierResultsHandler(ResultsHandler):
    """ "Earlier results": the five before."""

    async def answer(self, intent_obj, data, key):
        if (search := await self.results(data, key)) is None:
            return NO_RESULTS
        start = max(1, search["listed"] - RESULTS_PER_LIST)
        return await self.list_from(data, key, search, start)


class BackToResultsHandler(ResultsHandler):
    """ "Back to the results": as x on EBaC's screen, the list where it was
    left (the five around the result at), and which result that was."""

    async def answer(self, intent_obj, data, key):
        if (search := await self.results(data, key)) is None:
            return NO_RESULTS
        at = search["at"]
        start = ((at - 1) // RESULTS_PER_LIST) * RESULTS_PER_LIST + 1 if at else 1
        intro = f'{search["count"]} verses have "{search["words"]}"'
        intro += f", and you were at result {at}: " if at else ": "
        return intro + await self.list_from(data, key, search, start)


def words_of(text: str) -> list[str]:
    """The words of text, in small letters, without punctuation or
    accents: a name is matched as said, and speech to text may leave the
    accent off ("Reina Valera Gomez" for Gómez). (Searches, unlike names,
    keep accents exactly.)"""
    plain = "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )
    return re.findall(r"\w+", plain.lower())


def spoken_title(translation: dict[str, str]) -> str:
    """A translation, as said: its title and short name."""
    return f"{translation['title']} ({translation['name']})"


def match_translations(said: str, translations: list[dict]) -> list[dict]:
    """The translations installed that the words said name (see "Changing
    the translation by voice" in EBaC's readme.architecture): the short
    name, ignoring case, spaces and dots ("K J V A"); else those whose
    title has every word said ("King James"), the one whose title is just
    those words, if there is one."""
    letters = "".join(words_of(said))
    by_name = [t for t in translations if t["name"].lower() == letters]
    if by_name:
        return by_name
    said_words = [w for w in words_of(said) if w not in ("the", "translation")]
    if not said_words:
        return []
    found = [
        t
        for t in translations
        if all(w in words_of(t["title"]) for w in said_words)
    ]
    exact = [t for t in found if words_of(t["title"]) == said_words]
    return exact or found


class TranslationHandler(EbacHandler):
    """ "Change translation to KJVA", "switch to the Lexham translation":
    for the whole house (the integration's option)."""

    slot_schema = {vol.Required("name"): cv.string}

    async def answer(self, intent_obj, data, key):
        if not data.allow_change:
            return not_allowed("Changing the translation")
        slots = self.async_validate_slots(intent_obj.slots)
        said = slots["name"]["value"].strip(" .?!")
        translations = await data.api.translations()
        found = match_translations(said, translations)
        if not found:
            names = "; ".join(spoken_title(t) for t in translations)
            return f'No translation installed is called "{said}". Installed: {names}.'
        if len(found) > 1:
            names = "; or ".join(spoken_title(t) for t in found)
            return f"Which one: {names}?"
        chosen = found[0]
        if chosen["name"] == data.translation:
            return f"Already reading from {spoken_title(chosen)}."
        entries = intent_obj.hass.config_entries.async_entries(DOMAIN)
        if not entries:
            return NOT_SET_UP
        entry = entries[0]
        # (EBaC is then set up again, with the new translation's books)
        intent_obj.hass.config_entries.async_update_entry(
            entry, options={**entry.options, CONF_TRANSLATION: chosen["name"]}
        )
        return f"Now reading from {spoken_title(chosen)}."


class WhichTranslationHandler(EbacHandler):
    """ "Which translation is this?": the one in use, and the others."""

    async def answer(self, intent_obj, data, key):
        translations = await data.api.translations()
        current = data.translation or (translations[0]["name"] if translations else "")
        this = [t for t in translations if t["name"] == current]
        others = [t for t in translations if t["name"] != current]
        speech = (
            f"Reading from {spoken_title(this[0])}."
            if this
            else f"Reading from {current}."
        )
        # (with changing not allowed, the others aren't named: their names
        # may be private too, as a diary's)
        if others and data.allow_change:
            speech += " Also installed: " + "; ".join(spoken_title(t) for t in others) + "."
        return speech


# ---- moving through the text: chapters, books, back ----------------------


class MoveHandler(EbacHandler):
    """What "next chapter", "next book" and the like share: where the last
    verse read is (its book, as a number in the translation's books, and
    its chapter), and reading a chapter's first verses."""

    async def where(self, data: EbacData, key: str) -> tuple[int, int] | None:
        place = await self.place(data, key)
        if place is None:
            return None
        book, chapter = place.get("book"), place.get("chapter")
        if (not book or not chapter) and place.get("last_ref"):
            # (kept before the book and chapter were: "Song of Solomon 2:1")
            ref = place["last_ref"]
            book, _, numbers = ref.rpartition(" ")
            try:
                chapter = int(numbers.split(":")[0])
            except ValueError:
                return None
        names = [b["full_name"] for b in data.book_list]
        if book not in names:
            return None
        return names.index(book), int(chapter)

    async def read_chapter(self, data: EbacData, key: str, b: int, chapter: int) -> str:
        """The first verses of a chapter, as "Psalm 23" reads."""
        book = data.book_list[b]["full_name"]
        return self.speak(
            data, key, await data.api.verse(data.translation, f"{book} {chapter}", data.read_on)
        )

    def end(self, data: EbacData) -> str:
        the = "" if data.title.lower().startswith("the ") else "the "
        return f"That's the end of {the}{data.title}."

    def beginning(self, data: EbacData) -> str:
        the = "" if data.title.lower().startswith("the ") else "the "
        return f"That's the beginning of {the}{data.title}."

    async def answer(self, intent_obj, data, key):
        if (at := await self.where(data, key)) is None:
            return NO_PLACE
        return await self.move(data, key, *at)

    async def move(self, data: EbacData, key: str, b: int, chapter: int) -> str:
        raise NotImplementedError


class NextChapterHandler(MoveHandler):
    """ "Next chapter": on into the next book after a book's last."""

    async def move(self, data, key, b, chapter):
        if chapter < data.book_list[b]["chapters"]:
            return await self.read_chapter(data, key, b, chapter + 1)
        if b + 1 < len(data.book_list):
            return await self.read_chapter(data, key, b + 1, 1)
        return self.end(data)


class PreviousChapterHandler(MoveHandler):
    """ "Previous chapter": back into the book before, from a first chapter."""

    async def move(self, data, key, b, chapter):
        if chapter > 1:
            return await self.read_chapter(data, key, b, chapter - 1)
        if b > 0:
            return await self.read_chapter(data, key, b - 1, data.book_list[b - 1]["chapters"])
        return self.beginning(data)


class StartOfChapterHandler(MoveHandler):
    """ "Start of the chapter"."""

    async def move(self, data, key, b, chapter):
        return await self.read_chapter(data, key, b, chapter)


class NextBookHandler(MoveHandler):
    """ "Next book" (f in the app)."""

    async def move(self, data, key, b, chapter):
        if b + 1 < len(data.book_list):
            return await self.read_chapter(data, key, b + 1, 1)
        return self.end(data)


class PreviousBookHandler(MoveHandler):
    """ "Previous book" (b in the app, from a book's start)."""

    async def move(self, data, key, b, chapter):
        if b > 0:
            return await self.read_chapter(data, key, b - 1, 1)
        return self.beginning(data)


class StartOfBookHandler(MoveHandler):
    """ "Start of the book"."""

    async def move(self, data, key, b, chapter):
        return await self.read_chapter(data, key, b, 1)


class ReadBackHandler(EbacHandler):
    """ "Read back": the verses before, as many as "read on" reads."""

    async def answer(self, intent_obj, data, key):
        if (place := await self.place(data, key)) is None:
            return NO_PLACE
        answer = await data.api.previous(data.translation, place["first"], data.read_on)
        if not answer.get("verses"):
            the = "" if data.title.lower().startswith("the ") else "the "
            return f"That's the beginning of {the}{data.title}."
        return self.speak(data, key, answer)


# ---- information --------------------------------------------------------


class VersionHandler(EbacHandler):
    """ "What version of EBaC is this?": as on its Information screen."""

    async def answer(self, intent_obj, data, key):
        info = await data.api.info()
        speech = f"This is EBaC {info.get('release', '')}"
        commit = (info.get("commit") or "").split(",")[0].strip()
        if commit:
            speech += f", built from commit {commit}"
        if info.get("package"):
            speech += f", in the {info['package']}"
        return speech + (
            ". For help, or to report a problem, open an issue on GitHub, in "
            "neilbrookins's repositories: ebac for the program, ebac-ha-app "
            "for the Home Assistant app, and ebac-ha-integration for voice."
        )


class LicenseHandler(EbacHandler):
    """ "What's the license of this translation?": as agreed when it was
    added."""

    async def answer(self, intent_obj, data, key):
        translations = await data.api.translations()
        current = data.translation or (translations[0]["name"] if translations else "")
        this = next((t for t in translations if t["name"] == current), None)
        spoken = spoken_title(this) if this else current
        kept = await data.api.license(current)
        if not kept.get("recorded"):
            return (
                f"No license was recorded for {spoken}: it comes with EBaC, "
                "or was added before EBaC kept licenses."
            )
        speech = f"{spoken}: its license is {kept.get('license', 'not stated')}"
        if kept.get("agreed"):
            speech += f". Agreed to on {kept['agreed']}"
        return speech + "."


# ---- the language group, lists, adding and removing ----------------------


CATALOG_SECONDS = 600  # how long the catalog is kept


async def catalog(data: EbacData) -> dict[str, Any]:
    """ebac-admin's catalog (kept a few minutes: it downloads the list)."""
    if data.catalog and time.monotonic() - data.catalog[0] < CATALOG_SECONDS:
        return data.catalog[1]
    found = await data.api.catalog()
    data.catalog = (time.monotonic(), found)
    return found


def language_name(language: dict[str, Any]) -> str:
    """A language, as said: its English name (else its own, else its code)."""
    return language.get("english") or language.get("own") or language["code"]


def language_of(code: str, languages: list[dict[str, Any]]) -> str:
    """The name of the language with this code."""
    for language in languages:
        if language["code"] == code:
            return language_name(language)
    return code


def match_languages(said: str, languages: list[dict[str, Any]]) -> list[dict]:
    """The languages the words name: the code, the English name or the
    language's own; else those whose names have every word said."""
    said_words = [w for w in words_of(said) if w not in ("the", "language", "translations")]
    if not said_words:
        return []
    joined = "".join(said_words)
    exact = [
        lang
        for lang in languages
        if lang["code"].replace("-", "") == joined
        or words_of(lang.get("english", "")) == said_words
        or words_of(lang.get("own", "")) == said_words
    ]
    if exact:
        return exact
    return [
        lang
        for lang in languages
        if all(w in words_of(f"{lang.get('english', '')} {lang.get('own', '')}") for w in said_words)
    ]


def list_key(key: str) -> str:
    """Where a device's last list (languages, translations) is kept."""
    return f"{key}|list"


def say_list(data: EbacData, key: str, kind: str, items: list[str], start: int, intro: str = "") -> str:
    """Items from start (1 for the first), ITEMS_PER_LIST of them, and what
    can be said next; the list is kept, for "more"."""
    data.places.set(list_key(key), {"kind": kind, "items": items, "start": start})
    shown = items[start - 1 : start - 1 + ITEMS_PER_LIST]
    last = start + len(shown) - 1
    text = intro + "; ".join(f"{start + i}, {item}" for i, item in enumerate(shown)) + "."
    if last < len(items):
        text += f" Say more {kind} ({last} of {len(items)})."
    return text


def set_option(intent_obj: intent.Intent, **changes: Any) -> bool:
    """Change the integration's options (EBaC is then set up again)."""
    entries = intent_obj.hass.config_entries.async_entries(DOMAIN)
    if not entries:
        return False
    entry = entries[0]
    intent_obj.hass.config_entries.async_update_entry(
        entry, options={**entry.options, **changes}
    )
    return True


class UseLanguageHandler(EbacHandler):
    """ "Use Spanish translations", "manipulate translations Spanish": the
    language "add translation" looks in, from now on (the whole house)."""

    slot_schema = {vol.Required("language"): cv.string}

    async def answer(self, intent_obj, data, key):
        if not data.allow_add:
            return not_allowed("Adding translations")
        said = self.async_validate_slots(intent_obj.slots)["language"]["value"].strip(" .?!")
        languages = (await catalog(data))["languages"]
        found = match_languages(said, languages)
        if not found:
            return f'No language called "{said}" has translations. Say "which languages are there?" to hear them.'
        if len(found) > 1:
            return "Which one: " + "; or ".join(language_name(lang) for lang in found) + "?"
        language = found[0]
        if language["code"] == data.language:
            return f"Already adding translations in {language_name(language)}."
        if not set_option(intent_obj, **{CONF_LANGUAGE: language["code"]}):
            return NOT_SET_UP
        count = language.get("count", 0)
        return (
            f"Translations in {language_name(language)} from now on: "
            f"{count} translation{'s' if count != 1 else ''}. "
            'Say "what translations are there?" to hear them.'
        )


class ListLanguagesHandler(EbacHandler):
    """ "Which languages are there?"."""

    async def answer(self, intent_obj, data, key):
        if not data.allow_add:
            return not_allowed("Adding translations")
        languages = (await catalog(data))["languages"]
        items = [f"{language_name(lang)}, {lang.get('count', 0)}" for lang in languages]
        intro = (
            f"{len(languages)} languages, with how many translations each; "
            f"now adding in {language_of(data.language, languages)}: "
        )
        return say_list(data, key, "languages", items, 1, intro)


class ListAvailableHandler(EbacHandler):
    """ "What translations are there?" (in the language group, or the
    language said)."""

    slot_schema = {vol.Optional("language"): cv.string}

    async def answer(self, intent_obj, data, key):
        if not data.allow_add:
            return not_allowed("Adding translations")
        slots = self.async_validate_slots(intent_obj.slots)
        found = await catalog(data)
        code = data.language
        if "language" in slots:
            said = slots["language"]["value"].strip(" .?!")
            matches = match_languages(said, found["languages"])
            if len(matches) != 1:
                return f'Which language is "{said}"? Say "which languages are there?" to hear them.'
            code = matches[0]["code"]
        name = language_of(code, found["languages"])
        translations = [t for t in found["translations"] if t["language"] == code]
        if not translations:
            return f"There are no translations in {name}."
        items = [
            f"{t['name']}: {t['title']}" + (", added" if t.get("added") else "")
            for t in translations
        ]
        return say_list(data, key, "translations", items, 1, f"{len(items)} in {name}: ")


class ListAddedHandler(EbacHandler):
    """ "Which translations are added?"."""

    async def answer(self, intent_obj, data, key):
        translations = await data.api.translations()
        current = data.translation or (translations[0]["name"] if translations else "")
        if not data.allow_change:
            # (the others aren't named: see "which translation is this")
            this = [t for t in translations if t["name"] == current]
            return f"Reading from {spoken_title(this[0]) if this else current}."
        items = [spoken_title(t) for t in translations]
        return say_list(data, key, "translations", items, 1, f"{len(items)} added: ")


class MoreListHandler(EbacHandler):
    """ "More languages", "more translations": the next of the last list."""

    step = 1

    async def answer(self, intent_obj, data, key):
        kept = data.places.get(list_key(key))
        if not kept:
            return 'Ask for a list first, such as "which languages are there?".'
        start = kept["start"] + self.step * ITEMS_PER_LIST
        if start > len(kept["items"]):
            return f"That's all {len(kept['items'])}."
        return say_list(data, key, kept["kind"], kept["items"], max(1, start))


class EarlierListHandler(MoreListHandler):
    """ "Earlier languages": the ones before."""

    step = -1


class AddHandler(EbacHandler):
    """ "Add translation LITV": in the language group; its license is read,
    and "Do you agree?" waits for a yes."""

    slot_schema = {vol.Required("name"): cv.string}

    async def answer(self, intent_obj, data, key):
        if not data.allow_add:
            return not_allowed("Adding translations")
        said = self.async_validate_slots(intent_obj.slots)["name"]["value"].strip(" .?!")
        found = await catalog(data)
        language = language_of(data.language, found["languages"])
        in_group = [t for t in found["translations"] if t["language"] == data.language]
        matches = match_translations(said, in_group)
        if not matches:
            elsewhere = match_translations(said, found["translations"])
            speech = f'No translation in {language} is called "{said}".'
            if len(elsewhere) == 1:
                other = language_of(elsewhere[0]["language"], found["languages"])
                speech += f' There is one in {other}: say "use {other} translations" first.'
            else:
                speech += ' Say "what translations are there?" to hear them.'
            return speech
        if len(matches) > 1:
            return "Which one: " + "; or ".join(spoken_title(t) for t in matches) + "?"
        chosen = matches[0]
        spoken = spoken_title(chosen)
        if chosen.get("added"):
            check = await data.api.check(chosen["name"])
            if check.get("same_version"):
                return (
                    f"You already have this version of {spoken}, downloaded "
                    f"{check.get('downloaded', '')}. To download it again, remove "
                    "it first, then add it."
                )
        terms = await data.api.source_license(chosen["name"])
        data.pending[key] = {
            "action": "add",
            "name": chosen["name"],
            "title": chosen["title"],
            "until": time.monotonic() + CONFIRM_SECONDS,
        }
        return (
            f"{spoken}. Its license: {terms.get('license') or 'not stated'}. "
            "The details are on CrossWire's page for it. "
            "Say yes or no: do you agree to its license?"
        )


class RemoveHandler(EbacHandler):
    """ "Remove translation LITV": "Are you sure?" waits for a yes."""

    slot_schema = {vol.Required("name"): cv.string}

    async def answer(self, intent_obj, data, key):
        if not data.allow_remove:
            return not_allowed("Removing translations")
        said = self.async_validate_slots(intent_obj.slots)["name"]["value"].strip(" .?!")
        translations = await data.api.translations()
        matches = match_translations(said, translations)
        if not matches:
            names = "; ".join(spoken_title(t) for t in translations)
            return f'No translation added is called "{said}". Added: {names}.'
        if len(matches) > 1:
            return "Which one: " + "; or ".join(spoken_title(t) for t in matches) + "?"
        chosen = matches[0]
        data.pending[key] = {
            "action": "remove",
            "name": chosen["name"],
            "title": chosen["title"],
            "until": time.monotonic() + CONFIRM_SECONDS,
        }
        return f"Say yes or no: are you sure you want to remove {spoken_title(chosen)}?"


class YesHandler(EbacHandler):
    """ "Yes": to the question asked last on this device ("Do you agree?",
    "Are you sure?"), if it is still waiting."""

    async def answer(self, intent_obj, data, key):
        pending = data.pending.pop(key, None)
        if pending is None or pending["until"] < time.monotonic():
            return "There's no question waiting for a yes."
        name, title = pending["name"], pending["title"]
        spoken = f"{title} ({name})"
        if pending["action"] == "add":
            if not data.allow_add:
                return not_allowed("Adding translations")
            who = await adding.asker(intent_obj)
            await data.api.add(name, adding.agreed_text(who))
            intent_obj.hass.async_create_background_task(
                adding.watch_add(intent_obj.hass, name, title, who),
                f"EBaC: adding {name}",
            )
            return f"Adding {spoken}. It takes a minute or two; you'll be told when it's done."
        if not data.allow_remove:
            return not_allowed("Removing translations")
        translations = await data.api.translations()
        current = data.translation or (translations[0]["name"] if translations else "")
        await data.api.remove(name)
        # (a repair of a failed add of it: done with, as it's gone)
        ir.async_delete_issue(intent_obj.hass, DOMAIN, adding.issue_id(name))
        if name != current:
            # (set up again: the books of the translations left)
            entries = intent_obj.hass.config_entries.async_entries(DOMAIN)
            if entries:
                intent_obj.hass.async_create_task(
                    intent_obj.hass.config_entries.async_reload(entries[0].entry_id)
                )
            return f"Removed {spoken}."
        # The one in use: the app's default instead (the first of trans now)
        left = await data.api.translations()
        if not left:
            return f"Removed {spoken}."
        set_option(intent_obj, **{CONF_TRANSLATION: left[0]["name"]})
        return f"Removed {spoken}. Now reading from {spoken_title(left[0])}."


class NoHandler(EbacHandler):
    """ "No": the question waiting is answered no, and nothing is done."""

    async def answer(self, intent_obj, data, key):
        pending = data.pending.pop(key, None)
        if pending is None or pending["until"] < time.monotonic():
            return "There's no question waiting."
        spoken = f"{pending['title']} ({pending['name']})"
        if pending["action"] == "add":
            return f"All right: {spoken} isn't added."
        return f"All right: {spoken} isn't removed."


HANDLERS = {
    INTENT_READ: ReadHandler,
    INTENT_NEXT: NextHandler,
    INTENT_PREVIOUS: PreviousHandler,
    INTENT_REPEAT: RepeatHandler,
    INTENT_READ_ON: ReadOnHandler,
    INTENT_SEARCH: SearchHandler,
    INTENT_RESULT: ResultHandler,
    INTENT_NEXT_RESULT: NextResultHandler,
    INTENT_PREVIOUS_RESULT: PreviousResultHandler,
    INTENT_MORE_RESULTS: MoreResultsHandler,
    INTENT_EARLIER_RESULTS: EarlierResultsHandler,
    INTENT_BACK_TO_RESULTS: BackToResultsHandler,
    INTENT_TRANSLATION: TranslationHandler,
    INTENT_WHICH_TRANSLATION: WhichTranslationHandler,
    INTENT_USE_LANGUAGE: UseLanguageHandler,
    INTENT_LIST_LANGUAGES: ListLanguagesHandler,
    INTENT_LIST_AVAILABLE: ListAvailableHandler,
    INTENT_LIST_ADDED: ListAddedHandler,
    INTENT_MORE_LIST: MoreListHandler,
    INTENT_EARLIER_LIST: EarlierListHandler,
    INTENT_ADD: AddHandler,
    INTENT_REMOVE: RemoveHandler,
    INTENT_YES: YesHandler,
    INTENT_NO: NoHandler,
    INTENT_NEXT_CHAPTER: NextChapterHandler,
    INTENT_PREVIOUS_CHAPTER: PreviousChapterHandler,
    INTENT_START_CHAPTER: StartOfChapterHandler,
    INTENT_READ_BACK: ReadBackHandler,
    INTENT_NEXT_BOOK: NextBookHandler,
    INTENT_PREVIOUS_BOOK: PreviousBookHandler,
    INTENT_START_BOOK: StartOfBookHandler,
    INTENT_VERSION: VersionHandler,
    INTENT_LICENSE: LicenseHandler,
}


@callback
def async_register(hass: HomeAssistant) -> None:
    """Register EBaC's intents (again, if they already are)."""
    for intent_type, handler in HANDLERS.items():
        intent.async_register(hass, handler(intent_type))


@callback
def async_remove(hass: HomeAssistant) -> None:
    """Remove EBaC's intents."""
    for intent_type in HANDLERS:
        intent.async_remove(hass, intent_type)
