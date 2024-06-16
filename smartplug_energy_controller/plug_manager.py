from logging import Logger
from typing import Dict

from .config import *
from .plug_controller import *

class PlugManager():
    def __init__(self, logger : Logger, cfg_parser : ConfigParser) -> None:
        self._controllers : Dict[str, PlugController] = {}
        for uuid in cfg_parser.plug_uuids:
            self._controllers[uuid]=TapoPlugController(logger, cfg_parser.plug(uuid))
            logger.info(f"Added Tapo Plug Controller for plug with uuid {uuid} using these config values:")
            logger.info(cfg_parser.plug(uuid))

    def plug(self, plug_uuid : str) -> PlugController:
        return self._controllers[plug_uuid]