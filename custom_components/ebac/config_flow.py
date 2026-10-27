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
    CONF_READ_ON,
    CONF_TRANSLATION,
    CONF_URL,
    DEFAULT_READ_ON,
    DEFAULT_URL,
    DOMAIN,
    MAX_READ_ON,
)

TITLE = "EBaC"


class EbacConfigFlow(ConfigFlow, domain=DOMAIN):
    """Set up EBaC (one, for all of Home Assistant)."""

    VERSION = 1

    def __init__(self) -> None:
        self._url: str | None = None
        self._app: str = "EBaC"

    async def _check(self, url: str) -> str | None:
        """None if ebac-api answers at url; else the error's key."""
        try:
            await EbacApi(async_get_clientsession(self.hass), url).translations()
        except EbacError:
            return "cannot_connect"
        return None

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
                return self.async_create_entry(title=TITLE, data={CONF_URL: self._url})
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
                return self.async_create_entry(title=TITLE, data={CONF_URL: url})
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
    """The translation to read from, and how much "read on" reads."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            user_input[CONF_READ_ON] = int(user_input[CONF_READ_ON])
            return self.async_create_entry(data=user_input)
        api = EbacApi(
            async_get_clientsession(self.hass), self.config_entry.data[CONF_URL]
        )
        try:
            translations = await api.translations()
        except EbacError:
            return self.async_abort(reason="cannot_connect")
        options = self.config_entry.options
        current = options.get(CONF_TRANSLATION)
        names = [t["name"] for t in translations]
        if current not in names:
            current = names[0] if names else ""
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TRANSLATION, default=current): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=t["name"], label=f"{t['name']}: {t['title']}"
                                )
                                for t in translations
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(
                        CONF_READ_ON,
                        default=options.get(CONF_READ_ON, DEFAULT_READ_ON),
                    ): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=MAX_READ_ON, step=1, mode=NumberSelectorMode.BOX
                        )
                    ),
                }
            ),
        )
