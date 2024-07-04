import HABApp
#import HABApp.openhab.interface
from HABApp.core.events import EventFilter
from HABApp.openhab.events import ItemStateChangedEvent, ItemStateChangedEventFilter, ThingStatusInfoChangedEvent
from HABApp.openhab.items import NumberItem, SwitchItem, Thing

from datetime import timedelta

import asyncio
import logging
import http

import HABApp.rule

# writes to ../log/HABApp.log
log = logging.getLogger('HABApp')

class SmartMeterValueForwarder(HABApp.Rule):
    def __init__(self, watt_obtained_from_provider_item : str, watt_produced_item : str,
                 put_req_url : str, force_request_time_in_sec : int = 60) -> None:
        """
        Send values to the smartplug-energy-controller API
            Parameters:
                watt_obtained_from_provider_item (str): openHAB number item
                watt_produced_item (str): openHAB number item
                put_req_url (str): Full URL to send the put request to
                force_request_time_in_sec (int): Time in seconds to send the latest value in case of no state changed event. 
                    Disabled in case the value equals 0.
        """
        super().__init__()
        self._lock : asyncio.Lock = asyncio.Lock()
        self._url=put_req_url
        self._watt_obtained_item=NumberItem.get_item(watt_obtained_from_provider_item)
        self._watt_obtained_item.listen_event(self._item_state_changed, ItemStateChangedEventFilter())
        self._watt_produced_item=NumberItem.get_item(watt_produced_item)
        self._watt_produced_item.listen_event(self._item_state_changed, ItemStateChangedEventFilter())
        if force_request_time_in_sec > 0:
            self._send_latest_value_job=self.run.countdown(force_request_time_in_sec, self._send_latest_values) # type: ignore
        else:
            self._send_latest_value_job=None

    async def _item_state_changed(self, event):
        assert isinstance(event, ItemStateChangedEvent), type(event)
        await self._send_values(str(self._watt_obtained_item.get_value()), str(self._watt_produced_item.get_value()))

    async def _send_latest_values(self):
        await self._send_values(str(self._watt_obtained_item.get_value()), str(self._watt_produced_item.get_value()))

    async def _send_values(self, watt_obtained_value : str, watt_produced_value : str):
        try:
            async with self.async_http.put(self._url, json={'watt_obtained_from_provider': watt_obtained_value, 
                                                            'watt_produced': watt_produced_value}) as response:
                if response.status != http.HTTPStatus.OK:
                    log.warning(f"Failed to forward smart meter values via put request to {self._url}. Return code: {response.status}. Text: {await response.text()}")
            if self._send_latest_value_job:
                async with self._lock:
                    self._send_latest_value_job.stop()
                    self._send_latest_value_job.reset()
        except Exception as exc:
            log.error(f"Caught Exception: {exc}")

class SmartPlugSynchronizer(HABApp.Rule):
    def __init__(self, smartplug_uuid : str) -> None:
        """
        Sync between a openHAB SmartPlug and smartplug-energy-controller
        """
        super().__init__()
        self._smartplug_uuid : str = smartplug_uuid
        self._info_url='http://localhost:8000/plug-info'
        self._state_url='http://localhost:8000/plug-state'
        self.run.soon(callback=self._init_oh_connection) # type: ignore
    
    async def _init_oh_connection(self):
        try:
            async with self.async_http.get(f"{self._info_url}/{self._smartplug_uuid}") as response:
                if response.status != http.HTTPStatus.OK:
                    log.error(f"Failed to init SmartPlug with UUID {self._smartplug_uuid}. Return code: {response.status}. Text: {await response.text()}")
                else:
                    data = await response.json()
                    self._thing=Thing.get_item(data['oh_thing_name'])
                    self._thing.listen_event(self._sync_values, EventFilter(ThingStatusInfoChangedEvent))
                    self._switch_item=SwitchItem.get_item(data['oh_switch_item_name'])
                    self._switch_item.listen_event(self._sync_values, ItemStateChangedEventFilter())
                    self._power_consumption_item=NumberItem.get_item(data['oh_power_consumption_item_name'])
                    self._power_consumption_item.listen_event(self._sync_values, ItemStateChangedEventFilter())
                    log.info(f"SmartPlug with UUID {self._smartplug_uuid} successfully initialized.")
                    self.run.every(start_time=timedelta(seconds=1), interval=timedelta(seconds=5), callback=self._sync_state) # type: ignore
        except Exception as exc:
            log.error(f"Caught Exception: {exc}")

    async def _sync_values(self, event):
        try:
            power_consumption=self._power_consumption_item.get_value()
            online=self._thing.status == 'ONLINE'
            url=f"{self._state_url}/{self._smartplug_uuid}"
            async with self.async_http.put(url, json={'watt_consumed_at_plug': power_consumption, 
                                                      'online': online, 
                                                      'is_on' : self._switch_item.is_on()}) as response:
                if response.status != http.HTTPStatus.OK:
                    log.warning(f"Failed to forward smartplug values via put request to {url}. Return code: {response.status}. Text: {await response.text()}")
        except Exception as exc:
            log.error(f"Caught Exception: {exc}")
    
    async def _sync_state(self):
        try:
            async with self.async_http.get(f"{self._state_url}/{self._smartplug_uuid}") as response:
                if response.status != http.HTTPStatus.OK:
                    log.warning(f"Failed to sync state of SmartPlug with UUID {self._smartplug_uuid}. Return code: {response.status}. Text: {await response.text()}")
                else:
                    data = await response.json()
                    self._switch_item.on() if data['proposed_state'] == 'On' else self._switch_item.off()
        except Exception as exc:
            log.error(f"Caught Exception: {exc}")

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(f"{Path(__file__).parent}/../.env")
import os

if 'openhab_plug_ids' in os.environ:
    for plug_id in os.environ['openhab_plug_ids'].split(','):
        log.info(f"About to init SmartPlugSynchronizer for {plug_id}")
        SmartPlugSynchronizer(smartplug_uuid=plug_id)

if 'oh_watt_obtained_from_provider_item' in os.environ and 'oh_watt_produced_item' in os.environ:
    log.info("About to init SmartMeterValueForwarder")
    SmartMeterValueForwarder(watt_obtained_from_provider_item=os.environ['oh_watt_obtained_from_provider_item'], 
                            watt_produced_item=os.environ['oh_watt_produced_item'],
                            put_req_url='http://localhost:8000/smart-meter')