import logging
import sys
import unittest

from smartplug_energy_controller.plug_controller import PlugController

logging.basicConfig(stream=sys.stdout, level=logging.ERROR)
logger = logging.getLogger(__name__)

class PlugControllerMock(PlugController):
    def __init__(self, logger) -> None:
        super().__init__(logger, watt_consumption_eval_count=4, expected_watt_consumption=100)
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
        # plug is off and consumption low (< 10)
        controller=PlugControllerMock(logger)
        await controller.add_watt_consumption(0)
        self.assertFalse(await controller.is_on())
        await controller.add_watt_consumption(5)
        await controller.add_watt_consumption(2)
        await controller.add_watt_consumption(0)
        self.assertTrue(await controller.is_on())

        # plug is on and consumption increases a bit but is still < expected_watt_consumption
        await controller.add_watt_consumption(50)
        await controller.add_watt_consumption(60)
        await controller.add_watt_consumption(70)
        await controller.add_watt_consumption(80)
        self.assertTrue(await controller.is_on())

        # plug should be turned off when consumption increases to much (> expected_watt_consumption)
        await controller.add_watt_consumption(110)
        self.assertTrue(await controller.is_on())
        await controller.add_watt_consumption(120)
        await controller.add_watt_consumption(130)
        self.assertFalse(await controller.is_on())
        
if __name__ == '__main__':
    try:
        unittest.main()
    except Exception as e:
        logger.exception("Caught Exception: " + str(e))
    except:
        logger.exception("Caught unknow exception")