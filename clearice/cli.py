
import sys

from click import progressbar

from .app import App
from .exceptions import ClearIceException

def _main(app=None):
    quiet = False

    if not app:
        app = App()
    app.print_progress = not quiet

    if quiet:
        app.generate()
    else:
        app.generate_urls()
        prog = progressbar(
            app.build_content(),
            length=app.n_urls,
            label="Rendering Pages",
            item_show_func=lambda page: page,
        )
        with prog as urls:
            for url in urls:
                pass
        print("Generated {} pages".format(app.n_urls))

def main(*args, **kwargs):
    try:
        _main(*args, **kwargs)
    except ClearIceException as e:
        sys.stderr.write(str(e)+'\n')
        sys.exit(-1)

if __name__ == "__main__":
    main()
