import logging
import sys
import unittest

from smartplug_energy_controller.plug_controller import TapoPlugController
from smartplug_energy_controller.config import SmartPlugConfig

logging.basicConfig(stream=sys.stdout, level=logging.ERROR)
logger = logging.getLogger(__name__)

class TestTapoPlugController(unittest.IsolatedAsyncioTestCase):
    async def test_is_on(self) -> None:
        controller=TapoPlugController(logger, SmartPlugConfig(id='test_controller', auth_user='test', auth_passwd='test', 
                            expected_consumption_in_watt=200, consumer_efficiency=0.5))
        self.assertFalse(await controller.is_on())
        
if __name__ == '__main__':
    try:
        unittest.main()
    except Exception as e:
        logger.exception("Caught Exception: " + str(e))
    except:
        logger.exception("Caught unknow exception")