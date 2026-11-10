"""Names as speech to text writes them: translations, sources, languages
(intents.py); and the lists of the sentence file (sentences.py)."""

from __future__ import annotations

import pytest

from custom_components.ebac import sentences
from custom_components.ebac.intents import (
    match_languages,
    match_translations,
    source_named,
    words_of,
)

from .fake_ebac import CATALOGS

INSTALLED = [
    {"name": "AV", "title": "King James Version"},
    {"name": "KJVA", "title": "King James Version with Apocrypha"},
    {"name": "WLC", "title": "The Westminster Leningrad Codex"},
    {"name": "NIV-TB", "title": "New International Version"},
    {"name": "LITV-SM", "title": "Literal Translation of the Holy Bible"},
    {"name": "8294", "names": "WEB-PG", "title": "World English Bible"},
]
LANGUAGES = [
    *CATALOGS["scrollmapper"]["languages"],
    {"code": "pt-br", "english": "Brazilian Portuguese", "own": "Português", "count": 1},
    {"code": "pt", "english": "Portuguese", "own": "Português", "count": 1},
]


def names(found: list[dict]) -> list[str]:
    return [t["name"] for t in found]


@pytest.mark.parametrize(
    ("said", "expected"),
    [
        ("KJVA", ["KJVA"]),
        ("k j v a", ["KJVA"]),
        ("K.J.V.A.", ["KJVA"]),
        ("NIV-TB", ["NIV-TB"]),
        ("NIV", ["NIV-TB"]),  # (its source's ending implied)
        ("LITV", ["LITV-SM"]),  # (scrollmapper's too)
        ("WEB", ["8294"]),
        ("8294", ["8294"]),
        ("Westminster", ["WLC"]),
        ("the King James Version", ["AV"]),  # (the title that is just that)
        ("King James", ["AV", "KJVA"]),  # (which one?)
        ("king james apocrypha", ["KJVA"]),
        ("Klingon", []),
        ("the translation", []),
    ],
)
def test_match_translations(said: str, expected: list[str]) -> None:
    assert names(match_translations(said, INSTALLED)) == expected


def test_accents_left_off() -> None:
    """Speech to text may leave an accent off a name."""
    found = match_translations("Reina Valera Gomez", CATALOGS["scrollmapper"]["translations"])
    assert names(found) == ["RVG-SM"]
    assert words_of("Reina-Valera Gómez!") == ["reina", "valera", "gomez"]


@pytest.mark.parametrize(
    ("said", "expected"),
    [
        ("Spanish", ["es"]),
        ("español", ["es"]),
        ("Espanol", ["es"]),
        ("es", ["es"]),
        ("ancient greek", ["grc"]),
        ("Greek", ["grc"]),
        ("the Spanish language", ["es"]),
        ("ptbr", ["pt-br"]),
        ("Portuguese", ["pt"]),  # (exactly, over Brazilian Portuguese)
        ("Klingon", []),
    ],
)
def test_match_languages(said: str, expected: list[str]) -> None:
    assert [lang["code"] for lang in match_languages(said, LANGUAGES)] == expected


@pytest.mark.parametrize(
    ("said", "close", "expected"),
    [
        ("Gutenberg", False, "gutenberg"),
        ("project gutenberg", False, "gutenberg"),
        ("P G", False, "gutenberg"),
        ("thiago bodruk", False, "thiagobodruk"),
        ("TB", False, "thiagobodruk"),
        ("scroll mapper", False, "scrollmapper"),
        ("crosswire", False, "scrollmapper"),
        ("SM", False, "scrollmapper"),
        # heard nearly right: only when asked for (after languages)
        ("Thiago Bodruck", False, None),
        ("Thiago Bodruck", True, "thiagobodruk"),
        ("theago bodruck", True, "thiagobodruk"),
        ("Gutenburg", True, "gutenberg"),
        ("scroll map her", True, "scrollmapper"),
        # not sources, however close it looks
        ("Spanish", True, None),
        ("English", True, None),
        ("Portuguese", True, None),
        ("KJV", True, None),
    ],
)
def test_source_named(said: str, close: bool, expected: str | None) -> None:
    assert source_named(said, close=close) == expected


def test_no_language_name_is_mistaken_for_a_source() -> None:
    """None of the languages' names comes near a source's (CLOSE_ENOUGH)."""
    for language in LANGUAGES:
        for name in (language["english"], language["own"]):
            assert source_named(name, close=True) is None, name


# ---- the sentence file's lists


def test_book_forms() -> None:
    """Each spoken form, also without or with a final "s"."""
    assert sentences.book_forms({"full_name": "Psalms", "spoken": ["Psalms"]}) == [
        "Psalms", "Psalm",
    ]
    assert sentences.book_forms({"full_name": "Revelation", "spoken": ["Revelation"]}) == [
        "Revelation", "Revelations",
    ]
    # no spoken forms: the full name; and no form twice, whatever the case
    assert sentences.book_forms({"full_name": "John", "spoken": ["John", "john"]}) == [
        "John", "Johns",
    ]


def test_build() -> None:
    data = sentences.build(
        [
            {"full_name": "1 Samuel", "spoken": ["1 Samuel", "First Samuel"]},
            {"full_name": "John"},
        ],
        [
            {"number": 1, "spoken": ["1", "one", "i"]},
            {"number": 119, "spoken": ["119", "one hundred nineteen", "a hundred and nineteen"]},
        ],
    )
    assert data["language"] == "en"
    lists = data["lists"]
    assert {"in": "First Samuel", "out": "1 Samuel"} in lists["ebac_book"]["values"]
    assert {"in": "John", "out": "John"} in lists["ebac_book"]["values"]
    # digits from a range (to the most there is); words from the list
    assert lists["ebac_digits"] == {"range": {"from": 1, "to": 119}}
    number_ins = [v["in"] for v in lists["ebac_number"]["values"]]
    assert "a hundred and nineteen" in number_ins
    assert "119" not in number_ins
    # every intent EBaC handles has sentences
    from custom_components.ebac.intents import HANDLERS

    assert set(data["intents"]) == set(HANDLERS)


def test_ordinals() -> None:
    """"The second result", "the 2nd result", to the twentieth."""
    ordinals = {o["in"]: o["out"] for o in sentences.ORDINALS}
    assert ordinals["first"] == 1
    assert ordinals["twentieth"] == 20
    for n, suffix in ((1, "st"), (2, "nd"), (3, "rd"), (4, "th"), (11, "th"),
                      (12, "th"), (13, "th"), (20, "th")):
        assert ordinals[f"{n}{suffix}"] == n
    assert not {"11st", "12nd", "13rd"} & set(ordinals)
