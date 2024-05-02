import os

if 'TAPO_CONTROL_USER' not in os.environ:
    raise ValueError(f"Failed to initialize smartplug-energy-controller. Required env variable 'TAPO_CONTROL_USER' not found")
if 'TAPO_CONTROL_PASSWD' not in os.environ:
    raise ValueError(f"Failed to initialize smartplug-energy-controller. Required env variable 'TAPO_CONTROL_PASSWD' not found")
if 'TAPO_PLUG_IP' not in os.environ:
    raise ValueError(f"Failed to initialize smartplug-energy-controller. Required env variable 'TAPO_PLUG_IP' not found")