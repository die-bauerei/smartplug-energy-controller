# smartplug-energy-controller

A microservice to turn a smartplug on/off depending on current electricity consumption.
The intention of this service is to use all energy you produced, e.g with a balcony power plant, by e.g. loading a portable battery.
This can be achieved by plug in your battery into a smartplug. The smartplug is turned on/off dynamically, depending on your current electricity consumption. 

The service provides the post method *add_watt_consumption* with the value to be provided as a raw data string. 

## Installation ##
The python package can be installed from PyPi (https://pypi.org/project/smartplug-energy-controller/)

1. Navigate to the folder where the virtual environment shall be created (e.g. your home dir):
```bash
cd ~
```
2. Create virtual environment (this will create a new folder *smart_meter_py_env*):
```bash
python3 -m venv smart_meter_py_env
```
3. Activate the virtual environment
```bash
source smart_meter_py_env/bin/activate
```
4. Upgrade pip and setuptools
```bash
python3 -m pip install --upgrade pip setuptools
```
5. Install smartplug-energy-controller
```bash
pip install smartplug-energy-controller
```
6. Provide environment variables (e.g. in your ~/.profile).
```bash
TAPO_PLUG_IP='192.168.x.x'
TAPO_CONTROL_USER='your_user'
TAPO_CONTROL_PASSWD='your_passwd'

# Following values can be considered as parameters, but have to be provided as env variables 
# (see: https://fastapi.tiangolo.com/advanced/settings/#create-the-settings-object)
EVAL_COUNT=10
EXPECTED_CONSUMPTION=200
CONSUMER_EFFICIENCY=0.5
LOG_FILE='path_to_file'
LOG_LEVEL=20
```

## Autostart after reboot and on failure ##
Create a systemd service by opening the file */etc/systemd/system/smartplug_energy_controller.service* and copy paste the following contents. Replace User/Group/ExecStart accordingly. 
```bash
[Unit]
Description=smartplug_energy_controller
Documentation=https://github.com/die-bauerei/smartplug-energy-controller
After=network-online.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
UMask=002
Restart=on-failure
RestartSec=5s
Environment="EVAL_COUNT=10"
Environment="EXPECTED_CONSUMPTION=200"
Environment="CONSUMER_EFFICIENCY=0.5"
Environment="LOG_FILE=/home/ubuntu/plug_controller.log"
Environment="LOG_LEVEL=20"
ExecStart=/usr/bin/bash -lc "source /home/ubuntu/smart_meter_py_env/bin/activate && uvicorn --host 0.0.0.0 --port 8000 smartplug_energy_controller.app:app > /dev/null"

[Install]
WantedBy=multi-user.target
```

Now execute the following commands to enable autostart:
```bash
sudo systemctl --system daemon-reload
sudo systemctl enable smartplug_energy_controller.service
```

It is now possible to start, stop, restart and check the status of smartplug-energy-controller with:
```bash
sudo systemctl start smartplug_energy_controller.service
sudo systemctl stop smartplug_energy_controller.service
sudo systemctl restart smartplug_energy_controller.service
sudo systemctl status smartplug_energy_controller.service
```

## Usage in conjunction with openHAB ##

To use this service you need to get the consumption values from your smart-meter. There are of course lots of different ways to achieve this.
A possible setup could include:
- Read data from your smart-meter and push them to openHAB:
    - https://github.com/die-bauerei/smart-meter-to-openhab
    - ...
- Let openHAB send the post request to this service. 

Again, there are for sure many ways to do this. In case you are a python developer you may know https://github.com/spacemanspiff2007/HABApp. With HABApp you can accomplish this with a Rule like this:
```python
class NumberItemStateChangedHttpForwarder(HABApp.Rule):
    def __init__(self, item_to_fwd : str, post_req_url : str) -> None:
        """
        Listen to a state changed event of a NumberItem and forward the value via a http post request
            Parameters:
                item_to_fwd (str): openHAB number item
                post_req_url (str): Full URL to send the post request to
        """
        super().__init__()
        self._url=post_req_url
        item=NumberItem.get_item(item_to_fwd)
        item.listen_event(self._item_state_changed, ItemStateChangedEventFilter())

    async def _item_state_changed(self, event):
        assert isinstance(event, ItemStateChangedEvent), type(event)
        try:
            async with self.async_http.post(self._url, data=str(event.value)) as response:
                if response.status != http.HTTPStatus.OK:
                    log.warning(f"Failed to forward value via post request to {self._url}. Return code: {response.status}. Text: {await response.text()}")
        except Exception as exc:
            log.error(f"Caught Exception: {exc}")
```
