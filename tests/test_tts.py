"""EBaC voice (tts.py): EBaC's words said another way ("יהוה" as
"Adonai"), then handed to another voice; what Assist shows is unchanged."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant.common import MockConfigEntry

from custom_components.ebac.const import CONF_SPEAK_WITH, CONF_TRANSLATION, INTENT_READ
from custom_components.ebac.tts import ENTITY_ID, EbacVoice, say_words, speak_with

from .conftest import say, setup_ebac
from .fake_ebac import POINTED, TETRAGRAMMATON, FakeEbac

# As EBaC's file "said" may list the word: bare, and with its vowel points
SAID = [
    {"word": TETRAGRAMMATON, "say": "Adonai"},
    {"word": "יְהוָה", "say": "Adonai"},
]
MAQAF = "־"  # (joins words: "־")
SOF_PASUQ = "׃"  # (ends a verse: "׃")
JOINER = "͏"  # (the grapheme joiner, keeping a mark's place)


@pytest.mark.parametrize(
    ("text", "spoken"),
    [
        (TETRAGRAMMATON, "Adonai"),
        (f"Blessed be {TETRAGRAMMATON}.", "Blessed be Adonai."),
        # the chant mark among the letters is left out when compared
        (POINTED, "Adonai"),
        (f"{POINTED} אֱלֹהִים", "Adonai אֱלֹהִים"),
        ("יְהֽוָה", "Adonai"),  # (meteg)
        (f"יְ{JOINER}הוָ֑ה", "Adonai"),
        # Hebrew punctuation joins or ends words, and stays
        (f"{POINTED}{MAQAF}אֱלֹהִים", f"Adonai{MAQAF}אֱלֹהִים"),
        (f"אֱלֹהִים {POINTED}{SOF_PASUQ}", f"אֱלֹהִים Adonai{SOF_PASUQ}"),
        # whole words only: a longer word is left as it is
        (f"ל{TETRAGRAMMATON}", f"ל{TETRAGRAMMATON}"),
        ("Nothing to change here.", "Nothing to change here."),
    ],
)
def test_say_words(text: str, spoken: str) -> None:
    assert say_words(text, SAID) == spoken


def test_marks_stored_in_another_order() -> None:
    """The same points, stored in another order, are the same word."""
    # bet with dagesh then qamats, and with qamats then dagesh
    said = [{"word": "בָּרָא", "say": "bara"}]
    assert say_words("בָּרָא", said) == "bara"


def test_nothing_to_say_another_way() -> None:
    assert say_words(TETRAGRAMMATON, []) == TETRAGRAMMATON
    # (an entry missing its word or its saying is ignored)
    assert say_words(TETRAGRAMMATON, [{"word": TETRAGRAMMATON, "say": ""}]) == TETRAGRAMMATON


async def test_shown_text_unchanged(hass: HomeAssistant, ebac: FakeEbac) -> None:
    """Assist shows the verse as the source writes it: only the voice says
    it another way."""
    await setup_ebac(hass, **{CONF_TRANSLATION: "WLC"})
    speech = await say(hass, INTENT_READ, book="Genesis", chapter=2, verse=4)
    assert POINTED in speech
    assert "Adonai" not in speech


# ---- the voice handed to


async def test_speak_with(hass: HomeAssistant) -> None:
    assert speak_with(hass, {}) is None
    hass.states.async_set("tts.google", "unknown")
    assert speak_with(hass, {}) == "tts.google"
    hass.states.async_set(ENTITY_ID, "unknown")  # (never itself)
    hass.states.async_set("tts.piper", "unknown")
    assert speak_with(hass, {}) == "tts.piper"
    hass.states.async_set("tts.home_assistant_cloud", "unknown")
    assert speak_with(hass, {}) == "tts.home_assistant_cloud"
    # the one chosen in the options, unless it's EBaC voice itself
    assert speak_with(hass, {CONF_SPEAK_WITH: "tts.google"}) == "tts.google"
    assert speak_with(hass, {CONF_SPEAK_WITH: ENTITY_ID}) == "tts.home_assistant_cloud"


async def test_voice_unavailable_without_another(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.state == "unavailable"


def fake_engine() -> SimpleNamespace:
    return SimpleNamespace(
        supported_languages=["en-US", "en-GB"],
        default_language="en-GB",
        supported_options=["voice", "audio_output"],
        default_options={"audio_output": "mp3", "voice": "Ryan"},
        async_get_supported_voices=lambda language: ["Ryan", "Sonia"],
        async_internal_get_tts_audio=AsyncMock(return_value=("mp3", b"ID3 audio")),
    )


@pytest.fixture
def engine():
    """Another voice (Piper, say), for EBaC voice to hand its text to."""
    engine = fake_engine()
    with patch("custom_components.ebac.tts.get_engine_instance", return_value=engine) as get:
        get.engine = engine
        yield get


async def test_voice(hass: HomeAssistant, entry: MockConfigEntry, engine) -> None:
    entry.runtime_data.said = SAID
    hass.states.async_set("tts.piper", "unknown")
    voice = EbacVoice(hass, entry)
    voice.hass = hass
    assert voice.available
    assert voice.extra_state_attributes == {"speaks_with": "tts.piper"}
    engine.assert_called_with(hass, "tts.piper")
    # its languages and voices are the other voice's own
    assert voice.supported_languages == ["en-US", "en-GB"]
    assert voice.default_language == "en-GB"
    assert voice.supported_options == ["voice", "audio_output"]
    assert voice.async_get_supported_voices("en-GB") == ["Ryan", "Sonia"]

    audio = await voice.async_get_tts_audio(f"{POINTED} אֱלֹהִים", "en-GB", {"voice": "Sonia"})
    assert audio == ("mp3", b"ID3 audio")
    engine.engine.async_internal_get_tts_audio.assert_awaited_once_with(
        # the words said another way; the voice asked for, over its default
        "Adonai אֱלֹהִים", "en-GB", {"audio_output": "mp3", "voice": "Sonia"}
    )


async def test_voice_passes_other_text_unchanged(
    hass: HomeAssistant, entry: MockConfigEntry, engine
) -> None:
    hass.states.async_set("tts.piper", "unknown")
    voice = EbacVoice(hass, entry)
    voice.hass = hass
    await voice.async_get_tts_audio("The kitchen light is on.", "en-US", {})
    assert engine.engine.async_internal_get_tts_audio.await_args.args[0] == (
        "The kitchen light is on."
    )


async def test_voice_without_another(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    voice = EbacVoice(hass, entry)
    voice.hass = hass
    assert not voice.available
    assert voice.supported_languages == ["en-US"]
    with pytest.raises(HomeAssistantError, match="isn't there"):
        await voice.async_get_tts_audio("Hello", "en-US", {})
