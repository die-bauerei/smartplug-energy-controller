import logging
from typing import Union
from pathlib import Path
from smartplug_energy_controller.config import ConfigParser, OpenHabConnectionConfig
from smartplug_energy_controller.utils import OpenhabConnectionProtocol, OpenhabConnection

try:
    import importlib.metadata
    __version__ = importlib.metadata.version('smartplug_energy_controller')
except:
    __version__ = 'development'

_logger : Union[logging.Logger, None] = None
def init_logger(file : Union[Path, None], level) -> None:
    global _logger
    if _logger is None:
        _logger = logging.getLogger('smartplug-energy-controller')
        log_handler : Union[logging.FileHandler, logging.StreamHandler] = logging.FileHandler(file) if file else logging.StreamHandler() 
        formatter = logging.Formatter("%(levelname)s: %(asctime)s: %(message)s")
        log_handler.setFormatter(formatter)
        _logger.addHandler(log_handler)
        _logger.setLevel(logging.INFO)
        _logger.info(f"Starting smartplug-energy-controller version {__version__}")
        _logger.setLevel(level)

def get_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        raise RuntimeError(f"Unable to get logger. It has not been initialized yet.")
    return _logger

_oh_connection : Union[OpenhabConnectionProtocol, None] = None
def init_oh_connection(oh_con_cfg : Union[OpenHabConnectionConfig, None]) -> None:
    global _oh_connection
    _oh_connection = OpenhabConnection(oh_con_cfg, get_logger()) if oh_con_cfg else None

def get_oh_connection() -> Union[OpenhabConnectionProtocol, None]:
    global _oh_connection
    return _oh_connection

def init(cfg_parser : ConfigParser) -> None:
    init_logger(cfg_parser.general.log_file, cfg_parser.general.log_level)
    init_oh_connection(cfg_parser.oh_connection)