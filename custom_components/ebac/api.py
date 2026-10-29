"""Talking to ebac-api, EBaC's answers in JSON.

ebac-api is a CGI program: http://HOST:8080/cgi-bin/ebac/REQUEST?PARAMS.
Its requests are described in EBaC's readme.architecture, under "Voice":
translations, books, numbers, parse, verse, next, previous, search, info
and license. An error is HTTP 400 with {"error": "..."}.

Beside it, ebac-admin (http://HOST:8080/cgi-bin/ebac-admin/REQUEST)
adds and removes translations, only as the EBaC app's options allow:
permissions, catalog, license, check, add, status and remove (see the top
of EBaC's ebac-admin). Its refusals are errors too (HTTP 403, or 409 when
another add is under way).
"""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

TIMEOUT = 15  # seconds (a search of a common word takes well under one)
# ebac-admin's catalog downloads the list of translations first
ADMIN_TIMEOUT = 90


class EbacError(Exception):
    """ebac-api couldn't answer: the message says why, fit to be spoken."""


class EbacApi:
    """A client for one ebac-api."""

    def __init__(self, session: aiohttp.ClientSession, url: str) -> None:
        self._session = session
        self._url = url.rstrip("/")
        # ebac-admin, beside ebac-api: .../cgi-bin/ebac -> .../cgi-bin/ebac-admin
        base, _, last = self._url.rpartition("/")
        self._admin = f"{self._url}-admin" if last == "ebac" else f"{base}/ebac-admin"

    async def request(
        self, request: str, *, admin: bool = False, **params: Any
    ) -> dict[str, Any]:
        """Make a request (of ebac-admin, if admin); its JSON answer, or
        EbacError."""
        params = {k: str(v) for k, v in params.items() if v is not None}
        url = self._admin if admin else self._url
        try:
            async with self._session.get(
                f"{url}/{request}",
                params=params,
                timeout=aiohttp.ClientTimeout(total=ADMIN_TIMEOUT if admin else TIMEOUT),
            ) as response:
                try:
                    answer = await response.json(content_type=None)
                except ValueError as err:
                    raise EbacError(
                        f"EBaC's answer wasn't understood (HTTP {response.status})"
                    ) from err
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise EbacError(f"EBaC can't be reached at {url}") from err
        if not isinstance(answer, dict):
            raise EbacError("EBaC's answer wasn't understood")
        if "error" in answer:
            raise EbacError(str(answer["error"]))
        return answer

    async def translations(self) -> list[dict[str, str]]:
        """The translations: [{"name": "AV", "title": "..."}]."""
        return (await self.request("translations"))["translations"]

    async def books(self, translation: str | None) -> list[dict[str, Any]]:
        """A translation's books, with their spoken forms."""
        return (await self.request("books", t=translation))["books"]

    async def numbers(self, translation: str | None) -> list[dict[str, Any]]:
        """The numbers up to the most chapters or verses, and how each
        is said."""
        return (await self.request("numbers", t=translation))["numbers"]

    async def verse(
        self, translation: str | None, ref: str, count: int | None = None
    ) -> dict[str, Any]:
        """The verses of a reference ("John 3:16", "Jude 3 to 5")."""
        return await self.request("verse", t=translation, ref=ref, n=count)

    async def next(
        self, translation: str | None, svn: int, count: int = 1
    ) -> dict[str, Any]:
        """The verses after verse svn."""
        return await self.request("next", t=translation, svn=svn, n=count)

    async def previous(
        self, translation: str | None, svn: int, count: int = 1
    ) -> dict[str, Any]:
        """The verses before verse svn."""
        return await self.request("previous", t=translation, svn=svn, n=count)

    async def search(
        self, translation: str | None, words: str, most: int, start: int = 1
    ) -> dict[str, Any]:
        """A search, in EBaC's own syntax (words alone are a phrase): how
        many verses, and those from result start (1 for the first)."""
        return await self.request(
            "search", t=translation, q=words, max=most, start=start
        )

    async def info(self) -> dict[str, Any]:
        """EBaC's release, commit and package, and where to get help."""
        return await self.request("info")

    async def license(self, translation: str) -> dict[str, Any]:
        """The license kept when a translation was added ("recorded")."""
        return await self.request("license", t=translation)

    # ---- ebac-admin: adding and removing translations

    async def permissions(self) -> dict[str, bool]:
        """What the EBaC app's options allow: {"add": ..., "remove": ...}."""
        return await self.request("permissions", admin=True)

    async def catalog(self) -> dict[str, Any]:
        """Every language and translation that can be added."""
        return await self.request("catalog", admin=True)

    async def source_license(self, name: str) -> dict[str, Any]:
        """A translation's title, license and details page, from the source."""
        return await self.request("license", admin=True, name=name)

    async def check(self, name: str) -> dict[str, Any]:
        """Whether it is added, and if so whether it is the same version."""
        return await self.request("check", admin=True, name=name)

    async def add(self, name: str, agreed: str) -> dict[str, Any]:
        """Start adding it (in the background), agreeing to its license."""
        return await self.request("add", admin=True, name=name, agreed=agreed)

    async def status(self, name: str) -> dict[str, Any]:
        """How its add is going: running, done, failed, or none."""
        return await self.request("status", admin=True, name=name)

    async def remove(self, name: str) -> dict[str, Any]:
        """Remove it."""
        return await self.request("remove", admin=True, name=name)
