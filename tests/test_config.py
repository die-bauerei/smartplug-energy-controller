import logging
import sys
import unittest
import os

from ruamel.yaml import YAML
from dotenv import load_dotenv

from smartplug_energy_controller.config import *

logging.basicConfig(stream=sys.stdout, level=logging.ERROR)
logger = logging.getLogger(__name__)

from pathlib import Path
test_path = Path(__file__).parent.absolute()
config_file=Path(f"{test_path}/data/config.example.yml")
habapp_config_path=Path(f"{test_path}/../oh_to_smartplug_energy_controller/config.yml")

class TestConfig(unittest.TestCase):

    def test_creation(self) -> None:
        parser=ConfigParser(config_file, habapp_config_path)
        self.assertEqual(parser.general, GeneralConfig(Path('test.log'), 22, 11))
        self.assertEqual(parser.plug_uuids, ['5268704d-34c2-4e38-9d3f-73c4775babca', '46742b02-aabb-47a7-9207-92b7dcea4875'])
        self.assertEqual(parser.plug('5268704d-34c2-4e38-9d3f-73c4775babca'), 
                         SmartPlugConfig('192.168.110.1', 'test_user_1', 'test_passwd_1', 111, 0.1))
        self.assertEqual(parser.plug('46742b02-aabb-47a7-9207-92b7dcea4875'), 
                         SmartPlugConfig('192.168.110.2', 'test_user_2', 'test_passwd_2', 222, 0.2))
        
    def test_transfer_to_habapp(self) -> None:
        parser=ConfigParser(config_file, habapp_config_path)
        yaml=YAML(typ='safe', pure=True)
        habapp_config=yaml.load(habapp_config_path)
        self.assertEqual(habapp_config['openhab']['connection']['url'], 'http://localhost:8080')
        self.assertEqual(habapp_config['openhab']['connection']['user'], 'openhab')
        self.assertEqual(habapp_config['openhab']['connection']['password'], 'secret')

        load_dotenv(f"{habapp_config_path.parent}/.env")
        self.assertEqual(os.environ['oh_watt_obtained_from_provider_item'], 'smart_meter_overall_consumption')
        self.assertEqual(os.environ['oh_watt_produced_item'], 'system_balkonkraftwerk_now')

if __name__ == '__main__':
    try:
        unittest.main()
    except Exception as e:
        logger.exception("Caught Exception: " + str(e))
    except:
        logger.exception("Caught unknow exception")