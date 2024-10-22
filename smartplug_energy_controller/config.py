from ruamel.yaml import YAML
from dataclasses import dataclass
from pathlib import Path
from typing import Union, Dict, List
from functools import cached_property

@dataclass(frozen=True)
class SmartPlugConfig():
    type : str
    enabled : bool = True # When disabled, the plug can be controlled manually.
    # Expected consumption value in Watt of consumer(s) being plugged into the Plug
    expected_consumption_in_watt : int = 0
    # Efficiency of the consumer(s) being plugged into the Plug (0 < x < 1)
    # 0 means that the plug should be turned on only when no additional energy has to be obtained from the provider. 
    # 1 means that the plug should be turned on when the additional obtained energy from the provider is equal to the expected consumption.
    consumer_efficiency : float = 0

@dataclass(frozen=True)
class TapoSmartPlugConfig(SmartPlugConfig):
    id : str = '' # ip-adress
    auth_user : str = '' # user to authenticate.
    auth_passwd : str = '' # passwd to authenticate.

@dataclass(frozen=True)
class OpenHabSmartPlugConfig(SmartPlugConfig):
    oh_thing_name : str = ''
    oh_switch_item_name : str = ''
    oh_power_consumption_item_name : str = ''
    # optional. can be used to enable/disable a smartplug in terms of usage from this service. When disabled, the plug can be controlled manually.
    oh_automation_enabled_switch_item_name : str = '' 

@dataclass(frozen=True)
class OpenHabConnectionConfig():
    oh_url : str = ''
    oh_user : str = ''
    oh_password : str = ''

@dataclass(frozen=True)
class GeneralConfig():
    # Write logging to this file instead of to stdout
    log_file : Union[None, Path] = None
    log_level : int = 20
    # Time in minutes for which the energy consumption should be evaluated
    # Rule of thumb:
    # Use high value (~10) in case you do NOT propagate the produced watt.
    # Use low value (~2) in case you do propagate the produced watt.
    eval_time_in_min : int = 5

class ConfigParser():
    def __init__(self, file : Path, habapp_config : Path) -> None:
        self._smart_plugs : Dict[str, SmartPlugConfig] = {}
        self._oh_connection : Union[None, OpenHabConnectionConfig] = None
        yaml=YAML(typ='safe', pure=True)
        data=yaml.load(file)
        self._read_from_dict(data)
        if 'openhab_connection' in data:
            self._oh_connection=OpenHabConnectionConfig(data['openhab_connection']['oh_url'], 
                                                        data['openhab_connection']['oh_user'], 
                                                        data['openhab_connection']['oh_password'])
            self._transfer_to_habapp(data['openhab_connection'], habapp_config)

    @property
    def general(self) -> GeneralConfig:
        return self._general
    
    @property
    def oh_connection(self) -> Union[None, OpenHabConnectionConfig]:
        return self._oh_connection

    @cached_property
    def plug_uuids(self) -> List[str]:
        return list(self._smart_plugs.keys())
    
    def plug(self, plug_uuid : str) -> SmartPlugConfig:
        return self._smart_plugs[plug_uuid]

    def _read_from_dict(self, data : dict):
        self._general=GeneralConfig(Path(data['log_file']), data['log_level'], data['eval_time_in_min'])
        for plug_uuid in data['smartplugs']:
            plug_cfg=data['smartplugs'][plug_uuid]
            if plug_cfg['type'] == 'tapo':
                self._smart_plugs[plug_uuid]=TapoSmartPlugConfig(
                plug_cfg['type'], plug_cfg['enabled'], plug_cfg['expected_consumption_in_watt'], plug_cfg['consumer_efficiency'], 
                plug_cfg['id'], plug_cfg['auth_user'], plug_cfg['auth_passwd'])
            elif plug_cfg['type'] == 'openhab':
                self._smart_plugs[plug_uuid]=OpenHabSmartPlugConfig(
                plug_cfg['type'], plug_cfg['enabled'], plug_cfg['expected_consumption_in_watt'], plug_cfg['consumer_efficiency'], 
                plug_cfg['oh_thing_name'], plug_cfg['oh_switch_item_name'], plug_cfg['oh_power_consumption_item_name'], 
                plug_cfg['oh_automation_enabled_switch_item_name'])
            else:
                raise ValueError(f"Unknown Plug type: {plug_cfg['type']}")
    
    def _transfer_to_habapp(self, data : dict, habapp_config_path : Path):
        # 1. fwd config to habapp config file
        yaml=YAML(typ='safe', pure=True)
        habapp_config=yaml.load(habapp_config_path)
        habapp_config['openhab']['connection']['url'] = data['oh_url']
        habapp_config['openhab']['connection']['user'] = data['oh_user']
        habapp_config['openhab']['connection']['password'] = data['oh_password']
        yaml.dump(habapp_config, habapp_config_path)
        # 2. write openhab item names and plugs to a .env that is later on read by the habapp rules
        with open(f"{habapp_config_path.parent}/.env", 'w') as f:
            if 'oh_watt_obtained_from_provider_item' in data and 'oh_watt_produced_item' in data:
                f.write(f"oh_watt_obtained_from_provider_item={data['oh_watt_obtained_from_provider_item']}\n")
                f.write(f"oh_watt_produced_item={data['oh_watt_produced_item']}\n")
            openhab_plug_ids = [plug_uuid for plug_uuid in self.plug_uuids if self.plug(plug_uuid).type == 'openhab']
            f.write(f"openhab_plug_ids={','.join(openhab_plug_ids)}\n")