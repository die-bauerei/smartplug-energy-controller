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
        self.assertEqual(parser.general, GeneralConfig(Path('/full/path/to/your/test.log'), 20, 5))
        self.assertEqual(parser.plug_uuids, ['5268704d-34c2-4e38-9d3f-73c4775babca', 
                                             '46742b02-aabb-47a7-9207-92b7dcea4875',
                                             '5f5f39a3-e392-48a4-aa62-0bc6959f35d2',
                                             '5def8014-c16d-41aa-a01d-c19a0801f65c'])
        self.assertEqual(parser.plug('5268704d-34c2-4e38-9d3f-73c4775babca'), 
                         TapoSmartPlugConfig('tapo', True, 111, 0.1, '192.168.110.1', 'test_user_1', 'test_passwd_1'))
        self.assertEqual(parser.plug('46742b02-aabb-47a7-9207-92b7dcea4875'), 
                         TapoSmartPlugConfig('tapo', True, 222, 0.2, '192.168.110.2', 'test_user_2', 'test_passwd_2'))
        self.assertEqual(parser.plug('5f5f39a3-e392-48a4-aa62-0bc6959f35d2'),
                         OpenHabSmartPlugConfig('openhab', True, 333, 0.3, 'oh_smartplug_thing', 'oh_smartplug_switch', 'oh_smartplug_power', 'oh_automation_enabled'))
        self.assertEqual(parser.plug('5def8014-c16d-41aa-a01d-c19a0801f65c'), 
                         OpenHabSmartPlugConfig('openhab', True, 444, 0.4, 'oh_smartplug_thing_2', 'oh_smartplug_switch_2', 'oh_smartplug_power_2', 'oh_automation_enabled_2'))
        self.assertEqual(parser.oh_connection, OpenHabConnectionConfig('http://localhost:8080', 'openhab', 'secret'))
        
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
        self.assertEqual(os.environ['openhab_plug_ids'], '5f5f39a3-e392-48a4-aa62-0bc6959f35d2,5def8014-c16d-41aa-a01d-c19a0801f65c')

if __name__ == '__main__':
    try:
        unittest.main()
    except Exception as e:
        logger.exception("Caught Exception: " + str(e))
    except:
        logger.exception("Caught unknow exception")