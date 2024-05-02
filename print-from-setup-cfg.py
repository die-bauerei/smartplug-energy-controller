import configparser
import argparse
from typing import Any

def create_args_parser() -> argparse.ArgumentParser:
    parser=argparse.ArgumentParser(description="Helper script to get information from pyproject.toml")
    parser.add_argument('tags', metavar='N', type=str, nargs='+')
    return parser

if __name__ == '__main__':
    parser=create_args_parser()
    args = parser.parse_args()
    config: Any = configparser.ConfigParser()
    config.read('setup.cfg')
    for tag in args.tags:
        config=config[tag]
    print(config)