"""EBaC voice: words said another way, on the way to another voice.

A voice can't read some words as they are written: "יהוה", the divine
name with no vowel points, was read as "yo". EBaC's file "said" lists such
words and what to say for them ("יהוה = Adonai"). Assist shows the same
text it speaks, so they can't be changed in the answer: shown, "Adonai"
would claim letters the text doesn't have. So this is a voice of its own,
chosen in an Assist voice setup (Settings > Voice assistants): it puts the
words in place (whole words, compared without the chant marks of the
Hebrew text) and hands the text to the voice set in
EBaC's options (Home Assistant Cloud, Piper), with the language and voice
the voice setup chose, which are that voice's own. Everything else it is
given, it passes on unchanged.

See "Words said another way" in EBaC's readme.architecture.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Mapping
from typing import Any

from homeassistant.components.tts import (
    TextToSpeechEntity,
    TtsAudioType,
    Voice,
    get_engine_instance,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_SPEAK_WITH, DOMAIN

_LOGGER = logging.getLogger(__name__)

ENTITY_ID = "tts.ebac_voice"
# The voice used when EBaC's options name none: the first of these there is
PREFERRED = ("tts.home_assistant_cloud", "tts.piper")


def speak_with(hass: HomeAssistant, options: Mapping[str, Any]) -> str | None:
    """The voice EBaC voice hands its text to: the one in the options, else
    Home Assistant Cloud's or Piper's, else any other there is."""
    chosen = options.get(CONF_SPEAK_WITH)
    if chosen and chosen != ENTITY_ID:
        return chosen
    for engine in PREFERRED:
        if hass.states.get(engine) is not None:
            return engine
    for state in hass.states.async_all("tts"):
        if state.entity_id != ENTITY_ID:
            return state.entity_id
    return None


# A word: letters, numbers, and the marks on Hebrew letters (vowel points,
# chant marks), but not the Hebrew punctuation that joins or ends words
# (maqaf "־", paseq "׀", sof pasuq "׃")
_WORD = re.compile(r"[\w\u0591-\u05BD\u05BF\u05C1\u05C2\u05C4\u05C5\u05C7\u034F]+")
# Left out when words are compared: the chant marks (cantillation) and
# meteg, which the Westminster Leningrad Codex sets in among the letters,
# so that "יְהוָה" is written some 500 ways; and the grapheme joiner it
# uses to keep a mark's place
_IGNORED = re.compile(r"[\u0591-\u05AF\u05BD\u034F]")


def _key(word: str) -> str:
    """A word as compared: without the marks ignored, its marks in one
    order (the same points may be stored in another order)."""
    return unicodedata.normalize("NFC", _IGNORED.sub("", word))


def say_words(text: str, said: list[dict[str, str]]) -> str:
    """The text with each listed word (a whole word, compared without chant
    marks) said the listed way."""
    table = {
        _key(item["word"]): item["say"]
        for item in said
        if item.get("word") and item.get("say")
    }
    if not table:
        return text
    return _WORD.sub(lambda m: table.get(_key(m.group()), m.group()), text)


async def async_setup_entry(
    hass: HomeAssistant, entry: Any, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """EBaC voice."""
    async_add_entities([EbacVoice(hass, entry)])


class EbacVoice(TextToSpeechEntity):
    """Another voice, with EBaC's words said another way."""

    _attr_has_entity_name = False
    _attr_name = "EBaC voice"
    _attr_icon = "mdi:book-open-variant"

    def __init__(self, hass: HomeAssistant, entry: Any) -> None:
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_voice"
        self.entity_id = ENTITY_ID

    def _engine(self) -> tuple[str | None, Any]:
        """The voice handed to, and its engine (None if not there yet)."""
        engine = speak_with(self.hass, self._entry.options)
        if engine is None:
            return None, None
        return engine, get_engine_instance(self.hass, engine)

    @property
    def available(self) -> bool:
        return self._engine()[1] is not None

    @property
    def supported_languages(self) -> list[str]:  # type: ignore[override]
        instance = self._engine()[1]
        return list(instance.supported_languages or []) if instance else ["en-US"]

    @property
    def default_language(self) -> str:  # type: ignore[override]
        instance = self._engine()[1]
        return instance.default_language if instance else "en-US"

    @property
    def supported_options(self) -> list[str] | None:  # type: ignore[override]
        instance = self._engine()[1]
        return list(instance.supported_options or []) if instance else None

    @property
    def default_options(self) -> Mapping[str, Any] | None:  # type: ignore[override]
        instance = self._engine()[1]
        return instance.default_options if instance else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"speaks_with": self._engine()[0]}

    @callback
    def async_get_supported_voices(self, language: str) -> list[Voice] | None:
        instance = self._engine()[1]
        if instance is None or not hasattr(instance, "async_get_supported_voices"):
            return None
        return instance.async_get_supported_voices(language)

    async def async_get_tts_audio(
        self, message: str, language: str, options: dict[str, Any]
    ) -> TtsAudioType:
        """The other voice's audio of the message, with the words in place."""
        instance = self._engine()[1]
        if instance is None:
            raise HomeAssistantError("EBaC voice: the voice it speaks with isn't there")
        data = self.hass.data.get(DOMAIN)
        said = data.said if data is not None else []
        spoken = say_words(message, said)
        if spoken != message:
            _LOGGER.debug("EBaC voice: %r said as %r", message, spoken)
        # The whole recording, from the other voice itself, as Home Assistant
        # asks a voice that doesn't stream: its streamed audio (a WAV
        # header, then the sound as it comes), handed on whole, couldn't be
        # played ("# channels not specified"). The options were checked
        # against that voice's already (they are its own: above), with its
        # defaults (Home Assistant Cloud's needs its audio_output).
        options = {**(instance.default_options or {}), **options}
        return await instance.async_internal_get_tts_audio(spoken, language, options)
