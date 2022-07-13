"""Alarm.com thermostat."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging

from pyalarmdotcomajax.errors import UnexpectedDataStructure

from . import BaseDevice
from . import DesiredStateMixin
from . import DeviceType

log = logging.getLogger(__name__)


class Thermostat(DesiredStateMixin, BaseDevice):
    """Represent Alarm.com thermostat element."""

    # fan duration of 0 is indefinite. otherwise value == hours.
    # settable attributes: desiredRts (remote temp sensor), desiredLocalDisplayLockingMode,
    # In identity info, check localizeTempUnitsToCelsius.

    @dataclass
    class ThermostatAttributes(BaseDevice.DeviceAttributes):
        """Thermostat attributes."""

        # Base
        temp_average: int | None  # Temperature from thermostat and all remote sensors, averaged.
        temp_at_tstat: int | None  # Temperature at thermostat only.
        step_value: int | None
        # Fan
        supports_fan_mode: bool | None
        supports_fan_indefinite: bool | None
        supports_fan_circulate_when_off: bool | None
        supported_fan_durations: list[int] | None
        fan_mode: Thermostat.FanMode | None
        fan_duration: int | None
        # Temp
        supports_heat: bool | None
        supports_heat_aux: bool | None
        supports_cool: bool | None
        supports_auto: bool | None
        min_heat_setpoint: int | None
        max_heat_setpoint: int | None
        min_cool_setpoint: int | None
        max_cool_setpoint: int | None
        heat_setpoint: int | None
        cool_setpoint: int | None
        # Humidity
        supports_humidity: bool | None
        humidity: int | None
        # Schedules
        supports_schedules: bool | None
        supports_schedules_smart: bool | None
        schedule_mode: Thermostat.ScheduleMode | None

    class DeviceState(Enum):
        """Enum of thermostat states."""

        # https://www.alarm.com/web/system/assets/customer-ember/enums/ThermostatStatus.js

        UNKNOWN = 0
        OFF = 1
        HEAT = 2
        COOL = 3
        AUTO = 4
        AUX_HEAT = 5

    class FanMode(Enum):
        """Enum of thermostat fan modes."""

        # https://www.alarm.com/web/system/assets/customer-ember/enums/ThermostatFanMode.js

        AUTO_LOW = 0
        ON_LOW = 1
        AUTO_HIGH = 2
        ON_HIGH = 3
        AUTO_MEDIUM = 4
        ON_MEDIUM = 5
        CIRCULATE = 6
        HUMIDITY = 7

    class LockMode(Enum):
        """Enum of thermostat lock modes."""

        # https://www.alarm.com/web/system/assets/customer-ember/enums/ThermostatLock.js

        DISABLED = 0
        ENABLED = 1
        PARTIAL = 2

    class ScheduleMode(Enum):
        """Enum of thermostat programming modes."""

        # https://www.alarm.com/web/system/assets/customer-ember/enums/ThermostatProgrammingMode.js

        MANUAL = 0
        SCHEDULED = 1
        SMART_SCHEDULES = 2

    class SetpointType(Enum):
        """Enum of thermostat setpoint types."""

        FIXED = 0
        AWAY = 1
        HOME = 2
        SLEEP = 3

    class Command(Enum):
        """Commands for ADC lights."""

        SET_STATE = "setState"

    DEVICE_MODELS = {4293: {"manufacturer": "Honeywell", "model": "T6 Pro"}}

    @property
    def available(self) -> bool:
        """Return whether the light can be manipulated."""
        return (
            self._attribs_raw.get("canReceiveCommands", False)
            and self._attribs_raw.get("remoteCommandsEnabled", False)
            and self._attribs_raw.get("hasPermissionToChangeState", False)
            and self.state is not self.DeviceState.UNKNOWN
        )

    @property
    def attributes(self) -> ThermostatAttributes | None:
        """Return thermostat attributes."""

        return self.ThermostatAttributes(
            temp_average=self._get_int("forwardingAmbientTemp"),
            temp_at_tstat=self._get_int("ambientTemp"),
            step_value=self._get_int("setpointOffset"),
            supports_fan_mode=self._get_bool("supportsFanMode"),
            supports_fan_indefinite=self._get_bool("supportsIndefiniteFanOn"),
            supports_fan_circulate_when_off=self._get_bool(
                "supportsCirculateFanModeWhenOff"
            ),
            supported_fan_durations=self._get_list("supportedFanDurations", int),
            fan_mode=self._get_special("fanMode", self.FanMode),
            fan_duration=self._get_int("fanDuration"),
            supports_heat=self._get_bool("supportsHeatMode"),
            supports_heat_aux=self._get_bool("supportsAuxHeatMode"),
            supports_cool=self._get_bool("supportsCoolMode"),
            supports_auto=self._get_bool("supportsAutoMode"),
            min_heat_setpoint=self._get_int("minHeatSetpoint"),
            min_cool_setpoint=self._get_int("minCoolSetpoint"),
            max_heat_setpoint=self._get_int("maxHeatSetpoint"),
            max_cool_setpoint=self._get_int("maxCoolSetpoint"),
            heat_setpoint=self._get_int("heatSetpoint"),
            cool_setpoint=self._get_int("coolSetpoint"),
            supports_humidity=self._get_bool("supportsHumidity"),
            humidity=self._get_int("humidityLevel"),
            supports_schedules=self._get_bool("supportsSchedules"),
            supports_schedules_smart=self._get_bool("supportsSmartSchedules"),
            schedule_mode=self._get_special("scheduleMode", self.ScheduleMode),
        )

    async def async_set_attribute(
        self,
        state: DeviceState | None = None,
        fan: tuple[FanMode, int] | None = None,  # int = duration
        cool_setpoint: int | None = None,
        heat_setpoint: int | None = None,
        schedule_mode: ScheduleMode | None = None,
    ) -> None:
        """Send turn on command with optional brightness."""

        msg_body = {}

        # Make sure we're only being asked to set one attribute at a time.
        if (
            attrib_list := [state, fan, cool_setpoint, heat_setpoint, schedule_mode]
        ).count(None) < len(attrib_list):
            raise UnexpectedDataStructure

        # Build the request body.
        if state:
            msg_body = {"desiredState": state.value}
        elif fan:
            msg_body = {
                "desiredFanMode": self.FanMode(fan[0]).value,
                "desiredFanDuration": fan[1],
            }
        elif cool_setpoint:
            msg_body = {"desiredCoolSetpoint": cool_setpoint}
        elif heat_setpoint:
            msg_body = {"desiredHeatSetpoint": heat_setpoint}
        elif schedule_mode:
            msg_body = {"desiredScheduleMode": schedule_mode.value}

        # Send
        await self._send_action_callback(
            device_type=DeviceType.THERMOSTAT,
            event=self.Command.SET_STATE,
            device_id=self.id_,
            msg_body=msg_body,
        )
