import logging
import uvicorn
import os

from dotenv import load_dotenv
from pathlib import Path
root_path = str( Path(__file__).parent.absolute() )

from fastapi import FastAPI, Request
from typing import Union
from pydantic import BaseModel
from pydantic_settings import BaseSettings

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

if os.path.exists(f"{root_path}/.env"):
    load_dotenv(f"{root_path}/.env")

try:
    import importlib.metadata
    __version__ = importlib.metadata.version('smartplug_energy_controller')
except:
    __version__ = 'development'

settings = Settings()
cfg_parser = ConfigParser(settings.config_path)
logger=create_logger(cfg_parser.general.log_file)
logger.setLevel(logging.INFO)
logger.info(f"Starting smartplug-energy-controller version {__version__}")
logger.setLevel(cfg_parser.general.log_level)
manager=PlugManager(logger, cfg_parser)

app = FastAPI()

class PlugValues(BaseModel):
    watt_obtained_from_provider: float
    watt_consumed_at_plug: float

@app.get("/")
async def root(request: Request):
    return {"message": "Hallo from smartplug-energy-controller"}

@app.get("/plugs/{uuid}")
async def read_plug(uuid: str):
    return manager.plug(uuid).state_proposal

@app.put("/plugs/{uuid}")
async def update_plug(uuid: str, plug_values: PlugValues):
    await manager.plug(uuid).update_values(plug_values.watt_obtained_from_provider, plug_values.watt_consumed_at_plug)
    return manager.plug(uuid).state_proposal

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)