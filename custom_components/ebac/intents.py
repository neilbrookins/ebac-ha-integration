"""The intents that EBaC's sentences name (see sentences.py), and their handlers.

Each answer is spoken by Assist: the verses' "spoken" text from ebac-api
("John chapter 3, verse 16. For God so loved the world, ..."). The place
(the verses last read) is kept for each voice device, so that "next
verse" on the kitchen speaker goes on from what the kitchen heard.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import intent

from .api import EbacError
from .const import (
    DOMAIN,
    INTENT_NEXT,
    INTENT_PREVIOUS,
    INTENT_READ,
    INTENT_READ_ON,
    INTENT_REPEAT,
    INTENT_SEARCH,
    INTENT_TRANSLATION,
    INTENT_WHICH_TRANSLATION,
    CONF_TRANSLATION,
    SEARCH_READ,
)

if TYPE_CHECKING:
    from . import EbacData

NO_PLACE = "Say a verse first, such as John 3:16."
NOT_SET_UP = "EBaC isn't set up."


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
    """ "Search the Bible for faith hope charity": how many verses, and the
    first (which becomes the place, so "next verse" goes on from it)."""

    slot_schema = {vol.Required("words"): cv.string}

    async def answer(self, intent_obj, data, key):
        slots = self.async_validate_slots(intent_obj.slots)
        words = " ".join(slots["words"]["value"].split()).strip(" .?!")
        answer = await data.api.search(data.translation, words.lower(), SEARCH_READ)
        count = answer.get("count", 0)
        if count == 0:
            return f'No verse has "{words}".'
        verses = self.speak(data, key, answer)
        if count == 1:
            return f'One verse has "{words}": {verses}'
        return f'{count} verses have "{words}". The first: {verses}'


def words_of(text: str) -> list[str]:
    """The words of text, in small letters, without punctuation."""
    return re.findall(r"\w+", text.lower())


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
        if others:
            speech += " Also installed: " + "; ".join(spoken_title(t) for t in others) + "."
        return speech


HANDLERS = {
    INTENT_READ: ReadHandler,
    INTENT_NEXT: NextHandler,
    INTENT_PREVIOUS: PreviousHandler,
    INTENT_REPEAT: RepeatHandler,
    INTENT_READ_ON: ReadOnHandler,
    INTENT_SEARCH: SearchHandler,
    INTENT_TRANSLATION: TranslationHandler,
    INTENT_WHICH_TRANSLATION: WhichTranslationHandler,
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
