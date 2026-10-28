"""Talking to ebac-api, EBaC's answers in JSON.

ebac-api is a CGI program: http://HOST:8080/cgi-bin/ebac/REQUEST?PARAMS.
Its requests are described in EBaC's readme.architecture, under "Voice":
translations, books, numbers, parse, verse, next, previous and search.
An error is HTTP 400 with {"error": "..."}.
"""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

TIMEOUT = 15  # seconds (a search of a common word takes well under one)


class EbacError(Exception):
    """ebac-api couldn't answer: the message says why, fit to be spoken."""


class EbacApi:
    """A client for one ebac-api."""

    def __init__(self, session: aiohttp.ClientSession, url: str) -> None:
        self._session = session
        self._url = url.rstrip("/")

    async def request(self, request: str, **params: Any) -> dict[str, Any]:
        """Make a request; its JSON answer, or EbacError."""
        params = {k: str(v) for k, v in params.items() if v is not None}
        try:
            async with self._session.get(
                f"{self._url}/{request}",
                params=params,
                timeout=aiohttp.ClientTimeout(total=TIMEOUT),
            ) as response:
                try:
                    answer = await response.json(content_type=None)
                except ValueError as err:
                    raise EbacError(
                        f"EBaC's answer wasn't understood (HTTP {response.status})"
                    ) from err
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise EbacError(f"EBaC can't be reached at {self._url}") from err
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
