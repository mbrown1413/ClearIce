
import os
import sys
from pprint import pprint
from fnmatch import fnmatch
from datetime import datetime

from flask import Flask, render_template, Markup
from flask_frozen import Freezer

import jinja2.exceptions

import yaml
from markdown import Markdown

CONTENTS_DIR = "contents/"
DEFAULT_TEMPLATE = "default.html"

IGNORED_FILES = [".*", "*~"]
MARKDOWN_EXTENSIONS = [".md", ".markdown"]
MARKDOWN_FILES = list("*"+ext for ext in MARKDOWN_EXTENSIONS)


########## Exceptions ##########

class ClearIceException(Exception): pass

class FrontmatterError(ClearIceException):
    def __init__(self, filename, msg):
        self.filename = filename
        self.msg = msg
    def __str__(self):
        return 'Error processing frontmatter ' \
                'in {}:\n{}\n'.format(self.filename, self.msg)

class TemplateError(ClearIceException): pass

class TemplateNotFound(TemplateError):
    def __init__(self, template_name):
        self.template_name = template_name
    def __str__(self):
        return 'Template not found: "{}"\n'.format(self.template_name)

class YamlDataError(ClearIceException):
    def __init__(self, filename, underlying_exception=None):
        self.filename = filename
        self.e = underlying_exception
    def __str__(self):
        long_desc = ":\n{}".format(self.e) if self.e else ""
        return 'Error reading data file "{}"{}'.format(self.filename, long_desc)


########## Filename and URL Helpers ##########

def remove_extension(filename, divider='.'):
    return filename[:filename.rfind(divider)]

def remove_suffix(s, suffix):
    assert s.endswith(suffix)
    return s[:-len(suffix)]

def remove_prefix(s, prefix):
    assert s.startswith(prefix)
    return s[len(prefix):]

def contents_path_to_url(path):
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

    fm = yaml.load(''.join(lines[fm_start+1:fm_end]))
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

    def __init__(self, app, url, template=None, collection=None, context=None):
        self.app = app
        self.url = url
        self.template = template
        self.collection = collection
        self.default_context = context

        self.context = self.get_context()

    def __getitem__(self, key):
        return self.context[key]

    def get_context(self):
        # Order is important here: some sources will overwrite others.

        context = {
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
        #TODO: Error if template not specified
        template = self.context["template"]
        try:
            return render_template(template, **self.context)
        except jinja2.exceptions.TemplateNotFound as e:
            #TODO: Clarify where the user provided this template, so they can
            #      go fix the problem! Maybe a more detailed description if
            #      it's "default.html" that's missing.
            raise TemplateNotFound(template) from None
        except jinja2.exceptions.TemplateError as e:
            #TODO: Prettier error
            sys.stderr.write('Error while processing template "{}" for url'
                    '"{}"\n'.format(template, self.url))
            sys.stderr.write(e.message+'\n')
            if hasattr(e, "filename"):
                sys.stderr.write("File: {}\n".format(e.filename))
            if hasattr(e, "lineno"):
                sys.stderr.write("Line: {}\n".format(e.lineno))
            sys.stderr.write("\nTemplate Context: ")
            pprint(self.context, stream=sys.stderr)
            sys.exit(-1)

class MarkdownView(TemplateView):

    def __init__(self, md_file, *args, date_from_filename=True, **kwargs):
        self.md_file = md_file
        self.date_from_filename = date_from_filename
        self.frontmatter, self.content = read_frontmatter_file(self.md_file)
        super().__init__(*args, **kwargs)

    def get_context(self):
        context = super().get_context()
        context["content"] = self.content
        context["frontmatter"] = self.frontmatter

        if self.date_from_filename:
            filename = os.path.basename(self.md_file)
            if len(filename) >= 10:
                date = None
                try:
                    date = datetime.strptime(filename[:10], "%Y-%m-%d").date()
                except ValueError as e:
                    pass
                if date:
                    context["date"] = date

        # Explicitly provided frontmatter overwrides all
        context.update(self.frontmatter)

        # Default title to last part of url
        if "title" not in context:
            context["title"] = self.url.strip("/").split("/")[-1] or "home"

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
            url = contents_path_to_url(remove_extension(relpath))
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

    def __iter__(self):
        return self.items.__iter__()

    def __len__(self):
        return len(self.items)

    def __call__(self, app):
        self.app = app
        self.data = self.read_yaml_data()
        self.app.consume(self.yaml_path)

        # Register static pages
        for page in self.pages:
            self.register_page(page)

        # Find and collect items
        files = walk_dir(app.contents_dir,
                         exclude=app.consumed_files,
                         subdir=remove_prefix(self.url, '/'),
                         fname_patterns=MARKDOWN_FILES)
        for abspath, relpath, filename in files:
            url = contents_path_to_url(remove_extension(relpath))
            if self.url_is_item(url):
                view = MarkdownView(abspath, app, url, collection=self)
                self.items.append(view)
                app.consume(abspath)
                app.add_url_rule(url, url, view)

                if self.require_date and "date" not in view.context:
                    #TODO: Better Error
                    raise ValueError('Date required in collection items but none found in frontmatter or filename of "{}"'.format(abspath))

        # Sort items
        if self.item_order:
            def sortfunc(item):
                value = item.context.get(self.item_order, "")
                return str(value).lower()
            lambda item: str(item.context.get(self.item_order, "")).lower()
            self.items = list(sorted(self.items, key=sortfunc))

    def url_is_item(self, url):
        # If `self.url` is in "/blog/", then "/blog/foo.md" and
        # "/blog/bar/index.md" will be considered items.

        # Remove last part of the given url separated by slashes. If it
        # matches the collection's url, it's an item.
        if url.endswith('/'):
            url = url[:-1]
        try:
            last_slash = url.rindex('/')
        except ValueError:
            return False
        return self.url == url[:last_slash+1]

    def read_yaml_data(self):
        with open(self.yaml_path) as f:
            try:
                data = yaml.load(f)
            except yaml.error.YAMLError as e:
                raise YamlDataError(self.yaml_path, e) from None
        if not isinstance(data, dict):
            raise ValueError('Expected dict describing collection, got "{}"'
                    '(in file "{}")'.format(type(data), self.yaml_path))

        self.name = data.pop("name", "") or ""
        self.pages = data.pop("pages", []) or []
        self.context = data.pop("context", {}) or {}
        self.item_order = data.pop("order", None)
        self.require_date = data.pop("require_date", False)

        # Error on unexpected data
        if data:
            #TODO: Better error message
            raise ValueError('Unexpected fields {} in collection'
                    '(in file "{}")'.format(list(data.keys()), self.yaml_path))

    def register_page(self, page):
        name = page.pop("name")  #TODO: Graceful error when field not found.
        template = page.pop("template", None)
        context = page.pop("context", {})
        #TODO: Context attribute in yaml

        # Unrecognized field error
        if page:
            #TODO: Better error message
            raise ValueError('Unexpected fields {} in page of collection'
                    '(in file "{}")'.format(list(page.keys()), self.yaml_path))

        url = self.url + name
        if name.endswith("index"):
            url = remove_suffix(url, "index")
        else:
            url += "/"

        #TODO: Use `MARKDOWN_EXTENSIONS` to consider both .md and .markdown
        md_path = os.path.join(
            os.path.abspath(CONTENTS_DIR),
            self.url[1:] + name + ".md"
        )
        #TODO: Error if "template" not provided
        if os.path.exists(md_path):
            view = MarkdownView(md_path, self.app, url, template, self, context=context)
            self.app.consume(md_path)
        else:
            view = TemplateView(self.app, url, template, self, context=context)
        self.app.add_url_rule(url, url, view)


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
        self.generators = []

    def consume(self, abspath):
        self.consumed_files.add(abspath)

    def is_consumed(self, abspath):
        return abspath in self.consumed_files

    def generate(self):
        for generator in self.generators:
            generator(self)

    @property
    def collections(self):
        for generator in self.generators:
            if generator.is_collection:
                yield generator

    def get_collection_by_name(self, name):
        generator = self.get_generator_by_name(name)
        if generator.is_collection:
            return generator

    def get_generator_by_name(self, name):
        for generator in self.generators:
            if hasattr(generator, "name") and generator.name == name:
                return generator

def build_app():
    app = StaticGenApp(CONTENTS_DIR, __name__, root_path=os.getcwd())

    # Markdown Template Filter
    md_parser = Markdown()
    md_convert = lambda text: Markup(md_parser.reset().convert(text))
    app.add_template_filter(md_convert, "markdown")

    # Adding `Collection` generator for each _collection.yaml file
    for abspath, relpath, filename in walk_dir(CONTENTS_DIR):
        if filename == "_collection.yaml":
            url = contents_path_to_url(remove_suffix(relpath, "_collection.yaml"))
            generator = Collection(url, abspath)
            app.generators.append(generator)

    # Add template markdown generator
    app.generators.append(MarkdownGenerator())

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

if __name__ == "__main__":
    main()  # pragma: no cover
