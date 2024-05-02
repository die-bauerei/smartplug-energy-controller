from logging import Logger

from abc import ABC, abstractmethod
from typing import List, Any, Optional

from plugp100.common.credentials import AuthCredential
from plugp100.new.device_factory import connect, DeviceConnectConfiguration
from plugp100.new.tapoplug import TapoPlug

def _manage_rolling_list(list : List[Any], max_value_count : int, new_end_value : Any) -> List[Any]:
    if len(list) < max_value_count:
        return list+[new_end_value]
    else:
        return list[1:]+[new_end_value]

class PlugController(ABC):
    def __init__(self, logger : Logger, watt_consumption_eval_count : int, expected_watt_consumption : float) -> None:
        self._logger=logger
        self._watt_consumption_eval_count=watt_consumption_eval_count
        assert expected_watt_consumption >= 10
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

    async def add_watt_consumption(self, value : float) -> None:
        try:
            self._watt_consumption_values=_manage_rolling_list(self._watt_consumption_values, 
                                                            self._watt_consumption_eval_count, 
                                                            value)

            await self.update()
            if len(self._watt_consumption_values) == self._watt_consumption_eval_count:
                consumption_threshold=self._expected_watt_consumption if self.is_on() else 10
                values_less_threshold=[value for value in self._watt_consumption_values if value < consumption_threshold]
                if len(values_less_threshold) > self._watt_consumption_eval_count/2:
                    await self.turn_on()
                else:
                    await self.turn_off()
        except Exception as e:
            # Just log as warning since the plug could just be unconnected 
            self._logger.warning("Caught Exception while adding watt consumption. About to reset controller now.")
            self.reset()

class TapoPlugController(PlugController):

    def __init__(self, logger : Logger, watt_consumption_eval_count : int, expected_watt_consumption : float,
                tapo_user : str, tapo_passwd : str, tapo_plug_ip : str) -> None:
        super().__init__(logger, watt_consumption_eval_count, expected_watt_consumption)
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