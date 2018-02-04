import os

from flask import Flask, Markup
from flask_frozen import Freezer
from markdown import Markdown

from .helpers import walk_dir, normalize_url, remove_suffix
from .exceptions import ConfigError
from . import generators

class App(Flask):

    def __init__(self, root_path=None, *args, **kwargs):
        if root_path is None: root_path = os.getcwd()
        super().__init__("clearice", *args, root_path=root_path, **kwargs)

        # Normally, exceptions that occur when a url is requested are caught by
        # flask and a 500 status is returned. This causes the exception to be
        # propogated instead. See `flask.Flask.test_client()`.
        self.testing = True

        self.content_dir = os.path.join(self.root_path, "content")
        self.consumed_files = set()
        self._generators = []
        self.collections = Collections(self)

        # Markdown Template Filter
        md_parser = Markdown()
        md_convert = lambda text: Markup(md_parser.reset().convert(text))
        self.add_template_filter(md_convert, "markdown")

        # Adding `Collection` generator for each _collection.yaml file
        for abspath, relpath, filename in walk_dir(self.content_dir):
            if filename == "_collection.yaml":
                url = normalize_url(remove_suffix(relpath, "_collection.yaml"))
                generator = generators.Collection(url, abspath)
                self.add_generator(generator)

        # Add template markdown generator
        self.add_generator(generators.MarkdownGenerator())

    def consume(self, abspath):
        assert os.path.isabs(abspath)
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

        freezer = Freezer(self)
        freezer.freeze()

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
