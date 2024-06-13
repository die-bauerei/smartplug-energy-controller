import logging
import sys
import unittest
from datetime import datetime, timedelta

from smartplug_energy_controller.plug_controller import PlugController
from smartplug_energy_controller.config import SmartPlugConfig

logging.basicConfig(stream=sys.stdout, level=logging.ERROR)
logger = logging.getLogger(__name__)

class PlugControllerMock(PlugController):
    def __init__(self, logger) -> None:
        cfg=SmartPlugConfig(id='test_controller', auth_user='test', auth_passwd='test', 
                            expected_consumption_in_watt=200, consumer_efficiency=0.5, eval_time_in_min=4)
        super().__init__(logger, cfg)
        self._is_on = False

    def reset(self) -> None:
        pass

    async def update(self) -> None:
        pass

    async def is_on(self) -> bool:
        return self._is_on

    async def turn_on(self) -> None:
        self._is_on = True

    async def turn_off(self) -> None:
        self._is_on = False

class TestPlugController(unittest.IsolatedAsyncioTestCase):

    async def test_consumption(self) -> None:
        now = datetime.now()

        # plug is off and consumption low (< 10)
        controller=PlugControllerMock(logger)
        await controller.add_obtained_watt_from_provider(0, now+timedelta(minutes=1))
        self.assertTrue(await controller.is_on())

        # plug is on and consumption increases a bit but is still < expected_watt_consumption*consumer_efficiency
        await controller.add_obtained_watt_from_provider(50, now+timedelta(minutes=2))
        await controller.add_obtained_watt_from_provider(60, now+timedelta(minutes=3))
        await controller.add_obtained_watt_from_provider(70, now+timedelta(minutes=4))
        await controller.add_obtained_watt_from_provider(80, now+timedelta(minutes=5))
        self.assertTrue(await controller.is_on())

        # plug should be turned off when consumption increases to much (> expected_watt_consumption*consumer_efficiency)
        await controller.add_obtained_watt_from_provider(110, now+timedelta(minutes=6))
        self.assertTrue(await controller.is_on())
        await controller.add_obtained_watt_from_provider(120, now+timedelta(minutes=7))
        await controller.add_obtained_watt_from_provider(130, now+timedelta(minutes=8))
        self.assertFalse(await controller.is_on())
        
if __name__ == '__main__':
    try:
        unittest.main()
    except Exception as e:
        logger.exception("Caught Exception: " + str(e))
    except:
        logger.exception("Caught unknow exception")