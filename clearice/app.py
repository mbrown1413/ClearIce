import os

from flask import Flask, Markup
from flask_frozen import Freezer
from markdown import Markdown

from .helpers import walk_dir, normalize_url, remove_suffix
from .exceptions import ConfigError
from . import generators

class App(Flask):

    def __init__(self, root_path=None, print_progress=False, *args, **kwargs):
        if root_path is None: root_path = os.getcwd()
        self.print_progress = print_progress

        self.n_urls = 0
        super().__init__("clearice", *args, root_path=root_path, **kwargs)

        # Normally, exceptions that occur when a url is requested are caught by
        # flask and a 500 status is returned. This causes the exception to be
        # propogated instead. See `flask.Flask.test_client()`.
        self.testing = True

        self.content_dir = os.path.join(self.root_path, "content")
        self.consumed_files = set()
        self._generators = []
        self.collections = _Collections(self)

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

    def add_url_rule(self, rule, endpoint=None, view_func=None, **options):
        super().add_url_rule(rule, endpoint, view_func, **options)
        self.n_urls += 1

    def consume(self, abspath):
        assert os.path.isabs(abspath)
        self.consumed_files.add(abspath)

        if self.print_progress:
            print("\rProcessed {} files".format(len(self.consumed_files)), end="")  # pragma: nocover

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

    def generate_urls(self):
        """Reads content files and metadata by running all generators."""
        for generator in self._generators:
            generator(self)
        if self.print_progress:
            print()

        # Used to optimize URL matching (see "Optimization hack" below)
        self.fast_map = {}
        for rule in self.url_map.iter_rules():
            self.fast_map[rule.endpoint] = rule

    def render_content(self):
        """Yield pages as they are rendered."""
        freezer = Freezer(self)
        yield from freezer.freeze_yield()

    def generate(self):
        """The main no-frills entry point to generate content."""
        self.generate_urls()
        for url in self.render_content():
            pass

    # Optimization hack:
    #
    # The URL resolution system of werkzeug is way more complicated than we
    # need. We always have a simple one-to-one mapping of urls to rules, so
    # werkzeug's method of going through each rule one by one is very
    # inefficient when there are many URLs.
    #
    # Instead, we build a mapping of endpoints to rules (`self.fast_map`) and
    # search that first to find the rule. If a mapping is found,
    # `create_url_adapter` returns a simple adapter that always returns the
    # found rule.
    def create_url_adapter(self, request):
        normal_adapter = super().create_url_adapter(request)
        if request is not None and self.fast_map:
            rule = self.fast_map.get(request.path, None)
            if rule:
                return _Adapter(normal_adapter, rule)
        return normal_adapter

class _Adapter():
    """
    A URL mapping adapter (like `werkzeug.routing.MapAdapter`) which always
    returns the given rule, or falls back to the given adapter if it doesn't
    know how to handle things.
    """

    def __init__(self, normal_adapter, rule):
        self.normal_adapter = normal_adapter
        self.rule = rule

    def match(self, path_info=None, method=None, return_rule=False,
              query_args=None):
        if return_rule:
            return self.rule, {}
        else:
            raise AssertionError()  # pragma: nocover

    def build(self, *args, **kwargs):
        return self.normal_adapter.build(*args, **kwargs)

class _Collections():
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
