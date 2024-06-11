from logging import Logger

from abc import ABC, abstractmethod
from typing import List, Any, Tuple, Optional

from datetime import datetime, timedelta
import time

from redis import Redis
from redis.commands.timeseries import TimeSeries
from fastapi import FastAPI, Request, HTTPException
from functools import cached_property

from plugp100.common.credentials import AuthCredential
from plugp100.new.device_factory import connect, DeviceConnectConfiguration
from plugp100.new.tapoplug import TapoPlug

# TODO: use a redis timeseries db: https://redis.io/docs/latest/develop/data-types/timeseries/
# https://redis-py.readthedocs.io/en/stable/examples/timeseries_examples.html
def _manage_rolling_list(list : List[Any], max_value_count : int, new_end_value : Any) -> List[Any]:
    if len(list) == 0:
        return [new_end_value]*max_value_count
    elif len(list) < max_value_count:
        return list+[new_end_value]
    else:
        return list[1:]+[new_end_value]

class PlugController(ABC):
    def __init__(self, logger : Logger, watt_consumption_eval_count : int, expected_watt_consumption : float, consumer_efficiency : float,
                 redis_url : str) -> None:
        self._logger=logger
        self._watt_consumption_eval_count=watt_consumption_eval_count
        assert expected_watt_consumption >= 1
        self._consumer_efficiency=consumer_efficiency
        assert self._consumer_efficiency > 0 and self._consumer_efficiency < 1
        self._expected_watt_consumption=expected_watt_consumption
        self._redis_ts : TimeSeries = Redis.from_url(redis_url).ts()
        self._redis_ts.create("obtained_watt")

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

    def _watt_values_from_redis_ts(self) -> List[Tuple[int, float]]:
        time_end=datetime.now()
        # expect, that a new value has been added at least ones a minute
        time_start=time_end-timedelta(minutes=self._watt_consumption_eval_count+1)
        time_end_in_millisec=int(time.mktime(time_end.timetuple())*1000)
        time_start_in_millisec=int(time.mktime(time_start.timetuple())*1000)
        watt_values=self._redis_ts.range("obtained_watt", time_start_in_millisec, time_end_in_millisec)
        return watt_values

    async def add_watt_consumption(self, value : float) -> None:
        try:
            self._redis_ts.add("obtained_watt", "*", value)
            self._logger.debug(f"Added watt consumption value {value} to redis timeseries.")
            watt_values_ts=self._watt_values_from_redis_ts()
            if len(watt_values_ts) < self._watt_consumption_eval_count:
                self._logger.warning(f"Only {len(watt_values_ts)} values found in the last {self._watt_consumption_eval_count+1} minutes.\n" 
                                     f"Expected at least {self._watt_consumption_eval_count}.")
                return
            # only consider the last n values for evaluation
            watt_values_ts=watt_values_ts[-self._watt_consumption_eval_count:]

            await self.update()
            obtained_from_provider_threshold=self._expected_watt_consumption*self._consumer_efficiency if await self.is_on() else 1
            values_less_threshold=[value[1] for value in watt_values_ts if value[1] < obtained_from_provider_threshold]
            self._logger.debug(f"{len(values_less_threshold)} values are less then computed threshold of {obtained_from_provider_threshold}")
            if len(values_less_threshold) > self._watt_consumption_eval_count/2:
                await self.turn_on()
            else:
                await self.turn_off()
        except Exception as e:
            # Just log as warning since the plug could just be unconnected 
            self._logger.warning("Caught Exception while adding watt consumption. About to reset controller now.")
            self.reset()

class TapoPlugController(PlugController):

    def __init__(self, logger : Logger, watt_consumption_eval_count : int, expected_watt_consumption : float,  consumer_efficiency : float,
                redis_url : str, tapo_user : str, tapo_passwd : str, tapo_plug_ip : str) -> None:
        super().__init__(logger, watt_consumption_eval_count, expected_watt_consumption, consumer_efficiency, redis_url)
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