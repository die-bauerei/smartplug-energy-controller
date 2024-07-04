import logging
import uvicorn

from pathlib import Path
root_path = str( Path(__file__).parent.absolute() )

from fastapi import FastAPI, Request
from typing import Union, cast
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from smartplug_energy_controller.plug_controller import *
from smartplug_energy_controller.plug_manager import PlugManager
from smartplug_energy_controller.config import ConfigParser

class Settings(BaseSettings):
    config_path : Path

def create_logger(file : Union[Path, None]) -> logging.Logger:
    logger = logging.getLogger('smartplug-energy-controller')
    log_handler : Union[logging.FileHandler, logging.StreamHandler] = logging.FileHandler(file) if file else logging.StreamHandler() 
    formatter = logging.Formatter("%(levelname)s: %(asctime)s: %(message)s")
    log_handler.setFormatter(formatter)
    logger.addHandler(log_handler)
    return logger

try:
    import importlib.metadata
    __version__ = importlib.metadata.version('smartplug_energy_controller')
except:
    __version__ = 'development'

settings = Settings() # type: ignore
cfg_parser = ConfigParser(settings.config_path, Path(f"{root_path}/../oh_to_smartplug_energy_controller/config.yml"))
logger=create_logger(cfg_parser.general.log_file)
logger.setLevel(logging.INFO)
logger.info(f"Starting smartplug-energy-controller version {__version__}")
logger.setLevel(cfg_parser.general.log_level)
manager=PlugManager.create(logger, cfg_parser)

app = FastAPI()

class PlugValues(BaseModel):
    watt_consumed_at_plug: float
    online: bool
    is_on: bool

class SmartMeterValues(BaseModel):
    watt_obtained_from_provider: float
    watt_produced: Union[None, float] = None

@app.get("/")
async def root(request: Request):
    return {"message": "Hallo from smartplug-energy-controller"}

@app.get("/plug-info/{uuid}")
async def plug_info(uuid: str):
    openhab_plug_controller=cast(OpenHabPlugController, manager.plug(uuid))
    return openhab_plug_controller.oh_names

@app.get("/plug-state/{uuid}")
async def read_plug(uuid: str):
    return await manager.plug(uuid).state

@app.put("/plug-state/{uuid}")
async def update_plug(uuid: str, plug_values: PlugValues):
    openhab_plug_controller=cast(OpenHabPlugController, manager.plug(uuid))
    await openhab_plug_controller.update_values(plug_values.watt_consumed_at_plug, plug_values.online, plug_values.is_on)

@app.put("/smart-meter")
async def smart_meter(smart_meter_values: SmartMeterValues):
    await manager.add_smart_meter_values(smart_meter_values.watt_obtained_from_provider, smart_meter_values.watt_produced)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)