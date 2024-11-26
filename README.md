# smartplug-energy-controller

A microservice to turn a smartplug on/off depending on current electricity consumption.
The intention of this service is to use all energy you produced, e.g with a balcony power plant, by e.g. loading a portable battery.
This can be achieved by plug in your battery into a smartplug. The smartplug is turned on/off dynamically, depending on your current electricity consumption. 

The service is especially useful when your electricity meter supports OBIS 1.8.x only (no OBIS 2.8.x).
In such a scenario you can give this service your current electricity meter value (obtained watt from provider) and your current watt production (e.g. from a balcony power plant) and it calculates a reasonable point when to turn your smartplugs on/off.

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
CONFIG_PATH=full/path/to/config.yml
SMARTPLUG_ENERGY_CONTROLLER_PORT=8000
```

## Configuration ##
Everything is configured in the respective config.yml file. See https://github.com/die-bauerei/smartplug-energy-controller/blob/main/tests/data/config.example.yml 

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
Environment="CONFIG_PATH=full/path/to/config.yml"
Environment="SMARTPLUG_ENERGY_CONTROLLER_PORT=8000"
ExecStart=/usr/bin/bash -lc "/home/ubuntu/smart_meter_py_env/bin/smartplug_energy_controller"

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

## Usage of Tapo Smart Plugs ##

The service can control Tapo Smart Plugs via the plugp100 library (https://pypi.org/project/plugp100/).
Have a look at the example config at https://github.com/die-bauerei/smartplug-energy-controller/blob/main/tests/data/config.example

## Usage in conjunction with openHAB ##

To use this service you need to get the consumption values from your smart-meter. There are of course lots of different ways to achieve this.
A possible setup could include:
- Read data from your smart-meter and push them to openHAB:
    - https://github.com/die-bauerei/smart-meter-to-openhab
    - https://tibber.com/de/store/produkt/pulse-ir
    - ...
- Let openHAB send the requests to this service. 

This project includes a service that performs this requests by using HABApp (https://github.com/spacemanspiff2007/HABApp)

NOTE: Make sure to first start smartplug_energy_controller as this will setup the configuration for HABApp. 

*The service expects the smartplug_energy_controller API on http://localhost:$SMARTPLUG_ENERGY_CONTROLLER_PORT*

Create a systemd service */etc/systemd/system/oh_to_smartplug_energy_controller.service* to setup autostart for this service as well:
```bash
[Unit]
Description=Post smart meter values from openHAB to smartplug-energy-controller
Documentation=https://github.com/die-bauerei/smartplug-energy-controller
After=smartplug_energy_controller.service

[Service]
Type=simple
User=ubuntu
Group=ubuntu
UMask=002
Restart=on-failure
RestartSec=5s
#Provide environment variable (e.g. in your ~/.profile). Assignment example see above
Environment="SMARTPLUG_ENERGY_CONTROLLER_PORT=8000"
ExecStart=/usr/bin/bash -lc "source /home/heiko/smart_meter_py_env/bin/activate && /home/ubuntu/smart_meter_py_env/bin/oh_to_smartplug_energy_controller"

[Install]
WantedBy=multi-user.target
```

By setting up a connection to your openHAB instance you can additionally use any Smart Plug you have configured inside your openHAB instance. 
Have a look at the example config at https://github.com/die-bauerei/smartplug-energy-controller/blob/main/tests/data/config.example 

## Troubleshooting ##

- Have a look at the log-file you have given in your config.yml
- Have a look at the HABApp log-file located in smart_meter_py_env/lib/python3.xx/site-packages/oh_to_smartplug_energy_controller/log/HABApp.log. 

## Development ##
Development is done in wsl2 on ubuntu 22.04.
Setting up the development environment on Windows is not supported. But in principal it could be setup as well since no OS specific functionalities are used.

### Setup ###
The project is using [poetry](https://python-poetry.org/) for managing packaging and resolve dependencies.
To install poetry call *install-poetry.sh*. This will install poetry itself as well as python and the required packages as a virtual environment in *.venv*.
Example settings for development in VS Code are provided in *vscode-settings*. (Copy them to *.vscode* folder)
Follow these [instructions](https://docs.pydantic.dev/latest/integrations/visual_studio_code/) to enable proper linting and type checking. 