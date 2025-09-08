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
            # Create power sensor
            power_sensor = CozyLifePowerSensor(item, '28', 'W', 'power')
            sensors.append(power_sensor)
            
            # Create energy sensor using integration of power sensor
            power_entity_id = f"sensor.pw_28_{item.device_id}"
            energy_sensor = CozyLifeEnergySensorIntegrated(
                item, 
                power_entity_id, 
                'kWh', 
                'energy'
            )
            sensors.append(energy_sensor)
    
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


class CozyLifeEnergySensorIntegrated(SensorEntity):
    """Energy sensor that integrates power readings over time."""
    
    def __init__(self, tcp_client, power_entity_id, unit, sensor_type) -> None:
        """Initialize the energy sensor."""
        _LOGGER.info('CozyLifeEnergySensorIntegrated __init__')
        self._tcp_client = tcp_client
        self._power_entity_id = power_entity_id
        self._unique_id = 'en_int_' + tcp_client.device_id
        self.attrs: dict[str, Any] = {}
        self._name = tcp_client.device_model_name + ' ' + tcp_client.device_id[-4:] + ' Energy'
        self._state = 0.0
        self._unit = unit
        self._sensor_type = sensor_type
        self._last_update = None
        self._last_power = None
    
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
        return SensorStateClass.TOTAL_INCREASING
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        attrs = self.attrs.copy()
        attrs['power_source'] = self._power_entity_id
        attrs['integration_method'] = 'trapezoidal'
        return attrs

    async def async_update(self):
        """Update the energy sensor by integrating power over time."""
        try:
            # Get current power reading directly from TCP client
            current_power = self._tcp_client.query().get('28', 0)
            if current_power is None:
                current_power = 0
            current_power = float(current_power)
            
            from datetime import datetime
            current_time = datetime.now()
            
            if self._last_update is not None and self._last_power is not None:
                # Calculate time difference in hours
                time_diff = (current_time - self._last_update).total_seconds() / 3600
                
                if time_diff > 0 and time_diff < 1:  # Only integrate if reasonable time diff
                    # Trapezoidal integration: average power * time
                    avg_power = (current_power + self._last_power) / 2
                    energy_increment = (avg_power * time_diff) / 1000  # Convert W*h to kWh
                    
                    if energy_increment >= 0:  # Only add positive increments
                        self._state = round(float(self._state) + energy_increment, 6)
            
            # Store current values for next iteration
            self._last_power = current_power
            self._last_update = current_time
            
        except Exception as e:
            _LOGGER.warning(f"Error updating energy sensor {self._unique_id}: {e}")
            # Don't update state on error to maintain total_increasing property
