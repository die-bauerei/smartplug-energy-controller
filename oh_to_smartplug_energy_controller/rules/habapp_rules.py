import HABApp
#import HABApp.openhab.interface
from HABApp.openhab.events import ItemStateChangedEvent, ItemStateChangedEventFilter
from HABApp.openhab.items import NumberItem

import asyncio
import logging
import http

# writes to ../log/HABApp.log
log = logging.getLogger('HABApp')

class SmartPlugEnergyControllerForwarder(HABApp.Rule):
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
                    log.warning(f"Failed to forward value via put request to {self._url}. Return code: {response.status}. Text: {await response.text()}")
            if self._send_latest_value_job:
                async with self._lock:
                    self._send_latest_value_job.stop()
                    self._send_latest_value_job.reset()
        except Exception as exc:
            log.error(f"Caught Exception: {exc}")

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(f"{Path(__file__).parent}/../.env")
import os

SmartPlugEnergyControllerForwarder(watt_obtained_from_provider_item=os.environ['oh_watt_obtained_from_provider_item'], 
                                   watt_produced_item=os.environ['oh_watt_produced_item'],
                                   put_req_url='http://localhost:8000/smart_meter')