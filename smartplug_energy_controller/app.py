import uvicorn

from pathlib import Path
root_path = str( Path(__file__).parent.absolute() )

from fastapi import FastAPI, Request, HTTPException
from fastapi_utils.tasks import repeat_every
from typing import Union, cast
from pydantic import BaseModel
from pydantic_settings import BaseSettings
from datetime import datetime

from smartplug_energy_controller import init, get_logger
from smartplug_energy_controller.plug_controller import *
from smartplug_energy_controller.plug_manager import PlugManager
from smartplug_energy_controller.config import ConfigParser

class Settings(BaseSettings):
    config_path : Path
    smartplug_energy_controller_port : int

settings = Settings() # type: ignore
cfg_parser = ConfigParser(settings.config_path, Path(f"{root_path}/../oh_to_smartplug_energy_controller/config.yml"))
init(cfg_parser)
manager=PlugManager.create(get_logger(), cfg_parser)
app = FastAPI()

class PlugValues(BaseModel):
    watt_consumed_at_plug: float
    online: bool
    is_on: bool

class SmartMeterValues(BaseModel):
    watt_obtained_from_provider: float
    watt_produced: Union[None, float] = None
    timestamp : Union[None, datetime] = None

@app.get("/")
async def root(request: Request):
    return {"message": "Hallo from smartplug-energy-controller"}

@app.get("/plug-info/{uuid}")
async def plug_info(uuid: str):
    return manager.plug(uuid).info

@app.get("/plug-state/{uuid}")
async def read_plug(uuid: str):
    return await manager.plug(uuid).state

@app.put("/plug-state/{uuid}/enable")
async def enable_plug(uuid: str):
    await (manager.plug(uuid).set_enabled(True))

@app.put("/plug-state/{uuid}/disable")
async def disable_plug(uuid: str):
    await (manager.plug(uuid).set_enabled(False))

@app.put("/plug-state/{uuid}")
async def update_plug(uuid: str, plug_values: PlugValues):
    if not isinstance(manager.plug(uuid), OpenHabPlugController):
        raise HTTPException(status_code=501, detail=f"Plug with uuid {uuid} is not an OpenHabPlugController. Only OpenHabPlugController can be updated.")
    openhab_plug_controller=cast(OpenHabPlugController, manager.plug(uuid))
    await openhab_plug_controller.update_values(plug_values.watt_consumed_at_plug, plug_values.online, plug_values.is_on)

@app.get("/smart-meter")
async def smart_meter_get():
    return await manager.state

@app.put("/smart-meter")
async def smart_meter_put(smart_meter_values: SmartMeterValues):
    await manager.add_smart_meter_values(smart_meter_values.watt_obtained_from_provider, smart_meter_values.watt_produced, smart_meter_values.timestamp)

@app.on_event("startup")
@repeat_every(seconds=60*30)
async def reset_base_load():
    await manager.reset_base_load()

def serve():
    uvicorn.run(app, host="0.0.0.0", port=settings.smartplug_energy_controller_port)

if __name__ == "__main__":
    serve()