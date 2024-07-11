import logging
import sys
import unittest
from datetime import datetime, timedelta
from typing import List

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

class TestPlugManager(unittest.IsolatedAsyncioTestCase):
    eval_time_in_min=2
    def setUp(self) -> None:
        # this is called before each test
        self._manager=PlugManager(logger, TestPlugManager.eval_time_in_min)
        cfg=SmartPlugConfig(type='testing', expected_consumption_in_watt=200, consumer_efficiency=0.5)
        self._manager._add_plug_controller("A", PlugControllerMock(logger, cfg))
        cfg=SmartPlugConfig(type='testing', expected_consumption_in_watt=100, consumer_efficiency=0.5)
        self._manager._add_plug_controller("B", PlugControllerMock(logger, cfg))
        cfg=SmartPlugConfig(type='testing', expected_consumption_in_watt=50, consumer_efficiency=0.5)
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
        await self._manager.add_smart_meter_values(200, 0, now)
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))
        await self._manager.add_smart_meter_values(100, 100, now + timedelta(minutes=1, seconds=1))
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))
        await self._manager.add_smart_meter_values(0, 220, now + timedelta(minutes=2, seconds=2))
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))
        await self._manager.add_smart_meter_values(0, 250, now + timedelta(minutes=3, seconds=3))
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))
        self.assertEqual((await self._manager.plug('A').state)['proposed_state'], 'Off')
        await self._manager.add_smart_meter_values(0, 301, now + timedelta(minutes=4, seconds=4))
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertEqual((await self._manager.plug('A').state)['proposed_state'], 'On')
        self.assertTrue(not await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(80, 320, now + timedelta(minutes=5, seconds=5))
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertTrue(not await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(20, 380, now + timedelta(minutes=6, seconds=6))
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertTrue(not await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(0, 401, now + timedelta(minutes=7, seconds=7))
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertTrue(not await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(0, 460, now + timedelta(minutes=8, seconds=8))
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertTrue(await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(10, 490, now + timedelta(minutes=9, seconds=9))
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertTrue(await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(0, 600, now + timedelta(minutes=10, seconds=10))
        self.assertTrue(await self._all_plugs_on(self._plug_uuids))
        await self._manager.add_smart_meter_values(90, 500, now + timedelta(minutes=11, seconds=11))
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertTrue(await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(30, 480, now + timedelta(minutes=12, seconds=12))
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertTrue(await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(100, 400, now + timedelta(minutes=13, seconds=13))
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertTrue(not await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(0, 360, now + timedelta(minutes=14, seconds=14))
        self.assertEqual(self._manager._savings_from_plugs_turned_off.value(now + timedelta(minutes=14, seconds=14)), 75)
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertTrue(not await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(50, 350, now + timedelta(minutes=15, seconds=15))
        self.assertTrue(await self._manager.plug('A').is_on())
        self.assertTrue(not await self._manager.plug('B').is_on())
        self.assertTrue(not await self._manager.plug('C').is_on())
        await self._manager.add_smart_meter_values(130, 270, now + timedelta(minutes=16, seconds=16))
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))
        await self._manager.add_smart_meter_values(10, 190, now + timedelta(minutes=17, seconds=17))
        self.assertEqual(self._manager._savings_from_plugs_turned_off.value(now + timedelta(minutes=14, seconds=14)), 175)
        await self._manager.add_smart_meter_values(10, 190, now + timedelta(minutes=18, seconds=18))
        await self._manager.add_smart_meter_values(10, 190, now + timedelta(minutes=19, seconds=19))
        await self._manager.add_smart_meter_values(0, 210, now + timedelta(minutes=20, seconds=20))
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))
        await self._manager.add_smart_meter_values(100, 90, now + timedelta(minutes=21, seconds=21))
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))

    async def test_consumer_is_around_break_even(self):
        now = datetime.now()
        await self._manager.add_smart_meter_values(200, 0, now)
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))
        await self._manager.add_smart_meter_values(100, 100, now + timedelta(minutes=1))
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))
        await self._manager.add_smart_meter_values(0, 250, now + timedelta(minutes=2))
        self.assertTrue(await self._all_plugs_off(self._plug_uuids))
        state_a = await self._manager.plug('A').state
        self.assertEqual(state_a['proposed_state'], 'Off')
        self.assertEqual(state_a['actual_state'], 'Off')
        await self._manager.add_smart_meter_values(0, 310, now + timedelta(minutes=3))
        self.assertTrue(await self._manager.plug('A').is_on())
        state_a = await self._manager.plug('A').state
        self.assertEqual(state_a['proposed_state'], 'On')
        self.assertEqual(state_a['actual_state'], 'On')
        await self._manager.add_smart_meter_values(90, 310, now + timedelta(minutes=4))
        self.assertTrue(await self._manager.plug('A').is_on())
        # Plug should stay on if obtained/produced watt is around break-even point, ...
        await self._manager.add_smart_meter_values(110, 290, now + timedelta(minutes=5))
        self.assertTrue(await self._manager.plug('A').is_on())
        # ... but be turned off if the value is too far off
        await self._manager.add_smart_meter_values(130, 270, now + timedelta(minutes=6))
        self.assertTrue(not await self._manager.plug('A').is_on())
        # And only be turned back on again if the mean-value is higher then the break-even point again in the given timeframe 
        # (TestPlugManager.eval_time_in_min + min_expected_freq)
        await self._manager.add_smart_meter_values(0, 290, now + timedelta(minutes=7))
        watt_consumed= await self._manager.plug('A').watt_consumed
        efficiency= await self._manager.plug('A').consumer_efficiency
        self.assertEqual(self._manager._current_break_even(), (290+270)/2 - watt_consumed*efficiency)
        self.assertTrue(not await self._manager.plug('A').is_on())
        await self._manager.add_smart_meter_values(0, 280, now + timedelta(minutes=8))
        self.assertTrue(not await self._manager.plug('A').is_on())
        await self._manager.add_smart_meter_values(0, 310, now + timedelta(minutes=8, seconds=30))
        self.assertTrue(await self._manager.plug('A').is_on())
        await self._manager.add_smart_meter_values(80, 320, now + timedelta(minutes=9))
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