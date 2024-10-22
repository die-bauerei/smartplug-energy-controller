from logging import Logger

from abc import ABC, abstractmethod
from functools import cached_property
from typing import Optional, Dict

from plugp100.common.credentials import AuthCredential
from plugp100.new.device_factory import connect, DeviceConnectConfiguration
from plugp100.new.tapoplug import TapoPlug

from smartplug_energy_controller.config import *
from smartplug_energy_controller import get_oh_connection

import asyncio

class PlugController(ABC):
    def __init__(self, logger : Logger, plug_cfg : SmartPlugConfig) -> None:
        self._logger=logger
        assert plug_cfg.expected_consumption_in_watt >= 1
        assert plug_cfg.consumer_efficiency > 0 and plug_cfg.consumer_efficiency < 1
        self._watt_consumed_at_plug : float = plug_cfg.expected_consumption_in_watt
        self._consumer_efficiency=plug_cfg.consumer_efficiency
        self._enabled=plug_cfg.enabled
        self._propose_to_turn_on=False
        self._lock : asyncio.Lock = asyncio.Lock()

    @property
    async def state(self):
        state : Dict[str, str] = {}
        async with self._lock:
            state['enabled'] = 'On' if self._enabled else 'Off'
            state['proposed_state'] = 'On' if self._propose_to_turn_on else 'Off'
            state['actual_state'] = 'On' if await self.is_on() else 'Off'
            state['watt_consumed_at_plug'] = str(self._watt_consumed_at_plug)
        return state

    @property
    def enabled(self) -> bool:
        return self._enabled
    
    async def set_enabled(self, enabled : bool) -> None:
        async with self._lock:
            self._enabled = enabled

    @property
    def watt_consumed(self) -> float:
        return self._watt_consumed_at_plug

    @property
    def consumer_efficiency(self) -> float:
        return self._consumer_efficiency

    @cached_property
    @abstractmethod
    def info(self) -> Dict[str, str]:
        pass

    @abstractmethod
    async def is_online(self) -> bool:
        pass

    @abstractmethod
    def reset(self) -> None:
        pass

    @abstractmethod
    async def is_on(self) -> bool:
        pass

    async def turn_on(self) -> bool:
        self._propose_to_turn_on=True
        return True

    async def turn_off(self) -> bool:
        self._propose_to_turn_on=False
        return True

class TapoPlugController(PlugController):

    def __init__(self, logger : Logger, plug_cfg : TapoSmartPlugConfig) -> None:
        super().__init__(logger, plug_cfg)
        self._cfg=plug_cfg
        assert self._cfg.id != ''
        assert self._cfg.auth_user != ''
        assert self._cfg.auth_passwd != ''
        self._plug : Optional[TapoPlug] = None

    @cached_property
    def info(self) -> Dict[str, str]:
        info : Dict[str, str] = {}
        info['type'] = 'tapo'
        info['id'] = self._cfg.id
        info['user'] = self._cfg.auth_user
        info['passwd'] = self._cfg.auth_passwd
        return info

    async def is_online(self) -> bool:
        try:
            await self._update()
            return True
        except Exception as e:
            return False

    def reset(self) -> None:
        self._plug = None

    async def _update(self) -> None:
        if self._plug is None:
            credentials = AuthCredential(self._cfg.auth_user, self._cfg.auth_passwd)
            device_configuration = DeviceConnectConfiguration(
                host=self._cfg.id,
                credentials=credentials
            )
            self._plug = await connect(device_configuration) # type: ignore
        await self._plug.update() # type: ignore

    async def is_on(self) -> bool:
        try:
            await self._update()
            return self._plug is not None and self._plug.is_on
        except Exception as e:
            # return false in case no connection can be established
            return False

    async def turn_on(self) -> bool:
        base_rc = await super().turn_on()
        if base_rc and self._plug is not None:
            await self._plug.turn_on()
            self._logger.info("Turned Tapo Plug on")
            return await self.is_on()
        return False

    async def turn_off(self) -> bool:
        base_rc = await super().turn_off()
        if base_rc and self._plug is not None:
            await self._plug.turn_off()
            self._logger.info("Turned Tapo Plug off")
            return not await self.is_on()
        return False
    
class OpenHabPlugController(PlugController):

    def __init__(self, logger : Logger, plug_cfg : OpenHabSmartPlugConfig) -> None:
        super().__init__(logger, plug_cfg)
        assert get_oh_connection() is not None
        self._plug_cfg=plug_cfg
        assert self._plug_cfg.oh_thing_name != ''
        assert self._plug_cfg.oh_switch_item_name != ''
        assert self._plug_cfg.oh_power_consumption_item_name != ''
        self._is_on = False
        self._online = True

    @cached_property
    def info(self) -> Dict[str, str]:
        info : Dict[str, str] = {}
        info['type'] = 'openhab'
        info['oh_thing_name'] = self._plug_cfg.oh_thing_name
        info['oh_switch_item_name'] = self._plug_cfg.oh_switch_item_name
        info['oh_power_consumption_item_name'] = self._plug_cfg.oh_power_consumption_item_name
        info['oh_automation_enabled_switch_item_name'] = self._plug_cfg.oh_automation_enabled_switch_item_name
        return info

    def reset(self) -> None:
        pass

    async def is_online(self) -> bool:
        return self._online

    async def is_on(self) -> bool:
        return self._is_on
    
    async def turn_on(self) -> bool:
        base_rc = await super().turn_on()
        oh_connection = get_oh_connection()
        if oh_connection is None:
            self._logger.error("OpenHabConnection is not set. Cannot turn on plug")
        elif base_rc:
            success=await oh_connection.post_to_item(self._plug_cfg.oh_switch_item_name, 'ON')
            if success:
                self._logger.info("Turned OpenHabPlug Plug on")
            return success
        return False

    async def turn_off(self) -> bool:
        base_rc = await super().turn_off()
        oh_connection = get_oh_connection()
        if oh_connection is None:
            self._logger.error("OpenHabConnection is not set. Cannot turn off plug")
        elif base_rc:
            success=await oh_connection.post_to_item(self._plug_cfg.oh_switch_item_name, 'OFF')
            if success:
                self._logger.info("Turned OpenHabPlug Plug off")
            return success
        return False
    
    async def update_values(self, watt_consumed_at_plug: float, online : bool, is_on : bool) -> None:
        async with self._lock:
            self._watt_consumed_at_plug=watt_consumed_at_plug
            self._online=online
            self._is_on=is_on
        self._logger.debug(f"Updated values of OpenHabPlugController to {watt_consumed_at_plug}, {online}, {is_on}")