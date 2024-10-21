from __future__ import annotations
import sys
from logging import Logger
from typing import Dict, Union, cast

import asyncio

from smartplug_energy_controller.utils import *
from smartplug_energy_controller.config import *
from smartplug_energy_controller.plug_controller import *

class PlugManager():
    _efficiency_tolerance=0.05

    def __init__(self, logger : Logger, eval_time_in_min : int, min_expected_freq : timedelta = timedelta(seconds=90)) -> None:
        self._logger=logger
        # Add a dummy value to the rolling watt-obtained values to assure valid state at the beginning
        self._watt_obtained_values=RollingValues(timedelta(minutes=eval_time_in_min),
                                                 [ValueEntry(sys.float_info.max, datetime.now())])
        self._base_load=sys.float_info.max
        self._min_expected_freq=min_expected_freq
        self._watt_produced : Union[None, float] = None
        self._break_even : Union[None, float] = None
        self._latest_mean = sys.float_info.max
        self._having_overproduction = False
        self._controllers : Dict[str, PlugController] = {}
        self._lock : asyncio.Lock = asyncio.Lock()

    @property
    async def state(self):
        state : Dict[str, float] = {}
        async with self._lock:
            state['base_load'] = self._base_load
            state['min_expected_freq_in_sec'] = self._min_expected_freq.total_seconds()
            if self._watt_produced is not None:
                state['watt_produced'] = self._watt_produced
            if self._break_even is not None:
                state['break_even'] = self._break_even
            state['latest_mean'] = self._latest_mean
        return state
    
    async def reset_base_load(self) -> None:
        async with self._lock:
             self._base_load=sys.float_info.max

    def _add_plug_controller(self, uuid : str, controller : PlugController) -> None:
        self._controllers[uuid]=controller

    def plug(self, plug_uuid : str) -> PlugController:
        return self._controllers[plug_uuid]

    def plugs(self) -> List[PlugController]:
        return list(self._controllers.values())
    
    async def _handle_turn_on_plug(self) -> None:
        assert self._having_overproduction
        # check plugs in given order (highest prio to lowest prio)
        for uuid, controller in self._controllers.items():
            try:
                if controller.enabled and await controller.is_online() and not await controller.is_on():
                    turn_on = True
                    if self._watt_produced is not None and self._break_even is not None:
                        efficiency_factor=max(0.0, controller.consumer_efficiency - PlugManager._efficiency_tolerance)
                        turn_on = (self._watt_produced - self._break_even) > controller.watt_consumed*(1 - efficiency_factor)
                    if turn_on:
                        # if turning on fails due to connection issues -> continue with next plug
                        # Usually the plug should not be online in this case, but having this additional check makes it more robust.   
                        if not await controller.turn_on():
                            continue
                    # NOTE: Only check the controller which is off and has the highest prio
                    # Implementing consumer balancing would be to much overhead. 
                    break
            except Exception as e:
                # Just log as warning since the plug could just be unconnected 
                self._logger.warning(f"Caught Exception while turning on Plug with UUID {uuid}. Exception message: {e}")
                self._logger.warning("About to reset controller now.")
                controller.reset()

    async def _handle_turn_off_plug(self) -> None:
        assert not self._having_overproduction
        # check plugs in reversed order (lowest prio to highest prio)
        for uuid, controller in reversed(self._controllers.items()):
            try:
                if controller.enabled and await controller.is_online() and await controller.is_on():
                    efficiency_factor=min(1.0, controller.consumer_efficiency + PlugManager._efficiency_tolerance)
                    if self._latest_mean > controller.watt_consumed*efficiency_factor:
                        # if turning off fails due to connection issues -> continue with next plug
                        # Usually the plug should not be online in this case, but having this additional check makes it more robust.   
                        if not await controller.turn_off():
                            continue
                    # NOTE: Only check the controller which is on and has the lowest prio
                    # Implementing consumer balancing would be to much overhead 
                    break
            except Exception as e:
                # Just log as warning since the plug could just be unconnected 
                self._logger.warning(f"Caught Exception while turning off Plug with UUID {uuid}. Exception message: {e}")
                self._logger.warning("About to reset controller now.")
                controller.reset()

    def _evaluate(self, watt_produced : Union[None, float] = None) -> bool:
        if self._watt_obtained_values.value_count() < 2:
            self._logger.error(f"Not enough values in the evaluated timeframe of {self._watt_obtained_values.time_delta()}. Make sure to add values more frequently.")
            return False
        if self._watt_obtained_values[-1].timestamp - self._watt_obtained_values[-2].timestamp > self._min_expected_freq:
            self._logger.warning(f"Values are not added frequently enough. The minimum frequency is {self._min_expected_freq}. Some features might not work as intended.")
        had_overprotection = self._having_overproduction
        self._latest_mean = self._watt_obtained_values.mean()
        self._base_load = min(self._base_load, self._latest_mean + (watt_produced if watt_produced is not None else 0))
        self._having_overproduction = self._latest_mean < 1
        old_break_even = self._break_even
        if not had_overprotection and self._having_overproduction:
            if watt_produced is not None and self._watt_produced is not None:
                self._break_even = (self._watt_produced+watt_produced)/2
            elif watt_produced is not None:
                self._break_even = watt_produced
            else:
                self._break_even = None
            self._logger.info(f"Break-even value has been updated from {old_break_even} to {self._break_even}")
        elif had_overprotection and self._having_overproduction and self._break_even is not None:
            # decrease break-even value when overproduction is still present
            self._break_even = max(self._base_load, self._break_even*0.975)
            if old_break_even != self._break_even:
                self._logger.info(f"Break-even value has been updated from {old_break_even} to {self._break_even}")
        self._watt_produced=watt_produced
        return True

    async def add_smart_meter_values(self, watt_obtained_from_provider : float, watt_produced : Union[None, float] = None, timestamp : Union[None, datetime] = None):
        async with self._lock:
            self._watt_obtained_values.add(ValueEntry(watt_obtained_from_provider, timestamp if timestamp else datetime.now()))
            self._logger.debug(f"Added values: watt_obtained_from_provider={watt_obtained_from_provider}, watt_produced={watt_produced}")
            if self._evaluate(watt_produced):
                await self._handle_turn_on_plug() if self._having_overproduction else await self._handle_turn_off_plug()

    @staticmethod
    def create(logger : Logger, cfg_parser : ConfigParser) -> PlugManager:
        manager=PlugManager(logger, cfg_parser.general.eval_time_in_min)
        for uuid in cfg_parser.plug_uuids:
            plug_cfg = cfg_parser.plug(uuid)
            plug_controller : Union[OpenHabPlugController, TapoPlugController, None]=None
            if plug_cfg.type == 'openhab':
                plug_cfg = cast(OpenHabSmartPlugConfig, plug_cfg)
                plug_controller = OpenHabPlugController(logger, plug_cfg)
            else:
                plug_cfg = cast(TapoSmartPlugConfig, plug_cfg)
                plug_controller = TapoPlugController(logger, plug_cfg)
            manager._add_plug_controller(uuid, plug_controller)
            logger.info(f"Added Plug Controller for plug with uuid {uuid} using these config values:")
            logger.info(plug_cfg)
        return manager