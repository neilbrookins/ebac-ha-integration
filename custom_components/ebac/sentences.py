"""The sentences Assist matches for EBaC: config/custom_sentences/en/ebac.yaml.

Home Assistant has no supported way for an integration to add sentences
to Assist, but Assist reads the sentence files in config/custom_sentences/
LANGUAGE/ (before its own sentences). So the integration writes one at
setup, and removes it when it is removed.

The lists are made from ebac-api's answers, not written here: the books'
spoken forms (/books: "First Corinthians", "I Corinthians", "1
Corinthians") and the ways each number is said (/numbers: "16",
"sixteen", "a hundred and nineteen", "xvi"). So a sentence matches only a
real book and numbers EBaC reads, and can't take over "turn on the
kitchen light" or "Mark the door closed". The handler builds the text of
the reference ("John 3:16-18") from what matched, and ebac-api reads it,
so its rules ("Jude three" is Jude 1:3) are in one place.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .const import (
    INTENT_NEXT,
    INTENT_PREVIOUS,
    INTENT_READ,
    INTENT_READ_ON,
    INTENT_REPEAT,
    INTENT_SEARCH,
    LANGUAGE,
    SENTENCES_FILE,
)

HEADER = """\
# Written by the EBaC integration (custom_components/ebac), from the books
# and numbers of the translation it reads from. Don't edit this file: it
# is written again when the integration starts or its options change, and
# removed with the integration. Put sentences of your own in a file of
# their own.
"""

# A reference: book, chapter, verse, and the end of a range, in the ways
# speech to text writes them ("John 3:16-18", "John three sixteen",
# "Genesis I colon I", "Psalm 119 verse 1"). "[ ]" lets ":" and "-" join
# the numbers with no space, as "3:16-18" has them.
BOOK = "[read] [the] [book of] {ebac_book:book}"
# A number: digits, from a range list (which takes the whole run of
# digits: "23" as 23, where a list of values would also take "2" from
# it), or the words and Roman numerals of /numbers.
CHAPTER = "({ebac_digits:chapter}|{ebac_number:chapter})"
VERSE = "({ebac_digits:verse}|{ebac_number:verse})"
TO = "({ebac_digits:to}|{ebac_number:to})"
# Between chapter and verse, and before the end of a range. ":" and "-"
# may have no space around them ("3:16-18"); the words must, so that
# "23" isn't taken as 2 and 3.
SEPARATORS = ["[ ]:[ ]", " (colon|verse|verses) ", " "]
RANGES = ["[ ]-[ ]", " (to|through|thru) "]

READ_SENTENCES = [
    # John 3:16, John 3:16-18, John three sixteen to eighteen
    f"{BOOK} [chapter] {CHAPTER}({'|'.join(SEPARATORS)}){VERSE}"
    f"[({'|'.join(RANGES)}){TO}]",
    # Jude 3 to 5 (a book of one chapter: ebac-api reads them as verses)
    f"{BOOK} [verses] {CHAPTER}({'|'.join(RANGES)}){TO}",
    # John 3, John chapter 3
    f"{BOOK} [chapter] {CHAPTER}",
    # read Genesis
    "read [the] [book of] {ebac_book:book}",
]

OTHER_SENTENCES = {
    INTENT_NEXT: [
        "[read] [the] (next|following) verse",
        "[go] (on|forward) [a|one] verse",
    ],
    INTENT_PREVIOUS: [
        "[read] [the] (previous|last|preceding) verse",
        "[go] back [a|one] verse",
        "verse before",
    ],
    INTENT_REPEAT: [
        "read (that|it|the verse|that verse) again",
        "repeat (that|the|this) verse",
        "say (that|the|this) verse again",
    ],
    INTENT_READ_ON: [
        "(read|continue) on",
        "(keep|continue|go on) reading",
        "read [some] more",
    ],
    INTENT_SEARCH: [
        "search [the] (bible|scripture|scriptures) for {ebac_words:words}",
        "find {ebac_words:words} in the (bible|scripture|scriptures)",
    ],
}


def book_forms(book: dict[str, Any]) -> list[str]:
    """How a book may be said: its spoken forms from /books, each also
    without or with a final "s" ("Psalm", "Revelations"), as EBaC's
    parser forgives."""
    forms: list[str] = []
    for form in book.get("spoken") or [book["full_name"]]:
        for variant in (form, form[:-1] if form.endswith("s") else form + "s"):
            if variant and variant.lower() not in (f.lower() for f in forms):
                forms.append(variant)
    return forms


def build(books: list[dict[str, Any]], numbers: list[dict[str, Any]]) -> dict:
    """The sentence file, as YAML's data."""
    book_values = []
    for book in books:
        for form in book_forms(book):
            book_values.append({"in": form, "out": book["full_name"]})
    number_values = [
        {"in": form, "out": entry["number"]}
        for entry in numbers
        for form in entry["spoken"]
        if not form.isdigit()
    ]
    most = max((entry["number"] for entry in numbers), default=1)
    intents: dict[str, Any] = {INTENT_READ: {"data": [{"sentences": READ_SENTENCES}]}}
    for intent, sentences in OTHER_SENTENCES.items():
        intents[intent] = {"data": [{"sentences": sentences}]}
    return {
        "language": LANGUAGE,
        "intents": intents,
        "lists": {
            "ebac_book": {"values": book_values},
            "ebac_digits": {"range": {"from": 1, "to": most}},
            "ebac_number": {"values": number_values},
            "ebac_words": {"wildcard": True},
        },
    }


def path(config_dir: str) -> Path:
    """Where the sentence file goes."""
    return Path(config_dir) / "custom_sentences" / LANGUAGE / SENTENCES_FILE


def write(config_dir: str, data: dict) -> bool:
    """Write the sentence file (run in an executor). True if it changed."""
    text = HEADER + yaml.safe_dump(
        data, allow_unicode=True, sort_keys=False, width=1000
    )
    file = path(config_dir)
    try:
        if file.read_text(encoding="utf-8") == text:
            return False
    except OSError:
        pass
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(text, encoding="utf-8")
    return True


def remove(config_dir: str) -> bool:
    """Remove the sentence file (run in an executor). True if it was there."""
    try:
        path(config_dir).unlink()
    except FileNotFoundError:
        return False
    return True
