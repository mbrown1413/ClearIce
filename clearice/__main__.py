
import sys

from .app import App
from .exceptions import ClearIceException

def main():
    try:
        app = App()
        app.generate()
    except ClearIceException as e:
        sys.stderr.write(str(e)+'\n')
        sys.exit(-1)

if __name__ == "__main__":
    main()
