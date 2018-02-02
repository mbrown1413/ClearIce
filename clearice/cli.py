
import sys

from flask_frozen import Freezer

from .app import build_app
from .exceptions import ClearIceException

def main(catch_exceptions=True):
    to_catch = ()
    if catch_exceptions:  # pragma: no cover
        to_catch = ClearIceException  # pragma: no cover
    try:
        app = build_app()
        freezer = Freezer(app)
        freezer.freeze()
    except to_catch as e:
        sys.stderr.write(str(e)+'\n')  # pragma: no cover
        sys.exit(-1)  # pragma: no cover

    return app
