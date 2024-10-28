import HABApp
#import HABApp.openhab.interface
from HABApp.core.events import EventFilter
from HABApp.openhab.events import ItemStateChangedEvent, ItemStateChangedEventFilter, ItemStateUpdatedEvent, ItemStateUpdatedEventFilter, ThingStatusInfoChangedEvent
from HABApp.openhab.items import NumberItem, SwitchItem, Thing
from HABApp.openhab.definitions.values import OnOffValue

from datetime import timedelta

import asyncio
import logging
import http

import HABApp.rule

# writes to ../log/HABApp.log
log = logging.getLogger('HABApp')

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(f"{Path(__file__).parent}/../.env")
import os

if 'SMARTPLUG_ENERGY_CONTROLLER_PORT' not in os.environ:
    raise EnvironmentError("Failed to start oh_to_smartplug_energy_controller. Required env variable SMARTPLUG_ENERGY_CONTROLLER_PORT not found.")
base_url=f"http://localhost:{os.environ['SMARTPLUG_ENERGY_CONTROLLER_PORT']}"

class SmartMeterValueForwarder(HABApp.Rule):
    def __init__(self, watt_obtained_from_provider_item : str, watt_produced_item : str) -> None:
        """
        Send values to the smartplug-energy-controller API
            Parameters:
                watt_obtained_from_provider_item (str): openHAB number item
                watt_produced_item (str): openHAB number item
        """
        super().__init__()
        self._url=base_url+"/smart-meter"
        self._watt_obtained_item=NumberItem.get_item(watt_obtained_from_provider_item)
        self._watt_obtained_item.listen_event(self._watt_obtained_updated, ItemStateUpdatedEventFilter())
        self._watt_produced_item=NumberItem.get_item(watt_produced_item)
        self._watt_produced_item.listen_event(self._watt_produced_changed, ItemStateChangedEventFilter())
        self.run.soon(callback=self._init_oh_connection) # type: ignore
    
    async def _init_oh_connection(self):
        async with self.async_http.get(f"{self._url}", headers={'Cache-Control': 'no-cache'}) as response:
            if response.status != http.HTTPStatus.OK:
                log.error(f"Failed to init SmartMeterValueForwarder. Return code: {response.status}. Text: {await response.text()}")
            else:
                data = await response.json()
                force_request_time_in_sec=max(1, data['min_expected_freq_in_sec']-1)
                self._watt_obtained_item.watch_update(force_request_time_in_sec).listen_event(self._send_latest_values)
                log.info(f"SmartMeterValueForwarder successfully initialized with a force_request_time_in_sec of {force_request_time_in_sec}.")

    async def _fwd_latest_watt_values(self) -> None:
        try:
            await self._send_values(str(self._watt_obtained_item.get_value()), str(self._watt_produced_item.get_value()))
        except Exception as exc:
            log.error(f"Caught Exception while forwarding latest watt values: {exc}")

    async def _watt_obtained_updated(self, event):
        assert isinstance(event, ItemStateUpdatedEvent), type(event)
        await self._fwd_latest_watt_values()

    async def _watt_produced_changed(self, event):
        assert isinstance(event, ItemStateChangedEvent), type(event)
        await self._fwd_latest_watt_values()

    async def _send_latest_values(self, event):
        log.warning("Forcing request to send latest values. This should not happen. Check your service which reads values from your electricity meter.")
        await self._fwd_latest_watt_values()

    async def _send_values(self, watt_obtained_value : str, watt_produced_value : str):
        async with self.async_http.put(self._url, json={'watt_obtained_from_provider': watt_obtained_value, 
                                                        'watt_produced': watt_produced_value}) as response:
            if response.status != http.HTTPStatus.OK:
                log.warning(f"Failed to forward smart meter values via put request to {self._url}. Return code: {response.status}. Text: {await response.text()}")

class SmartPlugSynchronizer(HABApp.Rule):
    def __init__(self, smartplug_uuid : str) -> None:
        """
        Sync between a openHAB SmartPlug and smartplug-energy-controller
        """
        super().__init__()
        self._smartplug_uuid : str = smartplug_uuid
        self._info_url=base_url+'/plug-info'
        self._state_url=base_url+'/plug-state'
        self._lock : asyncio.Lock = asyncio.Lock()
        self.run.soon(callback=self._init_oh_connection) # type: ignore
    
    async def _init_oh_connection(self):
        async with self.async_http.get(f"{self._info_url}/{self._smartplug_uuid}", headers={'Cache-Control': 'no-cache'}) as response:
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
                self._automation_enabled_switch_item=None
                if 'oh_automation_enabled_switch_item_name' in data:
                    self._automation_enabled_switch_item=SwitchItem.get_item(data['oh_automation_enabled_switch_item_name'])
                    self._automation_enabled_switch_item.listen_event(self._enable_disable_automation, ItemStateChangedEventFilter())
        
        if self._automation_enabled_switch_item is not None:
            async with self.async_http.get(f"{self._state_url}/{self._smartplug_uuid}", headers={'Cache-Control': 'no-cache'}) as response:
                if response.status != http.HTTPStatus.OK:
                    log.error(f"Failed to init oh_automation_enabled_switch_item from SmartPlug with UUID {self._smartplug_uuid}. Return code: {response.status}. Text: {await response.text()}")
                else:
                    data = await response.json()
                    self.openhab.send_command(self._automation_enabled_switch_item.name, 
                                              OnOffValue.ON if data['enabled'] == 'On' else OnOffValue.OFF)
                    log.info(f"oh switch item {self._automation_enabled_switch_item.name} successfully initialized.")
        else:
            log.info(f"No oh_automation_enabled_switch_item_name for SmartPlug with UUID {self._smartplug_uuid} configured.")
        
        self.run.every(start_time=timedelta(seconds=1), interval=timedelta(minutes=20), callback=self._check_state) # type: ignore
        self.run.every(start_time=timedelta(seconds=1), interval=timedelta(minutes=21), callback=self._check_thing) # type: ignore
        log.info(f"SmartPlug with UUID {self._smartplug_uuid} successfully initialized.")

    async def _sync_values(self, event):
        async with self._lock:
            power_consumption=self._power_consumption_item.get_value()
            online=self._thing.status == 'ONLINE'
            url=f"{self._state_url}/{self._smartplug_uuid}"
            async with self.async_http.put(url, json={'watt_consumed_at_plug': power_consumption, 
                                                        'online': online, 
                                                        'is_on' : self._switch_item.is_on()}) as response:
                if response.status != http.HTTPStatus.OK:
                    log.warning(f"Failed to forward smartplug values via put request to {url}. Return code: {response.status}. Text: {await response.text()}")

    async def _enable_disable_automation(self, event):
        async with self._lock:
            route_suffix = "enable" if event.value == OnOffValue.ON else "disable"
            url=f"{self._state_url}/{self._smartplug_uuid}/{route_suffix}"
            async with self.async_http.put(url) as response:
                if response.status != http.HTTPStatus.OK:
                    log.warning(f"Failed to enable/disable smartplug via put request to {url}. Return code: {response.status}. Text: {await response.text()}")

    async def _check_state(self):
        async with self._lock:
            # check if the proposed state has been set in an interval of ~10sec
            check_count=0
            while check_count < 10:
                async with self.async_http.get(f"{self._state_url}/{self._smartplug_uuid}", headers={'Cache-Control': 'no-cache'}) as response:
                    if response.status != http.HTTPStatus.OK:
                        log.warning(f"Failed to check state of SmartPlug with UUID {self._smartplug_uuid}. Return code: {response.status}. Text: {await response.text()}")
                    else:
                        data = await response.json()
                        proposed_to_be_on = True if data['proposed_state'] == 'On' else False
                        if self._switch_item.is_on() == proposed_to_be_on:
                            return # check successful
                await asyncio.sleep(1)
                check_count+=1
            log.warning(f"Switch {self._switch_item.name} is not in the proposed state.")

    async def _check_thing_state_change(self, enable : bool) -> bool:
        def _is_in_state() -> bool:
            return self._thing.status == 'ONLINE' if enable else self._thing.status != 'ONLINE'
        
        self.run.soon(lambda:self._thing.set_enabled(enable)) # type: ignore
        retry_count=0
        while not _is_in_state() and retry_count < 10:
            await asyncio.sleep(1)
            retry_count+=1
        return _is_in_state()

    async def _check_thing(self):
        async with self._lock:
            # turn thing off and on again
            if not (await self._check_thing_state_change(False)):
                log.error(f"Failed to turn off thing {self._thing.name}")
            elif not (await self._check_thing_state_change(True)):
                log.error(f"Failed to turn on thing {self._thing.name}")

if 'openhab_plug_ids' in os.environ:
    for plug_id in os.environ['openhab_plug_ids'].split(','):
        log.info(f"About to init SmartPlugSynchronizer for plug {plug_id}")
        SmartPlugSynchronizer(smartplug_uuid=plug_id)

if 'oh_watt_obtained_from_provider_item' in os.environ and 'oh_watt_produced_item' in os.environ:
    log.info("About to init SmartMeterValueForwarder")
    SmartMeterValueForwarder(watt_obtained_from_provider_item=os.environ['oh_watt_obtained_from_provider_item'], 
                            watt_produced_item=os.environ['oh_watt_produced_item'])