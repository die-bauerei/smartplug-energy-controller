import logging
import sys
import unittest
from datetime import datetime, timedelta
from typing import List, Dict
from functools import cached_property

from smartplug_energy_controller.plug_controller import PlugController
from smartplug_energy_controller.plug_manager import PlugManager
from smartplug_energy_controller.config import SmartPlugConfig

logging.basicConfig(stream=sys.stdout, level=logging.ERROR)
logger = logging.getLogger(__name__)

class PlugControllerMock(PlugController):
    def __init__(self, logger, cfg : SmartPlugConfig) -> None:
        super().__init__(logger, cfg)
        self._is_on = False
        self._online = True

    @cached_property
    def info(self) -> Dict[str, str]:
        info : Dict[str, str] = {}
        info['type'] = 'testing'
        return info

    def reset(self) -> None:
        pass

    async def is_online(self) -> bool:
        return self._online

    async def is_on(self) -> bool:
        return self._is_on

    async def turn_on(self) -> bool:
        rc = await super().turn_on()
        if rc and not self._is_on:
            self._is_on = True
            return True
        return False

    async def turn_off(self) -> bool:
        rc = await super().turn_off()
        if rc and self._is_on:
            self._is_on = False
            return True
        return False

class DateTimeIncrementer():
    def __init__(self, time : datetime) -> None:
        self._time = time
        self._counter = 0

    def next_datetime(self) -> datetime:
        self._counter += 1
        return self._time + timedelta(minutes=self._counter, seconds=self._counter)

class TestPlugManager(unittest.IsolatedAsyncioTestCase):
    eval_time_in_min=2
    default_base_load_in_watt=200
    def setUp(self) -> None:
        # this is called before each test
        self._manager=PlugManager(logger, TestPlugManager.eval_time_in_min, TestPlugManager.default_base_load_in_watt)
        cfg=SmartPlugConfig(type='testing', enabled=True, expected_consumption_in_watt=200, consumer_efficiency=0.5)
        self._manager._add_plug_controller("A", PlugControllerMock(logger, cfg))
        cfg=SmartPlugConfig(type='testing', enabled=True, expected_consumption_in_watt=100, consumer_efficiency=0.5)
        self._manager._add_plug_controller("B", PlugControllerMock(logger, cfg))
        cfg=SmartPlugConfig(type='testing', enabled=True, expected_consumption_in_watt=50, consumer_efficiency=0.5)
        self._manager._add_plug_controller("C", PlugControllerMock(logger, cfg))
        self._plug_uuids=['A', 'B', 'C']

    def _set_plug_online(self, id : str, online : bool) -> None:
        self._manager.plug(id)._online = online # type: ignore

    async def _all_plugs_on(self, id_list : List[str]) -> bool:
        for id in id_list:
            if await self._manager.plug(id).is_online() and not await self._manager.plug(id).is_on():
                return False
        return True
    
    async def _all_plugs_off(self, id_list : List[str]) -> bool:
        for id in id_list:
            if await self._manager.plug(id).is_online() and await self._manager.plug(id).is_on():
                return False
        return True

    async def test_turn_on_off_sunny_day(self) -> None:
        now = datetime.now()
        await self._manager.add_smart_meter_values(150, 0, now)
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))
        time_incr = DateTimeIncrementer(now)
        await self._manager.add_smart_meter_values(100, 100, time_incr.next_datetime())
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))
        await self._manager.add_smart_meter_values(0, 220, time_incr.next_datetime())
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))
        await self._manager.add_smart_meter_values(0, 250, time_incr.next_datetime())
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))
        self.assertEqual((await self._manager.plug('A').state)['proposed_state'], 'Off')
        await self._manager.add_smart_meter_values(0, 300, time_incr.next_datetime())
        await self._manager.add_smart_meter_values(0, 350, time_incr.next_datetime())
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertEqual((await self._manager.plug('A').state)['proposed_state'], 'On')
        self.assertTrue(not await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(80, 320, time_incr.next_datetime())
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertTrue(not await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(20, 380, time_incr.next_datetime())
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertTrue(not await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(0, 401, time_incr.next_datetime())
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertTrue(not await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(0, 460, time_incr.next_datetime())
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertTrue(await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(10, 490, time_incr.next_datetime())
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertTrue(await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(0, 600, time_incr.next_datetime())
        self.assertTrue(await self._all_plugs_on(self._plug_uuids))
        await self._manager.add_smart_meter_values(90, 500, time_incr.next_datetime())
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertTrue(await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(30, 480, time_incr.next_datetime())
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertTrue(await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(100, 400, time_incr.next_datetime())
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertTrue(not await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(0, 360, time_incr.next_datetime())
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertTrue(not await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(50, 350, time_incr.next_datetime())
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertTrue(not await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(130, 270, time_incr.next_datetime())
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))
        await self._manager.add_smart_meter_values(10, 190, time_incr.next_datetime())
        await self._manager.add_smart_meter_values(10, 190, time_incr.next_datetime())
        await self._manager.add_smart_meter_values(10, 190, time_incr.next_datetime())
        await self._manager.add_smart_meter_values(0, 210, time_incr.next_datetime())
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))
        await self._manager.add_smart_meter_values(100, 90, time_incr.next_datetime())
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))

    async def test_consumer_is_around_break_even(self):
        now = datetime.now()
        await self._manager.add_smart_meter_values(150, 0, now)
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))
        await self._manager.add_smart_meter_values(100, 100, now + timedelta(minutes=1))
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))
        await self._manager.add_smart_meter_values(0, 250, now + timedelta(minutes=2))
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))
        state_a = await self._manager.plug('A').state
        self.assertEqual(state_a['proposed_state'], 'Off')
        self.assertEqual(state_a['actual_state'], 'Off')
        await self._manager.add_smart_meter_values(0, 310, now + timedelta(minutes=3))
        await self._manager.add_smart_meter_values(0, 320, now + timedelta(minutes=4))
        self.assertTrue(await self._manager.plug('A').is_on())
        state_a = await self._manager.plug('A').state
        self.assertEqual(state_a['proposed_state'], 'On')
        self.assertEqual(state_a['actual_state'], 'On')
        await self._manager.add_smart_meter_values(90, 310, now + timedelta(minutes=5))
        self.assertTrue(await self._manager.plug('A').is_on())
        # Plug should stay on if obtained/produced watt is around break-even point, ...
        await self._manager.add_smart_meter_values(110, 290, now + timedelta(minutes=6))
        self.assertTrue(await self._manager.plug('A').is_on())
        # ... but be turned off if the value is too far off
        await self._manager.add_smart_meter_values(130, 270, now + timedelta(minutes=7))
        self.assertTrue(not await self._manager.plug('A').is_on())
        # And only be turned back on again if the mean-value is higher then the break-even point again in the given timeframe 
        # (TestPlugManager.eval_time_in_min + min_expected_freq)
        await self._manager.add_smart_meter_values(0, 290, now + timedelta(minutes=8))
        self.assertEqual(self._manager._break_even, (290+270)/2)
        self.assertTrue(not await self._manager.plug('A').is_on())
        await self._manager.add_smart_meter_values(0, 280, now + timedelta(minutes=9))
        self.assertTrue(not await self._manager.plug('A').is_on())
        await self._manager.add_smart_meter_values(0, 310, now + timedelta(minutes=9, seconds=30))
        self.assertTrue(not await self._manager.plug('A').is_on())
        # each further call should decrease the break-even value until eventually Plug A is on
        for i in range(60):
            await self._manager.add_smart_meter_values(0, 340, now + timedelta(minutes=9, seconds=35+i))
        self.assertTrue(await self._manager.plug('A').is_on())
        await self._manager.add_smart_meter_values(80, 320, now + timedelta(minutes=11))
        self.assertTrue(await self._manager.plug('A').is_on())

    async def test_turn_on_off_plug_offline(self):
        self._set_plug_online('A', False)

        now = datetime.now()
        await self._manager.add_smart_meter_values(200, 0, now)
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))
        await self._manager.add_smart_meter_values(100, 100, now + timedelta(minutes=1))
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))
        await self._manager.add_smart_meter_values(0, 200, now + timedelta(minutes=2))
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))
        await self._manager.add_smart_meter_values(0, 280, now + timedelta(minutes=3))
        self.assertTrue(await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(40, 300, now + timedelta(minutes=4))
        self.assertTrue(await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(80, 310, now + timedelta(minutes=5))
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))

if __name__ == '__main__':
    try:
        unittest.main()
    except Exception as e:
        logger.exception("Caught Exception: " + str(e))
    except:
        logger.exception("Caught unknow exception")