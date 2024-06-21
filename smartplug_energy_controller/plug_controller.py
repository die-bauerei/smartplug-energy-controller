from logging import Logger

from abc import ABC, abstractmethod
from typing import Optional, Dict

from plugp100.common.credentials import AuthCredential
from plugp100.new.device_factory import connect, DeviceConnectConfiguration
from plugp100.new.tapoplug import TapoPlug

from .utils import *
from .config import SmartPlugConfig

class PlugController(ABC):
    def __init__(self, logger : Logger, plug_cfg : SmartPlugConfig) -> None:
        self._logger=logger
        self._cfg=plug_cfg
        assert plug_cfg.expected_consumption_in_watt >= 1
        assert plug_cfg.consumer_efficiency > 0 and plug_cfg.consumer_efficiency < 1
        self._watt_consumed_at_plug : float = plug_cfg.expected_consumption_in_watt
        self._consumer_efficiency=plug_cfg.consumer_efficiency
        self._propose_to_turn_on=False

    @property
    async def state(self):
        state : Dict[str, str] = {}
        state['proposed_state'] = 'On' if self._propose_to_turn_on else 'Off'
        state['actual_state'] = 'On' if await self.is_on() else 'Off'
        return state

    @property
    def watt_consumed(self) -> float:
        return self._watt_consumed_at_plug

    @property
    def consumer_efficiency(self) -> float:
        return self._consumer_efficiency

    @abstractmethod
    async def is_online(self) -> bool:
        pass

    @abstractmethod
    def reset(self) -> None:
        pass

    @abstractmethod
    async def is_on(self) -> bool:
        pass

    async def turn_on(self) -> None:
        self._propose_to_turn_on=True

    async def turn_off(self) -> None:
        self._propose_to_turn_on=False

    def update_values(self, watt_consumed_at_plug: float) -> None:
        self._watt_consumed_at_plug=watt_consumed_at_plug

class TapoPlugController(PlugController):

    def __init__(self, logger : Logger, plug_cfg : SmartPlugConfig) -> None:
        super().__init__(logger, plug_cfg)
        assert self._cfg.id != ''
        assert self._cfg.auth_user != ''
        assert self._cfg.auth_passwd != ''
        self._plug : Optional[TapoPlug] = None

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

    async def turn_on(self) -> None:
        await super().turn_on()
        if not await self.is_on() and self._plug is not None:
            await self._plug.turn_on()
            self._logger.info("Turned Tapo Plug on")

    async def turn_off(self) -> None:
        await super().turn_off()
        if await self.is_on() and self._plug is not None:
            await self._plug.turn_off()
            self._logger.info("Turned Tapo Plug off")