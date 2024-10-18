# Test the full API: https://fastapi.tiangolo.com/tutorial/testing/#extended-testing-file
from fastapi.testclient import TestClient
from typing import Any
from unittest.mock import patch
from dataclasses import dataclass

import logging
import unittest
import sys
import os

from smartplug_energy_controller.plug_controller import TapoPlugController, OpenHabPlugController

import smartplug_energy_controller
logging.basicConfig(stream=sys.stdout, level=logging.ERROR)
smartplug_energy_controller._logger = logging.getLogger(__name__)
logger = smartplug_energy_controller._logger

class OpenhabConnectionMock():
    def __init__(self, logger : logging.Logger) -> None:
        self._logger=logger

    async def post_to_item(self, oh_item_name : str, value : Any) -> bool:
        return True

smartplug_energy_controller._oh_connection=OpenhabConnectionMock(logger)

from pathlib import Path
test_path = Path(__file__).parent.absolute()
config_file=Path(f"{test_path}/data/config.example.yml")
os.environ['CONFIG_PATH']=config_file.as_posix()
os.environ['SMARTPLUG_ENERGY_CONTROLLER_PORT']='8000'

from smartplug_energy_controller.app import app
_client = TestClient(app)

@dataclass()
class PlugControllerMock:
    _is_on : bool = False
    _propose_to_turn_on : bool = False
    _turn_on_off_works : bool = True
    def is_on(self) -> bool:
        return self._is_on
    
    def turn_on(self) -> bool:
        self._propose_to_turn_on=True
        if self._turn_on_off_works:
            self._is_on=True
            return True
        return False

    def turn_off(self) -> bool:
        self._propose_to_turn_on=False
        if self._turn_on_off_works:
            self._is_on=False
            return True
        return False

tapo_ctrl_mock = PlugControllerMock()
oh_ctrl_mock= PlugControllerMock()

@patch.object(TapoPlugController, 'is_on', side_effect=tapo_ctrl_mock.is_on)
@patch.object(OpenHabPlugController, 'is_on', side_effect=oh_ctrl_mock.is_on)
@patch.object(TapoPlugController, 'turn_on', side_effect=tapo_ctrl_mock.turn_on)
@patch.object(OpenHabPlugController, 'turn_on', side_effect=oh_ctrl_mock.turn_on)
@patch.object(TapoPlugController, 'turn_off', side_effect=tapo_ctrl_mock.turn_off)
@patch.object(OpenHabPlugController, 'turn_off', side_effect=oh_ctrl_mock.turn_off)
class TestAppBasic(unittest.TestCase):
    def setUp(self) -> None:
        tapo_ctrl_mock._is_on=False
        oh_ctrl_mock._is_on=False

    def test_root(self, *mocks) -> None:
        response = _client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "Hallo from smartplug-energy-controller"}

    def test_plug_info(self, *mocks) -> None:
        response = _client.get("/plug-info/5268704d-34c2-4e38-9d3f-73c4775babca")
        assert response.status_code == 200
        assert response.json()['type'] == 'tapo'
        assert response.json()['id'] == '192.168.110.1'
        assert response.json()['user'] == 'test_user_1'
        assert response.json()['passwd'] == 'test_passwd_1'

        response = _client.get("/plug-info/5f5f39a3-e392-48a4-aa62-0bc6959f35d2")
        assert response.status_code == 200
        assert response.json()['type'] == 'openhab'
        assert response.json()['oh_thing_name'] == 'oh_smartplug_thing'
        assert response.json()['oh_switch_item_name'] == 'oh_smartplug_switch'
        assert response.json()['oh_power_consumption_item_name'] == 'oh_smartplug_power'
    
    def test_get_plug_state(self, *mocks) -> None:
        response = _client.get("/plug-state/5268704d-34c2-4e38-9d3f-73c4775babca")
        assert response.status_code == 200
        assert response.json()['proposed_state'] == 'Off'
        assert response.json()['actual_state'] == 'Off'
        assert response.json()['watt_consumed_at_plug'] == '111'

        response = _client.get("/plug-state/5f5f39a3-e392-48a4-aa62-0bc6959f35d2")
        assert response.status_code == 200
        assert response.json()['proposed_state'] == 'Off'
        assert response.json()['actual_state'] == 'Off'
        assert response.json()['watt_consumed_at_plug'] == '333'

        tapo_ctrl_mock._is_on=True
        oh_ctrl_mock._is_on=True

        response = _client.get("/plug-state/5268704d-34c2-4e38-9d3f-73c4775babca")
        assert response.status_code == 200
        assert response.json()['proposed_state'] == 'Off'
        assert response.json()['actual_state'] == 'On'
        assert response.json()['watt_consumed_at_plug'] == '111'

        response = _client.get("/plug-state/5f5f39a3-e392-48a4-aa62-0bc6959f35d2")
        assert response.status_code == 200
        assert response.json()['proposed_state'] == 'Off'
        assert response.json()['actual_state'] == 'On'
        assert response.json()['watt_consumed_at_plug'] == '333'

    def test_put_plug_state_tapo(self, *mocks) -> None:
        tapo_uuid='5268704d-34c2-4e38-9d3f-73c4775babca'
        response = _client.get(f"/plug-state/{tapo_uuid}")
        assert response.status_code == 200
        assert response.json()['proposed_state'] == 'Off'
        assert response.json()['actual_state'] == 'Off'

        response = _client.put(f"/plug-state/{tapo_uuid}", json={'watt_consumed_at_plug': 100, 'online': True, 'is_on': False})
        assert response.status_code == 501
        assert response.json() == {'detail': f"Plug with uuid {tapo_uuid} is not an OpenHabPlugController. Only OpenHabPlugController can be updated."}

class TestAppAdvanced(unittest.TestCase):
    def test_put_plug_state_oh(self, *mocks) -> None:
        oh_uuid='5f5f39a3-e392-48a4-aa62-0bc6959f35d2'
        response = _client.get(f"/plug-state/{oh_uuid}")
        assert response.status_code == 200
        assert response.json()['watt_consumed_at_plug'] == '333'
        assert response.json()['proposed_state'] == 'Off'
        assert response.json()['actual_state'] == 'Off'

        response = _client.put(f"/plug-state/{oh_uuid}", json={'watt_consumed_at_plug': 200, 'online': True, 'is_on': True})
        assert response.status_code == 200
        response = _client.get(f"/plug-state/{oh_uuid}")
        assert response.status_code == 200
        assert response.json()['watt_consumed_at_plug'] == '200.0'
        assert response.json()['proposed_state'] == 'Off'
        assert response.json()['actual_state'] == 'On'

def load_tests(loader, standard_tests, pattern):
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestAppBasic))
    suite.addTests(loader.loadTestsFromTestCase(TestAppAdvanced))
    return suite

if __name__ == '__main__':
    try:
        unittest.main()
    except Exception as e:
        logger.exception("Caught Exception: " + str(e))
    except:
        logger.exception("Caught unknow exception")