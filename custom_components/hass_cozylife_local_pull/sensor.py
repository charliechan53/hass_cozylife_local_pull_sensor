"""Platform for sensor integration."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from typing import Any, Final, Literal, TypedDict, final
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
import logging

_LOGGER = logging.getLogger(__name__)
_LOGGER.info('switch')


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """Set up the sensor platform."""
    # We only want this platform to be set up via discovery.
    # logging.info('setup_platform', hass, config, add_entities, discovery_info)
    _LOGGER.info('setup_platform')
    _LOGGER.info(f'ip={hass.data[DOMAIN]}')
    
    if discovery_info is None:
        return


    sensors = []
    for item in hass.data[DOMAIN]['tcp_client']:
        if SWITCH_TYPE_CODE == item.device_type_code:
            sensors.append(CozyLifePowerSensor(item, '28', 'W', 'power'))
            sensors.append(CozyLifeEnergySensor(item, '2', 'kWh', 'energy_total'))
            sensors.append(CozyLifeEnergySensor(item, '26', 'kWh', 'energy_daily'))
    
    add_entities(sensors)

class CozyLifePowerSensor(SensorEntity):
    _tcp_client = None
    _state = None
    
    def __init__(self, tcp_client, fld, unit, sensor_type) -> None:
        """Initialize the power sensor."""
        _LOGGER.info('__init__')
        self._tcp_client = tcp_client
        self._unique_id = 'pw_' + fld + '_' + tcp_client.device_id
        self.attrs: dict[str, Any] = {}
        self._name = tcp_client.device_model_name + ' ' + tcp_client.device_id[-4:] + ' Power'
        self._state = None
        self._refresh_state()
        self._fld = fld
        self._unit = unit
        self._sensor_type = sensor_type
    
    def _refresh_state(self):
        try:
            self._state = self._tcp_client.query()[self._fld]
        except Exception:
            self._state = 0     
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return True
    
    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return self._unique_id

    @property
    def state(self) -> str | None:
        return self._state
        
    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit
    
    @property
    def device_class(self):
        """Return the device class."""
        return SensorDeviceClass.POWER
    
    @property
    def state_class(self):
        """Return the state class."""
        return SensorStateClass.MEASUREMENT
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.attrs

    async def async_update(self):
        self._refresh_state()


class CozyLifeEnergySensor(SensorEntity):
    _tcp_client = None
    _state = None
    
    def __init__(self, tcp_client, fld, unit, sensor_type) -> None:
        """Initialize the energy sensor."""
        _LOGGER.info('__init__')
        self._tcp_client = tcp_client
        self._unique_id = 'en_' + fld + '_' + tcp_client.device_id
        self.attrs: dict[str, Any] = {}
        name_suffix = 'Total Energy' if sensor_type == 'energy_total' else 'Daily Energy'
        self._name = tcp_client.device_model_name + ' ' + tcp_client.device_id[-4:] + ' ' + name_suffix
        self._state = None
        self._refresh_state()
        self._fld = fld
        self._unit = unit
        self._sensor_type = sensor_type
    
    def _refresh_state(self):
        try:
            raw_value = self._tcp_client.query()[self._fld]
            # Convert from Wh to kWh if needed
            if raw_value is not None:
                self._state = round(float(raw_value) / 1000, 3) if self._unit == 'kWh' else raw_value
        except Exception:
            self._state = 0     
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return True
    
    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return self._unique_id

    @property
    def state(self) -> str | None:
        return self._state
        
    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self._unit
    
    @property
    def device_class(self):
        """Return the device class."""
        return SensorDeviceClass.ENERGY
    
    @property
    def state_class(self):
        """Return the state class."""
        if self._sensor_type == 'energy_total':
            return SensorStateClass.TOTAL_INCREASING
        else:
            return SensorStateClass.TOTAL
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self.attrs

    async def async_update(self):
        self._refresh_state()
