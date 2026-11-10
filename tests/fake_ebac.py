"""A fake EBaC: ebac-api and ebac-admin, answering as the real ones do.

Their requests are described in EBaC's readme.architecture ("Voice") and
at the top of ebac-admin; api.py is the integration's side. The text is
made up ("John 3:16 text"), but the shapes of the answers are EBaC's, so
the integration is tested through its real client (api.py) and HTTP.

Each chapter has VERSES verses; Jude has one chapter (a reference to it is
read as verses: "Jude 3 to 5" is Jude 1:3-5, as EBaC's parser reads it).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

URL = "http://ebac.test:8080/cgi-bin/ebac"
ADMIN_URL = "http://ebac.test:8080/cgi-bin/ebac-admin"
VERSES = 40

TETRAGRAMMATON = "יהוה"
# The same word as the Westminster Leningrad Codex writes it: with vowel
# points, and a chant mark (U+0591) among the letters
POINTED = "יְהוָ֑ה"

# (full name, chapters, the spoken forms /books gives)
BIBLE = [
    ("Genesis", 50, ["Genesis"]),
    ("1 Samuel", 31, ["1 Samuel", "First Samuel", "I Samuel"]),
    ("Psalms", 150, ["Psalms"]),
    ("John", 21, ["John"]),
    ("Jude", 1, ["Jude"]),
    ("Revelation", 22, ["Revelation"]),
]
# The Hebrew Bible: no New Testament
HEBREW = [b for b in BIBLE if b[0] in ("Genesis", "1 Samuel", "Psalms")]
# With the Apocrypha between the Testaments: the same verse has another
# SVN than in the AV (so a place is looked up again by reference)
APOCRYPHA = [*BIBLE[:3], ("Tobit", 14, ["Tobit"]), *BIBLE[3:]]

TRANSLATIONS = {
    "AV": {"title": "King James Version", "books": BIBLE},
    "WLC": {"title": "The Westminster Leningrad Codex", "books": HEBREW},
    "KJVA-SM": {"title": "King James Version with Apocrypha", "books": APOCRYPHA},
    # (not installed to begin with: added by voice)
    "LITV-SM": {"title": "Literal Translation of the Holy Bible", "books": BIBLE},
    "WEB-PG": {"title": "World English Bible", "books": BIBLE},
}

# What a search finds: the words searched for, and the verses that have them
SEARCHES = {
    "jesus wept": ["John 11:35"],
    "love": [f"John {c}:{v}" for c in (3, 13, 14, 15) for v in (1, 2, 3)],
}

_ONES = "zero one two three four five six seven eight nine ten eleven twelve " \
    "thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def number_words(n: int) -> str:
    """16 as "sixteen", 119 as "one hundred nineteen"."""
    if n < 20:
        return _ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _TENS[tens] + (f" {_ONES[ones]}" if ones else "")
    hundreds, rest = divmod(n, 100)
    return f"{_ONES[hundreds]} hundred" + (f" {number_words(rest)}" if rest else "")


def roman(n: int) -> str:
    out = ""
    for value, letters in ((100, "c"), (90, "xc"), (50, "l"), (40, "xl"), (10, "x"),
                           (9, "ix"), (5, "v"), (4, "iv"), (1, "i")):
        while n >= value:
            out += letters
            n -= value
    return out


class Answer(Exception):
    """An error answer: HTTP status and {"error": message}."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.status = status


@dataclass
class FakeEbac:
    """The state of the fake EBaC, which tests may change."""

    installed: list[str] = field(default_factory=lambda: ["AV", "WLC", "KJVA-SM"])
    said: list[dict[str, str]] = field(
        default_factory=lambda: [{"word": TETRAGRAMMATON, "say": "Adonai"}]
    )
    # what the EBaC app's options allow (ebac-admin)
    allow_add: bool = True
    allow_remove: bool = True
    # licenses recorded when translations were added: {name: {...}}
    licenses: dict[str, dict] = field(default_factory=dict)
    # adds under way or ended: {name: {"state": ..., "message": ...}}
    adds: dict[str, dict] = field(default_factory=dict)
    # down: no answer at all (the app stopped or removed)
    down: bool = False
    # broken: an answer that isn't JSON
    broken: bool = False
    # every request made: (path, params)
    requests: list[tuple[str, dict[str, str]]] = field(default_factory=list)

    # ---- the text

    def _translation(self, params: dict[str, str]) -> str:
        name = params.get("t") or self.installed[0]
        if name not in self.installed:
            raise Answer(f"No translation called {name} is installed")
        return name

    def _verses(self, translation: str) -> list[tuple[str, int, int]]:
        """Every verse of a translation, in order: its index is its SVN - 1."""
        return [
            (book, chapter, verse)
            for book, chapters, _ in TRANSLATIONS[translation]["books"]
            for chapter in range(1, chapters + 1)
            for verse in range(1, VERSES + 1)
        ]

    def _verse(self, translation: str, svn: int) -> dict[str, Any]:
        book, chapter, verse = self._verses(translation)[svn - 1]
        text = f"{book} {chapter}:{verse} text"
        if translation == "WLC" and (book, chapter, verse) == ("Genesis", 2, 4):
            text = f"{POINTED} אֱלֹהִים"
        return {
            "ref": f"{book} {chapter}:{verse}",
            "svn": svn,
            "book": book,
            "chapter": chapter,
            "verse": verse,
            "text": text,
            "spoken": f"{book} chapter {chapter}, verse {verse}. {text}.",
        }

    def _svn(self, translation: str, book: str, chapter: int, verse: int) -> int:
        try:
            return self._verses(translation).index((book, chapter, verse)) + 1
        except ValueError:
            raise Answer(f"There is no {book} {chapter}:{verse}") from None

    def _parse(self, translation: str, ref: str) -> tuple[int, int | None]:
        """A reference: the SVN of its first verse, and of its last (None:
        to be counted from the first)."""
        books = TRANSLATIONS[translation]["books"]
        title = TRANSLATIONS[translation]["title"]
        for book, chapters, _ in sorted(books, key=lambda b: -len(b[0])):
            if ref == book or ref.startswith(book + " "):
                rest = ref[len(book):].strip()
                break
        else:
            raise Answer(f"{title} has no {ref.split()[0]}")
        if rest.endswith("introduction"):
            raise Answer(f"There is no introduction to {book}")
        m = re.fullmatch(r"(?:(\d+)(?::(\d+))?(?: to (\d+))?)?", rest)
        if not m:
            raise Answer(f"{ref} isn't a reference")
        chapter, verse, to = (int(g) if g else None for g in m.groups())
        if chapter == 0:
            raise Answer(f"{book} has no introduction")
        if chapters == 1 and chapter is not None and verse is None and (to or chapter > 1):
            # (one chapter: "Jude 3 to 5" is verses 3 to 5)
            chapter, verse = 1, chapter
        chapter = chapter or 1
        if chapter > chapters:
            raise Answer(f"{book} has {chapters} chapters")
        first = self._svn(translation, book, chapter, verse or 1)
        if to is not None:
            return first, self._svn(translation, book, chapter, to)
        if verse is not None:
            return first, first
        return first, None

    # ---- the requests

    def answer(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        """The JSON answer to a request (or Answer, an error)."""
        admin = path.startswith("admin/")
        request = path.removeprefix("admin/")
        handler = getattr(self, f"{'admin' if admin else 'api'}_{request}", None)
        if handler is None:
            raise Answer(f"No request {request}", 404)
        return handler(params)

    def api_translations(self, params):
        return {
            "translations": [
                {"name": n, "title": TRANSLATIONS[n]["title"]} for n in self.installed
            ]
        }

    def api_said(self, params):
        return {"said": self.said}

    def api_books(self, params):
        t = self._translation(params)
        return {
            "books": [
                {"full_name": book, "chapters": chapters, "spoken": spoken}
                for book, chapters, spoken in TRANSLATIONS[t]["books"]
            ]
        }

    def api_numbers(self, params):
        self._translation(params)
        return {
            "numbers": [
                {"number": n, "spoken": [str(n), number_words(n), roman(n)]}
                for n in range(1, 151)
            ]
        }

    def api_verse(self, params):
        t = self._translation(params)
        first, last = self._parse(t, params["ref"])
        if "n" in params:
            # (a count: that many verses from the first, as EBaC reads
            # "read that again" of a range: its first verse and the count)
            last = first + int(params["n"]) - 1
        elif last is None:
            last = first
        count = len(self._verses(t))
        return {
            "translation": t,
            "verses": [self._verse(t, s) for s in range(first, min(last, count) + 1)],
        }

    def api_next(self, params):
        t = self._translation(params)
        svn, n = int(params["svn"]), int(params.get("n", 1))
        count = len(self._verses(t))
        return {
            "translation": t,
            "verses": [self._verse(t, s) for s in range(svn + 1, min(svn + n, count) + 1)],
        }

    def api_previous(self, params):
        t = self._translation(params)
        svn, n = int(params["svn"]), int(params.get("n", 1))
        return {
            "translation": t,
            "verses": [self._verse(t, s) for s in range(max(1, svn - n), svn)],
        }

    def api_search(self, params):
        t = self._translation(params)
        refs = SEARCHES.get(params["q"], [])
        found = [
            self._verse(t, self._parse(t, ref)[0])
            for ref in refs
            if ref.split()[0] in {b[0] for b in TRANSLATIONS[t]["books"]}
        ]
        start, most = int(params.get("start", 1)), int(params.get("max", 5))
        return {
            "translation": t,
            "count": len(found),
            "start": start,
            "verses": found[start - 1 : start - 1 + most],
        }

    def api_info(self, params):
        return {"release": "1.3.0", "commit": "abc1234, 2026-11-01", "package": "EBaC app 2.14.0"}

    def api_license(self, params):
        t = self._translation(params)
        if t in self.licenses:
            return {"recorded": True, **self.licenses[t]}
        return {"recorded": False}

    # ---- ebac-admin

    def _admin_allowed(self, what: str) -> None:
        if not (self.allow_add if what == "add" else self.allow_remove):
            raise Answer(f"The EBaC app's options don't allow voice to {what} translations", 403)

    def admin_permissions(self, params):
        return {"add": self.allow_add, "remove": self.allow_remove}

    def admin_catalog(self, params):
        self._admin_allowed("add")
        source = params.get("source", "scrollmapper")
        return CATALOGS[source]

    def _catalog_entry(self, params) -> dict:
        source = params.get("source", "scrollmapper")
        for t in CATALOGS[source]["translations"]:
            if t["name"] == params["name"]:
                return t
        raise Answer(f"{params['name']} isn't in {source}'s catalog")

    def admin_license(self, params):
        entry = self._catalog_entry(params)
        return {"title": entry["title"], "license": entry.get("license", "")}

    def admin_check(self, params):
        entry = self._catalog_entry(params)
        return {"added": bool(entry.get("added")), "same_version": bool(entry.get("added")),
                "downloaded": "2026-10-01"}

    def admin_add(self, params):
        self._admin_allowed("add")
        if any(a["state"] == "running" for a in self.adds.values()):
            raise Answer("Another translation is being added", 409)
        self._catalog_entry(params)
        self.adds[params["name"]] = {"state": "running", "message": "", "agreed": params["agreed"]}
        return {"started": True}

    def admin_status(self, params):
        status = self.adds.get(params["name"], {"state": "none"})
        if status["state"] == "done":
            # (installed, by its short name: an ebook's is WEB-PG)
            name = next(
                (t.get("names", t["name"]).split()[0]
                 for c in CATALOGS.values() for t in c["translations"]
                 if t["name"] == params["name"]),
                params["name"],
            )
            if name not in self.installed:
                self.installed.append(name)
        return status

    def admin_remove(self, params):
        self._admin_allowed("remove")
        if params["name"] not in self.installed:
            raise Answer(f"{params['name']} isn't added")
        self.installed.remove(params["name"])
        return {"removed": True}


CATALOGS: dict[str, dict] = {
    "scrollmapper": {
        "languages": [
            {"code": "en", "english": "English", "own": "English", "count": 3},
            {"code": "es", "english": "Spanish", "own": "Español", "count": 1},
            {"code": "grc", "english": "Ancient Greek", "own": "Ἑλληνική", "count": 1},
        ],
        "translations": [
            {"name": "LITV-SM", "title": "Literal Translation of the Holy Bible",
             "language": "en", "license": "Copyright Jay P. Green, used by permission"},
            {"name": "ASV-SM", "title": "American Standard Version", "language": "en",
             "license": "Public domain"},
            {"name": "KJVA-SM", "title": "King James Version with Apocrypha", "language": "en",
             "license": "Public domain", "added": True},
            {"name": "RVG-SM", "title": "Reina Valera Gómez", "language": "es",
             "license": "Public domain"},
            {"name": "TR-SM", "title": "Textus Receptus", "language": "grc",
             "license": "Public domain"},
        ],
    },
    "thiagobodruk": {
        "languages": [
            {"code": "en", "english": "English", "own": "English", "count": 2},
        ],
        "translations": [
            {"name": "NIV-TB", "title": "New International Version", "language": "en",
             "license": "Copyright Biblica"},
            {"name": "BBE-TB", "title": "Bible in Basic English", "language": "en",
             "license": "Public domain"},
        ],
    },
    "gutenberg": {
        "languages": [
            {"code": "en", "english": "English", "own": "English", "count": 1},
        ],
        "translations": [
            {"name": "8294", "names": "WEB-PG", "title": "World English Bible",
             "language": "en", "license": "Public domain in the USA"},
        ],
    },
}
