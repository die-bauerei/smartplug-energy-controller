from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

@dataclass()
class ValueEntry:
    value : float
    timestamp : datetime

@dataclass()
class Ratio:
    threshold_value : float
    less_threshold_ratio : float

class RollingValues:
    def __init__(self, window_time_delta : timedelta) -> None:
        self._time_delta = window_time_delta
        self._values : List[ValueEntry] = []

    def __len__(self) -> int:
        return len(self._values)
    
    def __getitem__(self, index: int) -> ValueEntry:
        return self._values[index]

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

