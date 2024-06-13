import sys

from logging import Logger

from abc import ABC, abstractmethod
from typing import List, Optional, Union

from plugp100.common.credentials import AuthCredential
from plugp100.new.device_factory import connect, DeviceConnectConfiguration
from plugp100.new.tapoplug import TapoPlug

from .utils import *

class PlugController(ABC):
    def __init__(self, logger : Logger, eval_time_in_min : int, expected_watt_consumption : float, consumer_efficiency : float) -> None:
        self._logger=logger
        assert eval_time_in_min > 0
        # Add a dummy value to the rolling values to assure valid state at the beginning
        self._rolling_values=RollingValues(timedelta(minutes=eval_time_in_min))
        self._rolling_values.add(ValueEntry(sys.float_info.max, datetime.now()))
        assert expected_watt_consumption >= 1
        self._consumer_efficiency=consumer_efficiency
        assert self._consumer_efficiency > 0 and self._consumer_efficiency < 1
        self._expected_watt_consumption=expected_watt_consumption
        self._watt_consumption_values : List[float] = []

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

    async def add_obtained_watt_from_provider(self, value : float, timestamp : Union[None, datetime] = None) -> None:
        try:
            self._rolling_values.add(ValueEntry(value, timestamp if timestamp else datetime.now()))
            await self.update()
            if len(self._rolling_values) > 1:
                obtained_from_provider_threshold=self._expected_watt_consumption*self._consumer_efficiency if await self.is_on() else 1
                ratio=self._rolling_values.ratio(obtained_from_provider_threshold)
                await self.turn_on() if ratio.less_threshold_ratio > 0.5 else await self.turn_off()
            else:
                self._logger.warning("Not enough values in the evaluated timeframe. Make sure to add values more frequently.")
        except Exception as e:
            # Just log as warning since the plug could just be unconnected 
            self._logger.warning("Caught Exception while adding watt consumption: " + str(e))
            self._logger.warning("About to reset controller now.")
            self.reset()

class OpenHabPlugController(PlugController):
    def __init__(self, logger: Logger, eval_time_in_min : int, expected_watt_consumption: float, consumer_efficiency: float,
                 oh_user : str, oh_passwd : str, oh_switch_item_url : str) -> None:
        super().__init__(logger, eval_time_in_min, expected_watt_consumption, consumer_efficiency)

class TapoPlugController(PlugController):

    def __init__(self, logger : Logger, eval_time_in_min : int, expected_watt_consumption : float,  consumer_efficiency : float,
                tapo_user : str, tapo_passwd : str, tapo_plug_ip : str) -> None:
        super().__init__(logger, eval_time_in_min, expected_watt_consumption, consumer_efficiency)
        self._tapo_user=tapo_user
        self._tapo_passwd=tapo_passwd
        self._tapo_plug_ip=tapo_plug_ip
        assert self._tapo_user != ''
        assert self._tapo_passwd != ''
        assert self._tapo_plug_ip != ''
        self._plug : Optional[TapoPlug] = None

    def reset(self) -> None:
        self._plug = None

    async def update(self) -> None:
        if self._plug is None:
            credentials = AuthCredential(self._tapo_user, self._tapo_passwd)
            device_configuration = DeviceConnectConfiguration(
                host=self._tapo_plug_ip,
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