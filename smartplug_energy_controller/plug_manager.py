from __future__ import annotations
import sys
from logging import Logger
from typing import Dict, Union

from .utils import *
from .config import *
from .plug_controller import *

efficiency_tolerance=0.05

class PlugManager():
    def __init__(self, logger : Logger, eval_time_in_min : int, base_load : float = 150, min_expected_freq : timedelta = timedelta(seconds=90)) -> None:
        self._logger=logger
        # Add a dummy value to the rolling watt-obtained values to assure valid state at the beginning
        self._watt_obtained_values=RollingValues(timedelta(minutes=eval_time_in_min),
                                                 [ValueEntry(sys.float_info.max, datetime.now())])
        self._base_load=base_load
        self._min_expected_freq=min_expected_freq
        self._watt_produced : Union[None, float] = None
        self._break_even : Union[None, float] = None
        # compensation for savings since last break-even update due to plugs that have been turned off 
        self._savings_from_plugs_turned_off : SavingsFromPlugsTurnedOff = SavingsFromPlugsTurnedOff()
        self._latest_mean = sys.float_info.max
        self._having_overproduction = False
        self._controllers : Dict[str, PlugController] = {}

    def _add_plug_controller(self, uuid : str, controller : PlugController) -> None:
        self._controllers[uuid]=controller

    async def _current_break_even(self) -> Union[None, float]:
        watt_saving = await self._savings_from_plugs_turned_off.value((await self._watt_obtained_values[-1]).timestamp)
        return self._break_even - watt_saving if self._break_even is not None else None

    def plug(self, plug_uuid : str) -> PlugController:
        return self._controllers[plug_uuid]
    
    async def _handle_turn_on_plug(self) -> None:
        assert self._having_overproduction
        # check plugs in given order (highest prio to lowest prio)
        for uuid, controller in self._controllers.items():
            try:
                if await controller.is_online() and not await controller.is_on():
                    turn_on = True
                    break_even = await self._current_break_even()
                    if self._watt_produced is not None and break_even is not None:
                        efficiency_factor=max(0.0, controller.consumer_efficiency - efficiency_tolerance)
                        turn_on = (self._watt_produced - break_even) > controller.watt_consumed*(1 - efficiency_factor)
                    if turn_on:
                        await controller.turn_on()
                    
                    # NOTE: Only check the controller which is off and has the highest prio
                    # Implementing consumer balancing would be to much overhead 
                    break                        
            except Exception as e:
                # Just log as warning since the plug could just be unconnected 
                self._logger.warning(f"Caught Exception while turning on Plug with UUID {uuid}. Exception message: {e}")
                self._logger.warning("About to reset controller now.")
                controller.reset()

    async def _handle_turn_off_plug(self) -> None:
        assert not self._having_overproduction
        controllers_on_count=len([controller for controller in self._controllers.values() if controller.is_on()])
        # check plugs in reversed order (lowest prio to highest prio)
        for uuid, controller in reversed(self._controllers.items()):
            try:
                if await controller.is_online() and await controller.is_on():
                    efficiency_factor=min(1.0, controller.consumer_efficiency + efficiency_tolerance)
                    if self._latest_mean > controller.watt_consumed*efficiency_factor:
                        if await controller.turn_off():
                            time_delta = self._watt_obtained_values.time_delta() + controllers_on_count*self._min_expected_freq
                            await self._savings_from_plugs_turned_off.add(controller.watt_consumed*(1 - controller.consumer_efficiency), 
                                                                    (await self._watt_obtained_values[-1]).timestamp,
                                                                    time_delta)

                    # NOTE: Only check the controller which is on and has the lowest prio
                    # Implementing consumer balancing would be to much overhead 
                    break
            except Exception as e:
                # Just log as warning since the plug could just be unconnected 
                self._logger.warning(f"Caught Exception while turning off Plug with UUID {uuid}. Exception message: {e}")
                self._logger.warning("About to reset controller now.")
                controller.reset()

    # TODO: do all calculations in a lock?
    async def _evaluate(self, watt_produced : Union[None, float] = None) -> bool:
        if await self._watt_obtained_values.value_count() < 2:
            self._logger.error(f"Not enough values in the evaluated timeframe of {self._watt_obtained_values.time_delta()}. Make sure to add values more frequently.")
            return False
        if (await self._watt_obtained_values[-1]).timestamp - (await self._watt_obtained_values[-2]).timestamp > self._min_expected_freq:
            self._logger.warning(f"Values are not added frequently enough. The minimum frequency is {self._min_expected_freq}. Some features might not work as intended.")
        had_overprotection = self._having_overproduction
        self._latest_mean = await self._watt_obtained_values.mean()
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
            self._logger.info(f"Break-even value has been updated from {old_break_even} to {self._break_even}")
        self._watt_produced=watt_produced
        return True

    async def add_smart_meter_values(self, watt_obtained_from_provider : float, watt_produced : Union[None, float] = None, timestamp : Union[None, datetime] = None):
        await self._watt_obtained_values.add(ValueEntry(watt_obtained_from_provider, timestamp if timestamp else datetime.now()))
        self._logger.debug(f"Added values: watt_obtained_from_provider={watt_obtained_from_provider}, watt_produced={watt_produced}")
        if await self._evaluate(watt_produced):
            await self._handle_turn_on_plug() if self._having_overproduction else await self._handle_turn_off_plug()

    @staticmethod
    def create(logger : Logger, cfg_parser : ConfigParser) -> PlugManager:
        manager=PlugManager(logger, cfg_parser.general.eval_time_in_min)
        for uuid in cfg_parser.plug_uuids:
            manager._add_plug_controller(uuid, TapoPlugController(logger, cfg_parser.plug(uuid)))
            logger.info(f"Added Tapo Plug Controller for plug with uuid {uuid} using these config values:")
            logger.info(cfg_parser.plug(uuid))
        return manager