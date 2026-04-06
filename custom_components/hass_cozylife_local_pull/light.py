"""Platform for light integration."""
from __future__ import annotations

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from typing import Any
from .const import (
    DOMAIN,
    SWITCH_TYPE_CODE,
    LIGHT_TYPE_CODE,
    LIGHT_DPID,
    SWITCH,
    WORK_MODE,
    TEMP,
    BRIGHT,
    HUE,
    SAT,
)
from .tcp_client import tcp_client
import logging

_LOGGER = logging.getLogger(__name__)
_LOGGER.info(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """Set up the light platform."""
    _LOGGER.info(
        f'setup_platform.hass={hass},config={config},add_entities={add_entities},discovery_info={discovery_info}')
    _LOGGER.info(f'hass.data={hass.data[DOMAIN]}')
    _LOGGER.info(f'discovery_info={discovery_info}')

    if discovery_info is None:
        return

    lights = []
    for item in hass.data[DOMAIN]['tcp_client']:
        if LIGHT_TYPE_CODE == item.device_type_code:
            lights.append(CozyLifeLight(item))

    add_entities(lights)


class CozyLifeLight(LightEntity):
    _tcp_client = None

    def __init__(self, tcp_client: tcp_client) -> None:
        """Initialize the light."""
        _LOGGER.info('__init__')
        self._tcp_client = tcp_client
        self._unique_id = tcp_client.device_id
        self._name = tcp_client.device_model_name + ' ' + tcp_client.device_id[-4:]

        # Build supported_color_modes from device capabilities.
        # HA requires exactly one "highest" mode — don't mix ONOFF with BRIGHTNESS,
        # or BRIGHTNESS with COLOR_TEMP/HS (higher modes imply lower ones).
        supported_modes: set[ColorMode] = set()
        if 5 in tcp_client.dpid or 6 in tcp_client.dpid:
            supported_modes.add(ColorMode.HS)
        if 3 in tcp_client.dpid:
            supported_modes.add(ColorMode.COLOR_TEMP)
        if not supported_modes:
            # Brightness-only or plain on/off
            if 4 in tcp_client.dpid:
                supported_modes.add(ColorMode.BRIGHTNESS)
            else:
                supported_modes.add(ColorMode.ONOFF)

        self._attr_supported_color_modes = supported_modes

        # Default active color mode to the highest capability present.
        if ColorMode.HS in supported_modes:
            self._attr_color_mode = ColorMode.HS
        elif ColorMode.COLOR_TEMP in supported_modes:
            self._attr_color_mode = ColorMode.COLOR_TEMP
        elif ColorMode.BRIGHTNESS in supported_modes:
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_color_mode = ColorMode.ONOFF

        _LOGGER.info(
            f'after:{self._unique_id}._attr_color_mode={self._attr_color_mode}'
            f'._attr_supported_color_modes={self._attr_supported_color_modes}'
            f'.dpid={tcp_client.dpid}')

        self._refresh_state()

    def _refresh_state(self):
        """Query device and update attributes."""
        self._state = self._tcp_client.query()
        _LOGGER.info(f'_state={self._state}')
        self._attr_is_on = 0 < self._state['1']

        if '4' in self._state:
            self._attr_brightness = int(self._state['4'] / 4)

        if '5' in self._state:
            self._attr_hs_color = (int(self._state['5']), int(self._state['6'] / 10))

        if '3' in self._state:
            # Device stores color temp as 0–1000 where 0 = warmest.
            # Previous mired conversion: mireds = 500 - raw/2
            # New: store as Kelvin = 1_000_000 / mireds
            raw = int(self._state['3'])
            mireds = 500 - raw // 2
            self._attr_color_temp_kelvin = int(1_000_000 / mireds) if mireds > 0 else 6500

    @property
    def name(self) -> str:
        return self._name

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return True

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        self._refresh_state()
        return self._attr_is_on

    @property
    def min_color_temp_kelvin(self) -> int:
        """Return the warmest (lowest K) color temperature supported."""
        return 2000

    @property
    def max_color_temp_kelvin(self) -> int:
        """Return the coolest (highest K) color temperature supported."""
        return 6500

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return self._unique_id

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        self._attr_is_on = True
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        colortemp_k = kwargs.get(ATTR_COLOR_TEMP_KELVIN)  # Kelvin
        hs_color = kwargs.get(ATTR_HS_COLOR)
        _LOGGER.info(f'turn_on.kwargs={kwargs}')

        payload = {'1': 255, '2': 0}

        if brightness is not None:
            payload['4'] = brightness * 4
            self._attr_brightness = brightness

        if hs_color is not None:
            payload['5'] = int(hs_color[0])
            payload['6'] = int(hs_color[1] * 10)
            self._attr_hs_color = hs_color

        if colortemp_k is not None:
            # Convert Kelvin → mireds → device value (0–1000)
            mireds = int(1_000_000 / colortemp_k)
            payload['3'] = 1000 - mireds * 2

        self._tcp_client.control(payload)
        self._refresh_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        self._attr_is_on = False
        _LOGGER.info(f'turn_off.kwargs={kwargs}')
        self._tcp_client.control({'1': 0})
        self._refresh_state()

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the hue and saturation color value [float, float]."""
        _LOGGER.info('hs_color')
        self._refresh_state()
        return self._attr_hs_color

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        _LOGGER.info('brightness')
        self._refresh_state()
        return self._attr_brightness

    @property
    def color_mode(self) -> str | None:
        """Return the color mode of the light."""
        _LOGGER.info('color_mode')
        return self._attr_color_mode
