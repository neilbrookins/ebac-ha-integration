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
    INTENT_RESULT,
    INTENT_NEXT_RESULT,
    INTENT_PREVIOUS_RESULT,
    INTENT_MORE_RESULTS,
    INTENT_EARLIER_RESULTS,
    INTENT_BACK_TO_RESULTS,
    INTENT_TRANSLATION,
    INTENT_WHICH_TRANSLATION,
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

# The text before a chapter's verse 1, where a text has it (verse 0: a
# book's heading and summary, in the Book of Mormon from Project
# Gutenberg): "Jacob introduction", "the introduction to Alma chapter 5".
# (A fixed slot, intro, tells the handler.)
INTRO_SENTENCES = [
    f"{BOOK} [chapter {CHAPTER}] introduction",
    "[read] [the] introduction (to|of) [the] [book of] {ebac_book:book} [chapter " + CHAPTER + "]",
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
    # "Repeat verse", to go with "next verse" and "previous verse"
    INTENT_REPEAT: [
        "(read|say) (that|it|the verse|that verse|this verse|the verses|those verses) (again|one more time)",
        "repeat [the|that|this] (verse|verses)",
        "repeat (that|it)",
        "[read|say] [the|that] (verse|verses) again",
        "(same|this) verse again",
        "again",
        "one more time",
    ],
    INTENT_READ_ON: [
        "(read|continue) on",
        "(keep|continue|go on) reading",
        "read [some] more",
    ],
    # (after fixed words, the name is a wildcard: the handler matches it,
    # by short name or title words, against the translations installed)
    INTENT_TRANSLATION: [
        "(change|select|set|switch) [the] [bible] translation [to] {ebac_translation:name}",
        "(change|switch) to [the] {ebac_translation:name} translation",
        "use [the] {ebac_translation:name} translation",
        "read from [the] {ebac_translation:name} translation",
    ],
    INTENT_WHICH_TRANSLATION: [
        "(which|what) translation [is (this|that|it)]",
        "(which|what) translation are you (reading|using)",
        "(which|what) translation is in use",
    ],
    # A search's results (see "A search's results" in readme.architecture).
    # "Result two", "number two", "the second result".
    INTENT_RESULT: [
        "[read|open|go to|show] [the] (result|number) "
        "({ebac_digits:number}|{ebac_number:number})",
        "[read|open|go to|show] the {ebac_ordinal:number} [result|one]",
    ],
    INTENT_NEXT_RESULT: [
        "[read] [the] next (result|one|match)",
        "[go to] [the] following result",
    ],
    INTENT_PREVIOUS_RESULT: [
        "[read] [the] (previous|last) (result|match)",
        "[go] back [a|one] result",
    ],
    INTENT_MORE_RESULTS: [
        "more results",
        "[list|read] [the] next (results|five)",
        "(list|read) more [results]",
    ],
    INTENT_EARLIER_RESULTS: [
        "(earlier|previous) results",
        "[list|read] [the] previous five",
    ],
    INTENT_BACK_TO_RESULTS: [
        "[go] back to the (results|list|search)",
        "(list|read) the results [again]",
        "(show|list) the search [results]",
    ],
    INTENT_SEARCH: [
        "search [the] (bible|scripture|scriptures) for {ebac_words:words}",
        "find {ebac_words:words} in the (bible|scripture|scriptures)",
    ],
    # Moving through the text (see "Moving through the text" in
    # readme.architecture): a few verses at a time, on across books
    INTENT_NEXT_CHAPTER: [
        "[read] [the] next chapter",
        "[go] (on|forward) [a|one] chapter",
    ],
    INTENT_PREVIOUS_CHAPTER: [
        "[read] [the] (previous|last|preceding) chapter",
        "[go] back [a|one] chapter",
    ],
    INTENT_START_CHAPTER: [
        "[go to|read] [the] (start|beginning) of [the|this] chapter",
        "[read] this chapter from the (start|beginning)",
    ],
    INTENT_READ_BACK: [
        "read back",
        "[read] [the] verses before",
        "(go|page) back [some] [more]",
    ],
    INTENT_NEXT_BOOK: [
        "[read] [the] next book",
        "[go] (on|forward) [a|one] book",
    ],
    INTENT_PREVIOUS_BOOK: [
        "[read] [the] (previous|last|preceding) book",
        "[go] back [a|one] book",
    ],
    INTENT_START_BOOK: [
        "[go to|read] [the] (start|beginning) of [the|this] book",
        "[read] this book from the (start|beginning)",
    ],
    # Information (I in the app)
    INTENT_VERSION: [
        "(what|which) version of (ebac|e bac|e back|eback|ebak|the bible app) is (this|it|installed|running)",
        "(what|which) (ebac|e bac|e back|eback|ebak) version [is (this|it)]",
        "(ebac|e bac|e back|eback|ebak) version",
    ],
    INTENT_LICENSE: [
        "(what|what's|what is) the license (of|for|on) [the|this] translation",
        "(what|which) license is (this|the) translation (under|in)",
        "[what's|what is] this translation's license",
    ],
    # The language group, lists, adding and removing (the handlers check
    # the integration's checkboxes)
    INTENT_USE_LANGUAGE: [
        "(use|switch to|choose|select) {ebac_language:language} translations",
        "manipulate translations {ebac_language:language}",
        "manipulate {ebac_language:language} translations",
    ],
    INTENT_LIST_LANGUAGES: [
        "(which|what) languages (are there|can i (add|choose|use)|have translations)",
        "(list|read) [the] languages",
    ],
    INTENT_LIST_AVAILABLE: [
        "(which|what) translations (are there|can i add) [in {ebac_language:language}]",
        "(list|read) [the] translations [that] (i can add|to add) [in {ebac_language:language}]",
    ],
    INTENT_LIST_ADDED: [
        "(which|what) translations (are|have been) (added|installed)",
        "(which|what) translations do (i|we) have",
        "(list|read) [the] (added|installed) translations",
    ],
    INTENT_MORE_LIST: [
        "more (languages|translations)",
        "[list|read] [the] next (languages|translations)",
    ],
    INTENT_EARLIER_LIST: [
        "(earlier|previous) (languages|translations)",
    ],
    INTENT_ADD: [
        "(add|download|install) [the] translation {ebac_translation:name}",
        "(add|download|install) the {ebac_translation:name} translation",
    ],
    INTENT_REMOVE: [
        "(remove|delete|uninstall) [the] translation {ebac_translation:name}",
        "(remove|delete|uninstall) the {ebac_translation:name} translation",
    ],
    # The answer to "Do you agree?" or "Are you sure?"
    INTENT_YES: [
        "yes",
        "yes [i] (agree|do|am|please|i'm sure|i am sure)",
        "i agree",
        "yes (add|remove|delete) it",
    ],
    INTENT_NO: [
        "no",
        "no (thanks|thank you|i don't|don't|i do not)",
        "i (don't|do not) agree",
        "(don't|do not) (add|remove|delete) it",
    ],
}


# "The second result": English ordinals, to the twentieth (results are
# listed five at a time; beyond that, "result twenty one").
ORDINALS = [
    {"in": word, "out": n}
    for n, word in enumerate(
        "first second third fourth fifth sixth seventh eighth ninth tenth "
        "eleventh twelfth thirteenth fourteenth fifteenth sixteenth "
        "seventeenth eighteenth nineteenth twentieth".split(),
        start=1,
    )
] + [{"in": f"{n}{'st' if n % 10 == 1 and n != 11 else 'nd' if n % 10 == 2 and n != 12 else 'rd' if n % 10 == 3 and n != 13 else 'th'}", "out": n} for n in range(1, 21)]


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
    intents: dict[str, Any] = {
        INTENT_READ: {
            "data": [
                {"sentences": READ_SENTENCES},
                {"sentences": INTRO_SENTENCES, "slots": {"intro": "yes"}},
            ]
        }
    }
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
            "ebac_ordinal": {"values": ORDINALS},
            "ebac_translation": {"wildcard": True},
            "ebac_language": {"wildcard": True},
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
