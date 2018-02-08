
import sys

from click import progressbar

from .app import App
from .exceptions import ClearIceException

def _main():
    quiet = False
    app = App(print_progress=not quiet)

    if quiet:
        app.generate()

    else:
        n_generated = 0
        app.generate_urls()
        prog = progressbar(
            app.render_content(),
            length=app.n_urls,
            label="Rendering Pages",
            item_show_func=lambda page: page.url if page else "",
        )
        with prog as urls:
            for url in urls:
                n_generated += 1
        print("Generated {} pages".format(n_generated))

def main():
    try:
        _main()
    except ClearIceException as e:
        sys.stderr.write(str(e)+'\n')
        sys.exit(-1)

if __name__ == "__main__":
    main()
