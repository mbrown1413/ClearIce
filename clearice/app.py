import os

from flask import Flask, Markup
from markdown import Markdown

from .helpers import walk_dir, normalize_url, remove_suffix
from .exceptions import ConfigError
from . import generators

DEFAULT_CONTENT_DIR = "content/"

class App(Flask):

    def __init__(self, content_dir, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.content_dir = content_dir

        # Normally, exceptions that occur when a url is requested are caught by
        # flask and a 500 status is returned. This causes the exception to be
        # propogated instead. See `flask.Flask.test_client()`.
        self.testing = True

        self.consumed_files = set()
        self._generators = []
        self.collections = Collections(self)

    def consume(self, abspath):
        self.consumed_files.add(abspath)

    def is_consumed(self, abspath):
        return abspath in self.consumed_files

    def add_generator(self, gen):

        # Check name for uniqueness
        if hasattr(gen, 'name'):
            for gen2 in self._generators:
                if hasattr(gen2, 'name') and gen.name == gen2.name:
                    raise ConfigError(None, 'Cannot have two generators with '
                            'the same name "{}"'.format(gen.name))

        self._generators.append(gen)

    def generate(self):
        for generator in self._generators:
            generator(self)

class Collections():
    """Passthrough object for handy access in templates."""

    def __init__(self, app):
        self.app = app

    def __iter__(self):
        return filter(lambda g: g.is_collection, self.app._generators)

    def __getattr__(self, name):
        for c in self:
            if c.name == name:
                return c

    def __len__(self):
        return sum([1 for collection in self])

def build_app():
    app = App(DEFAULT_CONTENT_DIR, __name__, root_path=os.getcwd())

    # Markdown Template Filter
    md_parser = Markdown()
    md_convert = lambda text: Markup(md_parser.reset().convert(text))
    app.add_template_filter(md_convert, "markdown")

    # Adding `Collection` generator for each _collection.yaml file
    for abspath, relpath, filename in walk_dir(DEFAULT_CONTENT_DIR):
        if filename == "_collection.yaml":
            url = normalize_url(remove_suffix(relpath, "_collection.yaml"))
            generator = generators.Collection(url, abspath)
            app.add_generator(generator)

    # Add template markdown generator
    app.add_generator(generators.MarkdownGenerator())

    app.generate()
    return app
