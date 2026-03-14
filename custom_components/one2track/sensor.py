"""Sensor platform for One2Track."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfLength, UnitOfSpeed

from .entity import One2TrackEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import One2TrackCoordinator
    from .data import One2TrackConfigEntry


@dataclass(frozen=True, kw_only=True)
class One2TrackSensorDescription(SensorEntityDescription):
    """Describes a One2Track sensor."""

    value_fn: Callable[[dict[str, Any]], Any]


def _loc(data: dict) -> dict:
    return data.get("last_location", {})


def _meta(data: dict) -> dict:
    loc = _loc(data)
    m = loc.get("meta_data")
    return m if isinstance(m, dict) else {}


SENSOR_DESCRIPTIONS: tuple[One2TrackSensorDescription, ...] = (
    One2TrackSensorDescription(
        key="battery",
        translation_key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _loc(d).get("battery_percentage"),
    ),
    One2TrackSensorDescription(
        key="sim_balance",
        translation_key="sim_balance",
        native_unit_of_measurement="EUR",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:sim",
        value_fn=lambda d: round(c / 100, 2)
        if (c := d.get("simcard", {}).get("balance_cents")) is not None
        else None,
    ),
    One2TrackSensorDescription(
        key="last_location_update",
        translation_key="last_location_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: datetime.fromisoformat(v)
        if (v := _loc(d).get("last_location_update"))
        else None,
    ),
    One2TrackSensorDescription(
        key="last_communication",
        translation_key="last_communication",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: datetime.fromisoformat(v)
        if (v := _loc(d).get("last_communication"))
        else None,
    ),
    One2TrackSensorDescription(
        key="signal_strength",
        translation_key="signal_strength",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:signal",
        value_fn=lambda d: _loc(d).get("signal_strength"),
    ),
    One2TrackSensorDescription(
        key="satellite_count",
        translation_key="satellite_count",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:satellite-variant",
        value_fn=lambda d: _loc(d).get("satellite_count"),
    ),
    One2TrackSensorDescription(
        key="speed",
        translation_key="speed",
        native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: float(v) if (v := _loc(d).get("speed")) is not None else None,
    ),
    One2TrackSensorDescription(
        key="altitude",
        translation_key="altitude",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:altimeter",
        value_fn=lambda d: float(v) if (v := _loc(d).get("altitude")) is not None else None,
    ),
    One2TrackSensorDescription(
        key="steps_today",
        translation_key="steps_today",
        native_unit_of_measurement="steps",
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:shoe-print",
        value_fn=lambda d: _loc(d).get("step_count_day"),
    ),
    One2TrackSensorDescription(
        key="accuracy",
        translation_key="accuracy",
        native_unit_of_measurement=UnitOfLength.METERS,
        device_class=SensorDeviceClass.DISTANCE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:crosshairs-gps",
        value_fn=lambda d: _meta(d).get("accuracy_meters"),
    ),
    One2TrackSensorDescription(
        key="heading",
        translation_key="heading",
        native_unit_of_measurement="\u00b0",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:compass",
        value_fn=lambda d: _meta(d).get("course"),
    ),
    One2TrackSensorDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=["online", "offline"],
        icon="mdi:access-point-network",
        value_fn=lambda d: v.lower() if (v := d.get("status")) else None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: One2TrackConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up One2Track sensor entities."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        One2TrackSensor(coordinator, device["uuid"], desc)
        for device in coordinator.device_list
        for desc in SENSOR_DESCRIPTIONS
    )


class One2TrackSensor(One2TrackEntity, SensorEntity):
    """A sensor for One2Track device data."""

    entity_description: One2TrackSensorDescription

    def __init__(
        self,
        coordinator: One2TrackCoordinator,
        uuid: str,
        description: One2TrackSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, uuid)
        self.entity_description = description
        self._attr_unique_id = f"{uuid}_{description.key}"

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self.entity_description.value_fn(self._data)
