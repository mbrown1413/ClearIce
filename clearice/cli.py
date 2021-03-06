
import sys
import argparse
import os
from contextlib import contextmanager

from click import progressbar

from .app import App
from .exceptions import ClearIceException

def get_app(args):
    kwargs = {}
    if args.build_dir:
        kwargs['build_dir'] = args.build_dir
    return App(root_dir=args.root, **kwargs)

@contextmanager
def print_errors(exit_on_error=True):
    try:
        yield None
    except ClearIceException as e:
        sys.stderr.write(str(e)+'\n')
        if exit_on_error:
            sys.exit(-1)

def cmd_generate(args, quiet=False):

    app = get_app(args)
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

def cmd_watch(args, serve=False):
    import time
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    class EventHandler(FileSystemEventHandler):

        def __init__(self, build_dir):
            self.build_dir = build_dir
            self.last_gen_time = 0
            self.build_timeout = 0.5

        def on_any_event(self, event):
            if event.src_path.startswith(self.build_dir):
                return

            t = time.time()
            if t - self.last_gen_time >= self.build_timeout:
                time.sleep(0.2)
                self.last_gen_time = t
                self.generate()

        def generate(self):
            print()
            print("Rebuilding...")
            with print_errors(exit_on_error=False):
                cmd_generate(args, quiet=True)
            print("Done")

    # Find out what build dir will be by instantiating app
    build_dir = get_app(args).build_dir

    handler = EventHandler(build_dir)
    handler.generate()

    observer = Observer()
    observer.schedule(handler, args.root, recursive=True)
    observer.start()

    if serve:
        from http.server import HTTPServer, SimpleHTTPRequestHandler
        os.chdir(build_dir)
        server = HTTPServer((args.bind, args.port), SimpleHTTPRequestHandler)

    try:
        if serve:
            server.serve_forever()
        else:
            while True:
                time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        if serve:
            server.server_close()
    observer.join()

def cmd_serve(args):
    cmd_watch(args, serve=True)

def main():
    parser = argparse.ArgumentParser(
        description="A simple extensible static site generator."
    )
    parser.add_argument("--root", '-r', default=os.getcwd(),
        help='Root directory of the site, containing the content/ and '
        'templates/ directories. (default current directory)')
    parser.add_argument("--build-dir", "-b", default=None,
        help="Directory to output built site. If relative, it is relative to "
        "the root directory.")
    subparsers = parser.add_subparsers()

    # Generate Command Parser
    gen_parser = subparsers.add_parser('generate',
        aliases=('gen',),
        help='Generate a static site (default)')
    gen_parser.set_defaults(func=cmd_generate)

    # Watch Command Parser
    watch_parser = subparsers.add_parser('watch',
        help='Re-generate site whenever files in the current directory change.')
    watch_parser.set_defaults(func=cmd_watch)

    # Serve Command Parser
    serve_parser = subparsers.add_parser('serve',
        help='Serve build directory on the built-in webserver, and re-generate'
        'site whenever files in the current directory change.')
    serve_parser.add_argument("--port", "-p", default=8000, type=int,
        help="Port to listen on (defalut: 8000)")
    serve_parser.add_argument("--bind", "-b", metavar="ADDRESS", default='localhost',
        help="Bind address to listen on (defalut: localhost)")
    serve_parser.set_defaults(func=cmd_serve)

    # Help Command Parser
    help_parser = subparsers.add_parser('help',
        help="show command usage")
    help_parser.set_defaults(func=lambda args: parser.print_help())

    # Parse and call command
    args = parser.parse_args()
    func = args.func if 'func' in args else cmd_generate
    with print_errors():
        func(args)

if __name__ == "__main__":
    main()
