from ruamel.yaml import YAML
from dataclasses import dataclass
from pathlib import Path
from typing import Union, Dict, List
from functools import cached_property

@dataclass(frozen=True)
class SmartPlugConfig():
    id : str = '' # e.g. ip-adress
    auth_user : str = '' # user to authenticate
    auth_passwd : str = '' # passwd to authenticate
    # Expected consumption value in Watt of consumer(s) being plugged into the Plug
    expected_consumption_in_watt : int = 0
    # Efficiency of the consumer(s) being plugged into the Plug (0 < x < 1)
    # 0 means that the plug should be turned on only when no energy has to be obtained from the provider. 
    # 1 means that the plug should be turned on when the the obtained energy from the provider is equal to the expected consumption.
    consumer_efficiency : float = 0

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
    def __init__(self, file : Path) -> None:
        self._smart_plugs : Dict[str, SmartPlugConfig] = {}
        yaml=YAML(typ='safe', pure=True)
        self._read_from_dict(yaml.load(file))

    @property
    def general(self) -> GeneralConfig:
        return self._general
    
    @cached_property
    def plug_uuids(self) -> List[str]:
        return list(self._smart_plugs.keys())
    
    def plug(self, plug_uuid : str) -> SmartPlugConfig:
        return self._smart_plugs[plug_uuid]
        
    def _read_from_dict(self, data : dict):
        self._general=GeneralConfig(Path(data['log_file']), data['log_level'], data['eval_time_in_min'])
        for plug_uuid in data['smartplugs']:
            plug_cfg=data['smartplugs'][plug_uuid]
            self._smart_plugs[plug_uuid]=SmartPlugConfig(
                plug_cfg['id'], plug_cfg['auth_user'], plug_cfg['auth_passwd'], plug_cfg['expected_consumption_in_watt'], plug_cfg['consumer_efficiency'])