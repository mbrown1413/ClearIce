
import os
import sys
from fnmatch import fnmatch
from datetime import datetime

from flask import Flask, render_template, Markup
from flask_frozen import Freezer

from jinja2 import Template
import jinja2.exceptions

import yaml
from markdown import Markdown

CONTENT_DIR = "content/"
DEFAULT_TEMPLATE = "default.html"

IGNORED_FILES = [".*", "*~"]
MARKDOWN_EXTENSIONS = [".md", ".markdown"]
MARKDOWN_FILES = list("*"+ext for ext in MARKDOWN_EXTENSIONS)


########## Exceptions ##########
# Some of these are basically duplicate exceptions of the libraries we use,
# providing more detail of the context which the error ocurred.

class ClearIceException(Exception): pass

class FrontmatterError(ClearIceException):
    def __init__(self, filename, msg):
        self.filename = filename
        self.msg = msg
    def __str__(self):
        return 'Error processing frontmatter ' \
                'in {}:\n{}\n'.format(self.filename, self.msg)

class ConfigError(ClearIceException):
    def __init__(self, filename, msg):
        self.filename = filename
        self.msg = msg
    def __str__(self):
        return 'Configuration error in "{}"\n' \
                '{}'.format(self.filename, self.msg)

class TemplateError(ClearIceException): pass

class TemplateNotFound(TemplateError):
    def __init__(self, template_name):
        self.template_name = template_name
    def __str__(self):
        return 'Template not found: "{}"\n'.format(self.template_name)

class YamlError(ClearIceException):
    def __init__(self, filename, underlying_exception=None):
        self.filename = filename
        self.e = underlying_exception
    def __str__(self):
        long_desc = ":\n{}".format(self.e) if self.e else ""
        return 'Error reading yaml file "{}"{}'.format(self.filename, long_desc)


########## Filename and URL Helpers ##########

def remove_extension(filename, divider='.'):
    return filename[:filename.rfind(divider)]

def remove_suffix(s, suffix):
    assert s.endswith(suffix)
    return s[:-len(suffix)]

def remove_prefix(s, prefix):
    assert s.startswith(prefix)
    return s[len(prefix):]

def normalize_url(path):
    url = path

    # Does not remove filename extensions
    #   /blah/this.md -> /blah/this.md/

    # Removes leading .
    #   ./blah/this/ -> /blah/this/
    if url.startswith("./"):
        url = url[1:]

    # If index file, remove filename
    #  /blah/index -> /blah/
    #  /blah/index/ -> /blah/index/
    if url.endswith("/index"):
        url = url[:-5]

    # Ensures starts/ends with /
    #   blah/this -> /blah/this/
    if not url.startswith("/"):
        url = '/' + url
    if not url.endswith("/"):
        url = url + '/'

    # Exactly one '/' between each part
    while '//' in url:
        url = url.replace('//', '/')

    assert url.startswith('/') and url.endswith('/')
    return url

def fnmatch_one_of(filename, patterns):
    for pattern in patterns:
        if fnmatch(filename, pattern):
            return True
    return False

def walk_dir(root, exclude=(), subdir="", fname_patterns=None):
    """Recursively lists all files the root directory.

    Args:
        root: The directory to walk.
        exclude: Ignore files with an absolute path in this collection.
        subdir: If not `None`, only return files the directory "root/subdir/".
        fname_patterns: A list of glob-style filename strings. If given, only
            filenames that match one of these patterns will be returned.

    Returns: [(abspath, relpath, filename), ...]
        abspath: Absolute path of file, via `os.path.abspath()`.
        relpath: Relative path of file from the root.
        filename: Name of the file.
    """
    root = os.path.abspath(root)
    assert subdir is None or not subdir.startswith('/')
    for dirpath, dirnames, filenames in os.walk(os.path.join(root, subdir)):
        for filename in filenames:

            if fnmatch_one_of(filename, IGNORED_FILES):
                continue
            if fname_patterns and not fnmatch_one_of(filename, fname_patterns):
                continue

            abspath = os.path.join(dirpath, filename)
            relpath = remove_prefix(abspath, root)
            if abspath in exclude:
                continue
            yield abspath, relpath, filename

def str_to_date(s):
    date = None
    leftover = s
    try:
        date = datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError as e:
        pass
    if date:
        leftover = s[10:]

    return date, leftover

def extract_info_from_filename(fname):
    fname = remove_extension(fname)
    info = {}

    # Extract date
    date, fname = str_to_date(fname)
    if date:
        info['date'] = date
        if fname[0] == '_':  # Common to have "date_slug.md". Remove the '_'
            fname = fname[1:]

    #TODO: Slugify
    info['slug'] = fname

    return info


########## Views ##########

def read_frontmatter_file(filename):
    """Returns (frontmatter dict, contents string)."""
    with open(filename) as f:
        lines = list(f)

    # Find frontmatter markers
    marker = "---\n"
    fm_start = None
    try:
        fm_start = lines.index(marker)
        fm_end = lines.index(marker, fm_start+1)
    except ValueError:
        # Allow last line to contain marker but no newline
        if fm_start is not None and lines[-1] == marker[:-1]:
            fm_end = len(lines)-1
        else:
            raise FrontmatterError(filename, 'Missing opening and closing '
                    '"---" frontmatter delimiter lines.') from None

    # Ensure that all preceeding lines are blank
    #TODO: Should we consider this to be no frontmatter instead of erroring?
    if ''.join(lines[:fm_start]).strip():
        raise FrontmatterError(filename, 'Frontmatter marker "---" may only '
                'be preceeded by blank lines.') from None

    yaml_lines = lines[fm_start+1:fm_end]

    try:
        fm = yaml.load(''.join(yaml_lines))
    except ValueError as e:
        raise FrontmatterError(filename, e)
    if fm is None:
        fm = {}

    if type(fm) != dict:
        raise FrontmatterError(filename, 'Frontmatter must be a YAML mapping') \
                from None

    content = ''.join(lines[fm_end+1:])
    return fm, content

class View():

    def __call__(self):
        raise NotImplementedError()  # pragma: no cover

class TemplateView(View):

    def __init__(self, app, url=None, template=None, collection=None, context=None):
        self.app = app
        self.url = url
        self.template = template
        self.collection = collection
        self.default_context = context

        self.context = self.get_context()

    def __getitem__(self, key):
        return self.context[key]

    def set_url(self, url):
        self.url = url
        self.context["url"] = url

    def get_context(self):
        # Order is important here: some sources will overwrite others.

        context = {
            "self": self,
            "url": self.url,
            "app": self.app,
            "collections": self.app.collections,
            "collection": self.collection,
            "template": DEFAULT_TEMPLATE,
        }
        context["context"] = context  # Context metavariable

        # Context from collection
        if self.collection:
            context.update(self.collection.context)

        # Context passed into view
        if self.default_context:
            context.update(self.default_context)

        # Template explicitly passed in
        if self.template:
            context["template"] = self.template

        return context

    def __call__(self):
        if not self.url:
            raise RuntimeError("Programmer error: url should have been set")
        template = self.context["template"]
        try:
            return render_template(template, **self.context)
        except jinja2.exceptions.TemplateNotFound as e:
            #TODO: Clarify where the user provided this template, so they can
            #      go fix the problem! Maybe a more detailed description if
            #      it's "default.html" that's missing.
            raise TemplateNotFound(template) from None
        except jinja2.exceptions.TemplateError as e:
            #TODO: Include context? It's helpful on variable undefined error.
            #TODO: Move some of this printing logic into exception class.
            file_msg = "in "+e.filename if hasattr(e, "filename") else ""
            line_msg = " on line "+str(e.lineno) if hasattr(e, "lineno") else ""
            raise TemplateError('Error while processing template "{}" for url '
                '"{}":\n  {}\n{}{}'.format(template, self.url,
                e.message, file_msg, line_msg)) from None

class MarkdownView(TemplateView):

    def __init__(self, md_file, *args, **kwargs):
        self.md_file = md_file
        self.frontmatter, self.content = read_frontmatter_file(self.md_file)
        super().__init__(*args, **kwargs)

    def get_context(self):
        context = super().get_context()
        context["content"] = self.content
        context["frontmatter"] = self.frontmatter

        # Extract info (like date and slug) from filename
        filename = os.path.basename(self.md_file)
        context.update(extract_info_from_filename(filename))

        # Explicitly provided frontmatter overwrides all
        context.update(self.frontmatter)

        return context


########## Generators ##########

class GeneratorBase():
    """Base class for content generators.

    Generators can be any callable that receives the app and modifies it. The
    main things that generators do are:

      - Add urls using `app.add_url_rule()`.
      - Consume files by calling `app.consume()`.

    A simple generator might walk the contents directory, `app.contents_dir`,
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
        files = walk_dir(app.contents_dir,
                         exclude=app.consumed_files,
                         fname_patterns=MARKDOWN_FILES)
        for abspath, relpath, filename in files:
            url = normalize_url(remove_extension(relpath))
            view = MarkdownView(abspath, app, url)
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
                view = MarkdownView(abspath, app, collection=self)
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
        return walk_dir(app.contents_dir,
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
            os.path.abspath(CONTENT_DIR),
            self.url[1:] + title + ".md"
        )
        if os.path.exists(md_path):
            view = MarkdownView(md_path, self.app, url, template, self, context=context)
            self.app.consume(md_path)
        else:
            context.setdefault("content", "")
            view = TemplateView(self.app, url, template, self, context=context)

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


########## Flask App ##########

class StaticGenApp(Flask):

    def __init__(self, contents_dir, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.contents_dir = contents_dir

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
    app = StaticGenApp(CONTENT_DIR, __name__, root_path=os.getcwd())

    # Markdown Template Filter
    md_parser = Markdown()
    md_convert = lambda text: Markup(md_parser.reset().convert(text))
    app.add_template_filter(md_convert, "markdown")

    # Adding `Collection` generator for each _collection.yaml file
    for abspath, relpath, filename in walk_dir(CONTENT_DIR):
        if filename == "_collection.yaml":
            url = normalize_url(remove_suffix(relpath, "_collection.yaml"))
            generator = Collection(url, abspath)
            app.add_generator(generator)

    # Add template markdown generator
    app.add_generator(MarkdownGenerator())

    app.generate()
    return app

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

if __name__ == "__main__":
    main()  # pragma: no cover
