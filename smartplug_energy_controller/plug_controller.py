import sys

from logging import Logger

from abc import ABC, abstractmethod
from typing import Optional, Union

from plugp100.common.credentials import AuthCredential
from plugp100.new.device_factory import connect, DeviceConnectConfiguration
from plugp100.new.tapoplug import TapoPlug

from .utils import *
from .config import SmartPlugConfig

class PlugController(ABC):
    def __init__(self, logger : Logger, plug_cfg : SmartPlugConfig) -> None:
        self._logger=logger
        assert plug_cfg.eval_time_in_min > 0
        assert plug_cfg.expected_consumption_in_watt >= 1
        assert plug_cfg.consumer_efficiency > 0 and plug_cfg.consumer_efficiency < 1
        self._cfg=plug_cfg
        # Add a dummy value to the rolling values to assure valid state at the beginning
        self._rolling_values=RollingValues(timedelta(minutes=plug_cfg.eval_time_in_min))
        self._rolling_values.add(ValueEntry(sys.float_info.max, datetime.now()))
        self._propose_to_turn_on=False

    @property
    def state_proposal(self):
        return {'proposed_state': 'On'} if self._propose_to_turn_on else {'proposed_state': 'Off'}

    @abstractmethod
    def reset(self) -> None:
        pass

    @abstractmethod
    async def update(self) -> None:
        pass

    @abstractmethod
    async def is_on(self) -> bool:
        pass

    @abstractmethod
    async def turn_on(self) -> None:
        pass

    @abstractmethod
    async def turn_off(self) -> None:
        pass

    async def update_values(self, watt_obtained_from_provider: float, watt_consumed_at_plug: float, 
                            timestamp : Union[None, datetime] = None) -> None:
        try:
            self._rolling_values.add(ValueEntry(watt_obtained_from_provider, timestamp if timestamp else datetime.now()))
            await self.update()
            if len(self._rolling_values) > 1:
                obtained_from_provider_threshold=watt_consumed_at_plug*self._cfg.consumer_efficiency if await self.is_on() else 1
                ratio=self._rolling_values.ratio(obtained_from_provider_threshold)
                if ratio.less_threshold_ratio > 0.5:
                    await self.turn_on()
                    self._propose_to_turn_on=True
                else:
                    await self.turn_off()
                    self._propose_to_turn_on=False
            else:
                self._logger.warning("Not enough values in the evaluated timeframe. Make sure to add values more frequently.")
            self._logger.debug(f"Updated values to: watt_obtained_from_provider={watt_obtained_from_provider}, watt_consumed_at_plug={watt_consumed_at_plug}")
        except Exception as e:
            # Just log as warning since the plug could just be unconnected 
            self._logger.warning("Caught Exception while adding watt consumption: " + str(e))
            self._logger.warning("About to reset controller now.")
            self.reset()

class TapoPlugController(PlugController):

    def __init__(self, logger : Logger, plug_cfg : SmartPlugConfig) -> None:
        super().__init__(logger, plug_cfg)
        assert self._cfg.id != ''
        assert self._cfg.auth_user != ''
        assert self._cfg.auth_passwd != ''
        self._plug : Optional[TapoPlug] = None

    def reset(self) -> None:
        self._plug = None

    async def update(self) -> None:
        if self._plug is None:
            credentials = AuthCredential(self._cfg.auth_user, self._cfg.auth_passwd)
            device_configuration = DeviceConnectConfiguration(
                host=self._cfg.id,
                credentials=credentials
            )
            self._plug = await connect(device_configuration) # type: ignore
        await self._plug.update()

    async def is_on(self) -> bool:
        await self.update()
        return self._plug is not None and self._plug.is_on

    async def turn_on(self) -> None:
        if not await self.is_on() and self._plug is not None:
            await self._plug.turn_on()
            self._logger.info("Turned Tapo Plug on")

    async def turn_off(self) -> None:
        if await self.is_on() and self._plug is not None:
            await self._plug.turn_off()
            self._logger.info("Turned Tapo Plug off")