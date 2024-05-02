import logging
import argparse
import os
import uvicorn

from fastapi import FastAPI, Request
from pathlib import Path
from typing import Union
from dotenv import load_dotenv

from smartplug_energy_controller.plug_controller import TapoPlugController

def create_logger(file : Union[str, None]) -> logging.Logger:
    logger = logging.getLogger('smartplug-energy-controller')
    log_handler : Union[logging.FileHandler, logging.StreamHandler] = logging.FileHandler(file) if file else logging.StreamHandler() 
    formatter = logging.Formatter("%(levelname)s: %(asctime)s: %(message)s")
    log_handler.setFormatter(formatter)
    logger.addHandler(log_handler)
    return logger

def log_level_from_arg(verbosity_count : int) -> int:
    if verbosity_count == 0:
        return logging.ERROR
    if verbosity_count == 1:
        return logging.WARN
    if verbosity_count == 2:
        return logging.INFO
    return logging.DEBUG

def create_args_parser() -> argparse.ArgumentParser:
    parser=argparse.ArgumentParser(description=f"Turning off/on Tapo Plug based on watt consumption.")
    parser.add_argument("--dotenv_path", type=Path, required=False, help=f"Provide the required environment variables in this .env file \
                        or by any other means (e.g. in your ~/.profile)")
    parser.add_argument("--eval_count", type=int, required=False, default=10, 
                        help="Consider this number of watt consumption values for evaluation")
    parser.add_argument("--expected_consumption", type=float, required=False, default=10, 
                        help="Expected consumption value in Watt of consumer(s) being plugeed into the Tapo Plug")
    parser.add_argument("--logfile", type=Path, required=False, help="Write logging to this file instead of to stdout")
    parser.add_argument('-v', '--verbose', action='count', default=0)
    return parser

parser=create_args_parser()
args = parser.parse_args()
if args.dotenv_path:
    load_dotenv(dotenv_path=args.dotenv_path)
logger=create_logger(args.logfile)
logger.setLevel(logging.INFO)
logger.info(f"Starting smartplug-energy-controller")
logger.setLevel(log_level_from_arg(args.verbose))
controller=TapoPlugController(logger, args.eval_count, args.expected_consumption, os.getenv('TAPO_CONTROL_USER', default=''), 
                            os.getenv('TAPO_CONTROL_PASSWD', default=''), os.getenv('TAPO_PLUG_IP', default=''))

app = FastAPI()

@app.get("/")
async def root(request: Request):
    return {"message": "Hallo from Tapo Plug Controller"}

@app.post("/add_watt_consumption")
async def add_watt_consumption(request: Request):
    value = float(await request.body())
    await controller.add_watt_consumption(value)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)