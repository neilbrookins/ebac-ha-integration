"""Setting up EBaC: found by the EBaC app's announcement, or an address typed.

The EBaC app announces itself to Home Assistant (Supervisor discovery,
service "ebac"), so the integration is offered under Settings > Devices &
services with one click to confirm. Otherwise the address of ebac-api is
typed: the app's (the default), or any web server running ebac-api.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .api import EbacApi, EbacError
from .const import (
    CONF_ALLOW_ADD,
    CONF_ALLOW_CHANGE,
    CONF_ALLOW_REMOVE,
    CONF_LANGUAGE,
    CONF_READ_ON,
    CONF_TRANSLATION,
    CONF_URL,
    DEFAULT_LANGUAGE,
    DEFAULT_READ_ON,
    DEFAULT_URL,
    DOMAIN,
    MAX_READ_ON,
)

TITLE = "EBaC"
# The translation offered first at setup: the King James Version, which
# comes with every EBaC (else the first installed).
DEFAULT_TRANSLATION = "AV"


def translation_selector(translations: list[dict[str, str]]) -> SelectSelector:
    """A list of the translations installed, to choose one."""
    return SelectSelector(
        SelectSelectorConfig(
            options=[
                SelectOptionDict(value=t["name"], label=f"{t['name']}: {t['title']}")
                for t in translations
            ],
            mode=SelectSelectorMode.DROPDOWN,
        )
    )


async def language_selector(api: EbacApi) -> SelectSelector:
    """The languages translations can be added in (from the EBaC app's
    list, if its options allow adding; else English, or a code typed)."""
    options = [SelectOptionDict(value=DEFAULT_LANGUAGE, label="English")]
    try:
        languages = (await api.catalog())["languages"]
    except (EbacError, KeyError):
        languages = []
    if languages:
        options = [
            SelectOptionDict(
                value=lang["code"],
                label=lang.get("english") or lang.get("own") or lang["code"],
            )
            for lang in languages
        ]
    return SelectSelector(
        SelectSelectorConfig(
            options=options, mode=SelectSelectorMode.DROPDOWN, custom_value=True
        )
    )


def permission_fields(options: dict[str, Any]) -> dict:
    """The three checkboxes, each off unless checked (see "Permissions" in
    EBaC's readme.architecture)."""
    return {
        vol.Required(
            CONF_ALLOW_CHANGE, default=bool(options.get(CONF_ALLOW_CHANGE, False))
        ): BooleanSelector(),
        vol.Required(
            CONF_ALLOW_ADD, default=bool(options.get(CONF_ALLOW_ADD, False))
        ): BooleanSelector(),
        vol.Required(
            CONF_ALLOW_REMOVE, default=bool(options.get(CONF_ALLOW_REMOVE, False))
        ): BooleanSelector(),
    }


def permission_errors(user_input: dict[str, Any]) -> dict[str, str]:
    """Each checkbox needs the one above it (forms can't grey one out)."""
    if user_input.get(CONF_ALLOW_ADD) and not user_input.get(CONF_ALLOW_CHANGE):
        return {CONF_ALLOW_ADD: "add_needs_change"}
    if user_input.get(CONF_ALLOW_REMOVE) and not user_input.get(CONF_ALLOW_ADD):
        return {CONF_ALLOW_REMOVE: "remove_needs_add"}
    return {}


class EbacConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up EBaC (one, for all of Home Assistant)."""

    VERSION = 1

    def __init__(self) -> None:
        self._url: str | None = None
        self._app: str = "EBaC"
        self._translations: list[dict[str, str]] = []

    async def _check(self, url: str) -> str | None:
        """None if ebac-api answers at url (and its translations are kept,
        to choose from); else the error's key."""
        try:
            self._translations = await EbacApi(
                async_get_clientsession(self.hass), url
            ).translations()
        except EbacError:
            return "cannot_connect"
        if not self._translations:
            return "no_translations"
        return None

    async def async_step_translation(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Which translation to read from, to start with (the options can
        change it later, as can "change translation" said to Assist, if
        allowed); the language translations are added in; and what Assist
        may do beyond reading."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = permission_errors(user_input)
            if not errors:
                return self.async_create_entry(
                    title=TITLE,
                    data={CONF_URL: self._url},
                    options={
                        CONF_TRANSLATION: user_input[CONF_TRANSLATION],
                        CONF_READ_ON: DEFAULT_READ_ON,
                        CONF_LANGUAGE: user_input.get(CONF_LANGUAGE) or DEFAULT_LANGUAGE,
                        CONF_ALLOW_CHANGE: user_input[CONF_ALLOW_CHANGE],
                        CONF_ALLOW_ADD: user_input[CONF_ALLOW_ADD],
                        CONF_ALLOW_REMOVE: user_input[CONF_ALLOW_REMOVE],
                    },
                )
        names = [t["name"] for t in self._translations]
        default = DEFAULT_TRANSLATION if DEFAULT_TRANSLATION in names else names[0]
        assert self._url is not None
        api = EbacApi(async_get_clientsession(self.hass), self._url)
        given = user_input or {}
        return self.async_show_form(
            step_id="translation",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TRANSLATION, default=given.get(CONF_TRANSLATION, default)
                    ): translation_selector(self._translations),
                    vol.Required(
                        CONF_LANGUAGE, default=given.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
                    ): await language_selector(api),
                    **permission_fields(given),
                }
            ),
            errors=errors,
        )

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """The EBaC app announced itself."""
        config = discovery_info.config
        url = f"http://{config['host']}:{config['port']}{config.get('path', '')}"
        await self.async_set_unique_id(DOMAIN)
        # (already set up: follow the app, if its address changed)
        self._abort_if_unique_id_configured(updates={CONF_URL: url})
        self._url = url
        self._app = discovery_info.name or self._app
        self.context["title_placeholders"] = {"name": self._app}
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm the app found."""
        errors: dict[str, str] = {}
        if user_input is not None:
            assert self._url is not None
            if (error := await self._check(self._url)) is None:
                return await self.async_step_translation()
            errors["base"] = error
        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={"app": self._app},
            errors=errors,
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up by hand: ebac-api's address."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        errors: dict[str, str] = {}
        url = DEFAULT_URL
        if user_input is not None:
            url = user_input[CONF_URL].strip().rstrip("/")
            if (error := await self._check(url)) is None:
                self._url = url
                return await self.async_step_translation()
            errors["base"] = error
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL, default=url): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.URL)
                    )
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return EbacOptionsFlow()


class EbacOptionsFlow(OptionsFlow):
    """The translation to read from, how much "read on" reads, the
    language translations are added in, and what Assist may do beyond
    reading."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = permission_errors(user_input)
            if not errors:
                user_input[CONF_READ_ON] = int(user_input[CONF_READ_ON])
                return self.async_create_entry(data=user_input)
        api = EbacApi(
            async_get_clientsession(self.hass), self.config_entry.data[CONF_URL]
        )
        try:
            translations = await api.translations()
        except EbacError:
            return self.async_abort(reason="cannot_connect")
        options = {**self.config_entry.options, **(user_input or {})}
        current = options.get(CONF_TRANSLATION)
        names = [t["name"] for t in translations]
        if current not in names:
            current = names[0] if names else ""
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TRANSLATION, default=current): translation_selector(
                        translations
                    ),
                    vol.Required(
                        CONF_READ_ON,
                        default=options.get(CONF_READ_ON, DEFAULT_READ_ON),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=MAX_READ_ON, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                    vol.Required(
                        CONF_LANGUAGE, default=options.get(CONF_LANGUAGE, DEFAULT_LANGUAGE)
                    ): await language_selector(api),
                    **permission_fields(options),
                }
            ),
            errors=errors,
        )
