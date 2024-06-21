from __future__ import annotations
import sys
from logging import Logger
from typing import Dict, Union

from .config import *
from .plug_controller import *

class PlugManager():
    def __init__(self, logger : Logger, eval_time_in_min : int) -> None:
        self._logger=logger
        # Add a dummy value to the rolling watt-obtained values to assure valid state at the beginning
        self._watt_obtained_values=RollingValues(timedelta(minutes=eval_time_in_min),
                                                 [ValueEntry(sys.float_info.max, datetime.now())])
        self._watt_produced : Union[None, float] = None
        self._break_even : Union[None, float] = None
        self._latest_mean = sys.float_info.max
        self._having_overproduction = False
        self._controllers : Dict[str, PlugController] = {}

    def _add_plug_controller(self, uuid : str, controller : PlugController) -> None:
        self._controllers[uuid]=controller

    def plug(self, plug_uuid : str) -> PlugController:
        return self._controllers[plug_uuid]
    
    async def _handle_turn_on_plug(self) -> None:
        assert self._having_overproduction
        # check plugs in given order (highest prio to lowest prio)
        for uuid, controller in self._controllers.items():
            try:
                if await controller.is_online() and not await controller.is_on():
                    turn_on = True
                    if self._watt_produced is not None and self._break_even is not None:
                        turn_on = (self._watt_produced - self._break_even) > controller.watt_consumed*(1 - controller.consumer_efficiency)
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
        # check plugs in reversed order (lowest prio to highest prio)
        for uuid, controller in reversed(self._controllers.items()):
            try:
                if await controller.is_online() and await controller.is_on():
                    if self._latest_mean > controller.watt_consumed*controller.consumer_efficiency:
                        await controller.turn_off()

                    # NOTE: Only check the controller which is on and has the lowest prio
                    # Implementing consumer balancing would be to much overhead 
                    break                 
            except Exception as e:
                # Just log as warning since the plug could just be unconnected 
                self._logger.warning(f"Caught Exception while turning off Plug with UUID {uuid}. Exception message: {e}")
                self._logger.warning("About to reset controller now.")
                controller.reset()

    async def _evaluate(self, watt_produced : Union[None, float] = None) -> bool:
        if len(self._watt_obtained_values) < 2:
            self._logger.error("Not enough values in the evaluated timeframe. Make sure to add values more frequently.")
            return False
        had_overprotection = self._having_overproduction
        self._latest_mean = await self._watt_obtained_values.mean()
        self._having_overproduction = self._latest_mean < 1
        if not had_overprotection and self._having_overproduction:
            if watt_produced is not None and self._watt_produced is not None:
                self._break_even = (self._watt_produced+watt_produced)/2
            elif watt_produced is not None:
                self._break_even = watt_produced
            else:
                self._break_even = None
        elif had_overprotection and self._having_overproduction and self._break_even is not None:
            self._break_even *= 0.95 # decrease break-even value when overproduction is still present
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