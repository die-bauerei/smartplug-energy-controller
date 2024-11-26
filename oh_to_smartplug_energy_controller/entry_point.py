import selectors
import subprocess
import sys
from pathlib import Path

config_file=f"{Path(__file__).parent.absolute()}/config.yml"

# https://stackoverflow.com/questions/31833897/python-read-from-subprocess-stdout-and-stderr-separately-while-preserving-order
def main() -> None:
    p = subprocess.Popen(["habapp", "--config", config_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    sel = selectors.DefaultSelector()
    sel.register(p.stdout, selectors.EVENT_READ) # type: ignore
    sel.register(p.stderr, selectors.EVENT_READ) # type: ignore

    while True:
        for key, _ in sel.select():
            data = key.fileobj.read1().decode() # type: ignore
            if key.fileobj is p.stdout:
                print(data, end="")
            else:
                print(data, end="", file=sys.stderr)

if __name__ == '__main__':
    main()