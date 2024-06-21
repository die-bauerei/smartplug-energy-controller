import logging
import sys
import unittest

from smartplug_energy_controller.config import *

logging.basicConfig(stream=sys.stdout, level=logging.ERROR)
logger = logging.getLogger(__name__)

import pathlib
test_path = str( pathlib.Path(__file__).parent.absolute() )
config_file=test_path+"/data/config.example.yml"

class TestConfig(unittest.TestCase):

    def test_creation(self) -> None:
        parser=ConfigParser(Path(config_file))
        self.assertEqual(parser.general, GeneralConfig(Path('test.log'), 22, 11))
        self.assertEqual(parser.plug_uuids, ['5268704d-34c2-4e38-9d3f-73c4775babca', '46742b02-aabb-47a7-9207-92b7dcea4875'])
        self.assertEqual(parser.plug('5268704d-34c2-4e38-9d3f-73c4775babca'), 
                         SmartPlugConfig('192.168.110.1', 'test_user_1', 'test_passwd_1', 111, 0.1))
        self.assertEqual(parser.plug('46742b02-aabb-47a7-9207-92b7dcea4875'), 
                         SmartPlugConfig('192.168.110.2', 'test_user_2', 'test_passwd_2', 222, 0.2))
  
if __name__ == '__main__':
    try:
        unittest.main()
    except Exception as e:
        logger.exception("Caught Exception: " + str(e))
    except:
        logger.exception("Caught unknow exception")