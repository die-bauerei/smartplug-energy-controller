from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

import asyncio

@dataclass()
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

    def __len__(self) -> int:
        return len(self._values)
    
    def __getitem__(self, index: int) -> ValueEntry:
        return self._values[index]

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
            # TODO: rm outliers (e.g. coffee machine has been used)
            weighted_sum : float = 0
            for index in range(1, len(self._values)):
                weighted_sum+=self._values[index].value*(self._values[index].timestamp - self._values[index-1].timestamp).total_seconds()
            return weighted_sum/(self._values[-1].timestamp - self._values[0].timestamp).total_seconds()
