from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Any, Dict, Protocol
from logging import Logger
import aiohttp

from smartplug_energy_controller.config import OpenHabConnectionConfig

@dataclass(frozen=True)
class SavingFromPlug():
    watt_value : float
    valid_until_time : datetime

class SavingsFromPlugsTurnedOff():
    def __init__(self) -> None:
        self._savings : Dict[str, SavingFromPlug] = {}

    def value(self, timestamp : datetime) -> float:
        # trim dict according to given timestamp
        while self._savings and list(self._savings.values())[0].valid_until_time < timestamp:
            self._savings.pop(list(self._savings.keys())[0])
        return sum([saving.watt_value for saving in self._savings.values()])
    
    def remove(self, plug_uuid : str) -> None:
        if plug_uuid in self._savings: 
            self._savings.pop(plug_uuid)

    def add(self, plug_uuid : str, watt_value : float, timestamp : datetime, time_delta : timedelta) -> None:
        self._savings[plug_uuid]=SavingFromPlug(watt_value, timestamp + time_delta)

@dataclass(frozen=True)
class ValueEntry:
    value : float
    timestamp : datetime

@dataclass()
class Ratio:
    threshold_value : float
    less_threshold_ratio : float

class RollingValues:
    def __init__(self, window_time_delta : timedelta, init_values : List[ValueEntry] = []) -> None:
        self._time_delta = window_time_delta
        self._values : List[ValueEntry] = init_values.copy()

    def value_count(self) -> int:
        return len(self._values)
    
    def __getitem__(self, index: int) -> ValueEntry:
        return self._values[index]
    
    def time_delta(self) -> timedelta:
        return self._time_delta

    def add(self, value : ValueEntry):
        if len(self._values) != 0:
            assert value.timestamp > self._values[-1].timestamp, "Timestamps must be in ascending order"
        
        # append value and trim list according to time delta
        self._values.append(value)
        while self._values[-1].timestamp - self._values[0].timestamp >= self._time_delta:
            self._values = self._values[1:]

    def ratio(self, threshold_value : float) -> Ratio:
        assert len(self._values) > 1, "Not enough values to calculate ratio"
        values_less_threshold_time_deltas : List[timedelta] = []
        for index, value_entry in enumerate(self._values):
            if index > 0 and value_entry.value < threshold_value:
                values_less_threshold_time_deltas.append(value_entry.timestamp - self._values[index-1].timestamp)
        
        less_threshold_time = sum(values_less_threshold_time_deltas, timedelta())
        window_time = self._values[-1].timestamp - self._values[0].timestamp
        return Ratio(threshold_value, less_threshold_time/window_time)
    
    def mean(self) -> float:
        assert len(self._values) > 1, "Not enough values to calculate mean"
        # TODO: rm outliers?
        weighted_sum : float = 0
        for index in range(1, len(self._values)):
            weighted_sum+=self._values[index].value*(self._values[index].timestamp - self._values[index-1].timestamp).total_seconds()
        return weighted_sum/(self._values[-1].timestamp - self._values[0].timestamp).total_seconds()

class OpenhabConnectionProtocol(Protocol):
    async def post_to_item(self, oh_item_name : str, value : Any) -> bool: ...
        
class OpenhabConnection():
    def __init__(self, oh_con_cfg : OpenHabConnectionConfig, logger : Logger) -> None:
        self._oh_url=oh_con_cfg.oh_url
        self._logger=logger
        auth=aiohttp.BasicAuth(oh_con_cfg.oh_user, oh_con_cfg.oh_password) if oh_con_cfg.oh_user != '' else None
        self._session=aiohttp.ClientSession(auth=auth, headers={'Content-Type': 'text/plain'})

    async def post_to_item(self, oh_item_name : str, value : Any) -> bool:
        try:
            async with self._session.post(url=f"{self._oh_url}/rest/items/{oh_item_name}", data=str(value), ssl=False) as response:
                if response.status != 200:
                    self._logger.warning(f"Failed to post value to openhab item {oh_item_name}. Return code: {response.status}. text: {await response.text()})")
                    return False
        except aiohttp.ClientError as e:
            self._logger.warning("Caught Exception while posting to openHAB: " + str(e))
            return False
        return True