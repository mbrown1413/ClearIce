import os

import yaml
from jinja2 import Template
import jinja2.exceptions

from .helpers import walk_dir, normalize_url, remove_prefix, remove_extension
from .exceptions import ConfigError, YamlError
from . import views

MARKDOWN_EXTENSIONS = [".md", ".markdown"]
MARKDOWN_FILES = list("*"+ext for ext in MARKDOWN_EXTENSIONS)


class GeneratorBase():
    """Base class for content generators.

    Generators can be any callable that receives the app and modifies it. The
    main things that generators do are:

      - Add urls using `app.add_url_rule()`.
      - Consume files by calling `app.consume()`.

    A simple generator might walk the contents directory, `app.content_dir`,
    add a url for every markdown file. Any files it comes across that are
    consumsed already are usually ignored. If the generator doesn't want other
    generators to use a file later, it consumes it.
    """

    # If instances should be part of the collections list `app.collections`.
    is_collection = False

    def __call__(self, app):
        """
        Produces content using `app.add_url_rule()` and consumes files in the
        contents directory using `app.consume()`.
        """
        raise NotImplementedError()  # pragma: no cover

class MarkdownGenerator(GeneratorBase):
    """Adds a `MarkdownView` url for every markdown file."""

    def __call__(self, app):
        files = walk_dir(app.content_dir,
                         exclude=app.consumed_files,
                         fname_patterns=MARKDOWN_FILES)
        for abspath, relpath, filename in files:
            url = normalize_url(remove_extension(relpath))
            view = views.MarkdownView(abspath, app, url)
            app.add_url_rule(url, url, view)
            app.consume(abspath)

class Collection(GeneratorBase):
    #TODO: Describe collections and yaml data.

    is_collection = True

    def __init__(self, url, yaml_path):
        """
        `url`: Determines the base url that pages will be located, as well as
            the base path in the contents directory to look for pages and items.
        `yaml_path`: Absolute path of yaml file that describes the collection.
        """
        self.url = url
        self.yaml_path = yaml_path
        self.items = []

        self.read_yaml_data()

    def __iter__(self):
        return self.items.__iter__()

    def __len__(self):
        return len(self.items)

    def __bool__(self):
        # Empty collections should evaluate to True.
        return True

    def __call__(self, app):
        self.app = app
        self.app.consume(self.yaml_path)

        # Register static pages
        for page in self.pages:
            self.register_page(page)

        # Find and collect items
        for abspath, relpath, filename in self.get_item_files(app):
            if self.file_is_item(app, abspath, relpath, filename):
                view = views.MarkdownView(abspath, app, collection=self)
                url = self.file_to_url(app, view, abspath, relpath, filename)
                view.set_url(url)

                self.items.append(view)
                app.consume(abspath)
                app.add_url_rule(url, url, view)

        # Sort items
        if self.item_order:
            def sortfunc(item):
                value = item.context.get(self.item_order, "")
                return str(value).lower()
            self.items = list(sorted(self.items, key=sortfunc))

    def get_item_files(self, app):
        return walk_dir(app.content_dir,
                        exclude=app.consumed_files,
                        subdir=remove_prefix(self.url, '/'),
                        fname_patterns=MARKDOWN_FILES)

    def file_is_item(self, app, abspath, relpath, filename):
        # If `self.url` is in "/blog/", then "/blog/foo.md" and
        # "/blog/bar/index.md" will be considered items.

        # Remove last part of url separated by slashes. If it matches the
        # collection's url, it's an item.
        url = normalize_url(remove_extension(relpath))
        if url.endswith('/'):
            url = url[:-1]
        try:
            last_slash = url.rindex('/')
        except ValueError:
            return False
        return url[:last_slash+1] == self.url

    def file_to_url(self, app, view, abspath, relpath, filename):
        if self.url_format:
            try:
                template = Template(self.url_format)
                url = template.render(view.context)
            except jinja2.exceptions.TemplateError as e:
                raise ConfigError(self.yaml_path, 'Error with url format: '
                        '{}'.format(e)) from None
            return normalize_url(self.url + url)
        else:
            return normalize_url(remove_extension(relpath))

    def read_yaml_data(self):
        with open(self.yaml_path) as f:
            try:
                data = yaml.load(f)
            except yaml.error.YAMLError as e:
                raise YamlError(self.yaml_path, e) from None
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise ConfigError(self.yaml_path, 'Expected dict describing '
                    'collection, got "{}"'.format(type(data)))

        #TODO: Error if field isn't correct type.
        #TODO: Maybe this needs a more formal schema that can validate
        #      everything.
        self.name = data.pop("name", "") or ""
        self.pages = data.pop("pages", []) or []
        self.context = data.pop("context", {}) or {}
        self.item_order = data.pop("order", None)
        self.url_format = data.pop("url_format", None)

        if self.url_format and self.url_format.startswith('/'):
            raise ConfigError(self.yaml_path, 'Collection url formats are '
                    'relative to the collection root, they cannot start with '
                    'a "/".')

        # Error on unexpected data
        if data:
            raise ConfigError(self.yaml_path, 'Unexpected collection fields: '
                    '{}'.format(list(data.keys())))

    def register_page(self, page):
        if not isinstance(page, dict):
            raise ConfigError(self.yaml_path, 'Expected dict describing '
                'page, got "{}"'.format(type(page)))
        title = page.pop("title", None)
        template = page.pop("template", None)
        context = page.pop("context", {})

        if title is None:
            raise ConfigError(self.yaml_path, 'Collection pages must have a '
                    'title')
        if not isinstance(title, str):
            raise ConfigError(self.yaml_path, 'Page title must be '
                    'a non-zero length string (not {})'.format(title))

        # Unrecognized field error
        if page:
            raise ConfigError(self.yaml_path, 'Unexpected fields in '
                    'collection page: {}'.format(list(page.keys())))

        if title[0] == '/':
            raise ConfigError(self.yaml_path, 'Collection page names cannot '
                    'start with a "/" (unlike "{}")'.format(title))

        #TODO: Slugify
        url = normalize_url(self.url + title)

        #TODO: Use `MARKDOWN_EXTENSIONS` to consider both .md and .markdown
        md_path = os.path.join(
            os.path.abspath(self.app.content_dir),
            self.url[1:] + title + ".md"
        )
        if os.path.exists(md_path):
            view = views.MarkdownView(md_path, self.app, url, template, self, context=context)
            self.app.consume(md_path)
        else:
            context.setdefault("content", "")
            view = views.TemplateView(self.app, url, template, self, context=context)

        try:
            self.app.add_url_rule(url, url, view)
        except AssertionError as e:
            if str(e).startswith("View function mapping is overwriting an "
                                 "existing endpoint function:"):
                raise ConfigError(self.yaml_path, 'Page title "{}" with url '
                        '"{}" conflicts with an existing url.'.format(
                        title, url))
            else:
                raise  # pragma: no cover
