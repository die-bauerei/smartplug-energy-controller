#!/bin/bash

# Usage:
# Call this script for installation of python and all dependencies (using poetry)

# change into the directory of this script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $SCRIPT_DIR

# read python version
PY_VERSION=$(python3 print-from-setup-cfg.py mypy python_version)

# needed for installation of python 3.11
sudo apt install software-properties-common -y
sudo -E add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update

# install python and wget
sudo apt-get -y install python$PY_VERSION python$PY_VERSION-dev python$PY_VERSION-distutils wget
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python$PY_VERSION 1

# install poetry. https://stackoverflow.com/questions/592620/how-can-i-check-if-a-program-exists-from-a-bash-script
if ! command -v poetry &> /dev/null; then
    wget -O install-poetry.py https://install.python-poetry.org
    python3 install-poetry.py --yes
 else
    echo "poetry already installed"
 fi

# update poetry, install packages
~/.local/bin/poetry self update
~/.local/bin/poetry env use /usr/bin/python$PY_VERSION
~/.local/bin/poetry config virtualenvs.in-project true
~/.local/bin/poetry install
# if install fails, check https://github.com/MISP/PyMISP/issues/669
# to uninstall call: python3 install-poetry.py --uninstall

# setup tab completion in bash. You may need to restart your shell in order for the changes to take effect.
# NOTE: in case poetry can not be found, add export PATH="$HOME/.local/bin:$PATH" to bashrc 
# (https://stackoverflow.com/questions/69830902/poetry-installation-with-windows-wsl-not-working-ignoring-home)
sudo sh -c "${HOME}/.local/bin/poetry completions bash > /etc/bash_completion.d/poetry.bash-completion"

# activate venv
sleep 1
source .venv/bin/activate