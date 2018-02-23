import os

import yaml
from jinja2 import Template
import jinja2.exceptions
from hfilesize import FileSize

from .helpers import normalize_url, remove_prefix, remove_extension
from .exceptions import ConfigError, YamlError, UrlConflictError
from . import views, buildactions

MARKDOWN_EXTENSIONS = [".md", ".markdown"]
MARKDOWN_FILES = list("*"+ext for ext in MARKDOWN_EXTENSIONS)


class GeneratorBase():
    """Base class for content generators.

    Generators can be any callable that receives the app and modifies it. The
    main things that generators do are:

      - Add urls using `app.add_url()`.
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
        Produces content using `app.add_url()` and consumes files in the
        contents directory using `app.consume()`.
        """
        raise NotImplementedError()  # pragma: no cover

class MarkdownGenerator(GeneratorBase):
    """Adds a `MarkdownView` url for every markdown file."""

    def __call__(self, app):
        files = app.walk_content(patterns=MARKDOWN_FILES)
        for abspath, relpath in files:
            url = normalize_url(remove_extension(relpath))
            view = views.MarkdownView(abspath, app, url)
            app.add_url(url, view)
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
        if not isinstance(self.pages, list):
            raise ConfigError(self.yaml_path, '"pages" field must be a list')
        for page in self.pages:
            self.register_page(page)

        # Find and collect items
        files = app.walk_content(
            subdir=remove_prefix(self.url, '/'),
            patterns=MARKDOWN_FILES
        )
        for abspath, relpath in files:
            if self.file_is_item(app, abspath, relpath):
                view = views.MarkdownView(abspath, app, collection=self)
                url = self.file_to_url(app, view, abspath, relpath)
                view.set_url(url)

                self.items.append(view)
                app.consume(abspath)
                app.add_url(url, view)

        # Sort items
        if self.item_order:
            def sortfunc(item):
                value = item.context.get(self.item_order, "")
                return str(value).lower()
            self.items = list(sorted(self.items, key=sortfunc))

    def file_is_item(self, app, abspath, relpath):
        # If `self.url` is in "/blog/", then "/blog/foo.md" and
        # "/blog/bar/index.md" will be considered items.

        # Remove last part of url separated by slashes. If it matches the
        # collection's url, it's an item.
        url = normalize_url(remove_extension(relpath))
        url = url[:-1]  # Remove last '/'
        last_slash = url.rindex('/')
        return url[:last_slash+1] == self.url

    def file_to_url(self, app, view, abspath, relpath):
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
            raise ConfigError(self.yaml_path, 'Unexpected fields: '
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
            self.app.add_url(url, view)
        except UrlConflictError:
            raise ConfigError(self.yaml_path, 'Page title "{}" with url '
                    '"{}" conflicts with an existing url.'.format(
                    title, url))


class StaticFileGeneraor(GeneratorBase):

    def __init__(self, patterns=None, link=None, link_above=None, link_type="soft", **kwargs):
        self.patterns = patterns or []
        self.link = link_above is not None if link is None else link
        try:
            self.link_above = FileSize(link_above or 0, case_sensitive=False)
        except ValueError:
            raise ConfigError(None, "Unrecognized file size: {}".format(link_above))
        self.link_type = link_type

        if not isinstance(self.link, bool):
            raise ConfigError(None, "static link option must be true or false")
        if self.link_type not in ("hard", "soft"):
            raise ConfigError(None, 'Unrecognized link_type "geort", must be "soft" or "hard"')
        if not isinstance(self.patterns, list) or False in [isinstance(p, str) for p in self.patterns]:
            raise ConfigError(None, "static patterns must be a list of strings")

        if kwargs:
            key = list(kwargs.keys())[0]
            raise ConfigError(None, 'Unexpected field "{}" in static config'.format(key))

    @classmethod
    def from_conf(cls, yaml_file, data):
        if not isinstance(data, dict):
            raise ConfigError(yaml_file, 'Expected static option to be a dict, got "{}"'.format(type(data)))
        try:
            return cls(**data)
        except ConfigError as e:
            # Re-raise after adding yaml_file info
            e.filename = yaml_file
            raise e

    def __call__(self, app):
        for abspath, relpath in app.walk_content(patterns=self.patterns):
            app.consume(abspath)
            url = normalize_url(relpath)
            action = self.get_action(abspath)
            app.add_url(url, action)

    def get_action(self, abspath):
        if self.link:
            if self.link_above > 0:
                size = os.path.getsize(abspath)
            else:
                size = float('inf')
            if size > self.link_above:
                is_hard = self.link_type=='hard'
                return buildactions.Link(abspath, hard=is_hard)

        # Default to copy
        return buildactions.Copy(abspath)
