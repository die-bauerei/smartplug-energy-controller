from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

import asyncio

@dataclass(frozen=True)
class SavingFromPlug():
    watt_value : float
    valid_until_time : datetime

class SavingsFromPlugsTurnedOff():
    def __init__(self) -> None:
        self._savings : List[SavingFromPlug] = []
        self._lock : asyncio.Lock = asyncio.Lock()

    async def value(self, timestamp : datetime) -> float:
        async with self._lock:
            if self._savings:
                # trim list according to given timestamp
                while self._savings[0].valid_until_time < timestamp:
                    self._savings = self._savings[1:]
            return sum([saving.watt_value for saving in self._savings])

    async def add(self, watt_value : float, timestamp : datetime, time_delta : timedelta) -> None:
        async with self._lock:
            self._savings.append(SavingFromPlug(watt_value, timestamp + time_delta))

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
        self._lock : asyncio.Lock = asyncio.Lock()

    async def value_count(self) -> int:
        async with self._lock:
            return len(self._values)
    
    async def __getitem__(self, index: int) -> ValueEntry:
        async with self._lock:
            return self._values[index]
    
    def time_delta(self) -> timedelta:
        return self._time_delta

    async def add(self, value : ValueEntry):
        if len(self._values) != 0:
            assert value.timestamp > self._values[-1].timestamp, "Timestamps must be in ascending order"
        
        # append value and trim list according to time delta
        async with self._lock:
            self._values.append(value)
            while self._values[-1].timestamp - self._values[0].timestamp >= self._time_delta:
                self._values = self._values[1:]

    async def ratio(self, threshold_value : float) -> Ratio:
        assert len(self._values) > 1, "Not enough values to calculate ratio"
        async with self._lock:
            values_less_threshold_time_deltas : List[timedelta] = []
            for index, value_entry in enumerate(self._values):
                if index > 0 and value_entry.value < threshold_value:
                    values_less_threshold_time_deltas.append(value_entry.timestamp - self._values[index-1].timestamp)
            
            less_threshold_time = sum(values_less_threshold_time_deltas, timedelta())
            window_time = self._values[-1].timestamp - self._values[0].timestamp
        return Ratio(threshold_value, less_threshold_time/window_time)
    
    async def mean(self) -> float:
        assert len(self._values) > 1, "Not enough values to calculate mean"
        async with self._lock:
            # TODO: rm outliers?
            weighted_sum : float = 0
            for index in range(1, len(self._values)):
                weighted_sum+=self._values[index].value*(self._values[index].timestamp - self._values[index-1].timestamp).total_seconds()
            return weighted_sum/(self._values[-1].timestamp - self._values[0].timestamp).total_seconds()
