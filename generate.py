
import os
import sys
from pprint import pprint
from fnmatch import fnmatch

from flask import Flask, render_template, Markup
from flask_frozen import Freezer

from jinja2.exceptions import TemplateError, TemplateNotFound

import yaml
from markdown import Markdown

CONTENTS_DIR = "contents/"
IGNORED_FILES = [".*", "*~"]
MARKDOWN_FILES = ["*.md"]
STATIC_FILES = ["*.jpg", "*.png"]

DEFAULT_TEMPLATE = "default.html"


########## Filename and URL Helpers ##########

def matches_ignored(filename):
    for ignored_pattern in IGNORED_FILES:
        if fnmatch(filename, ignored_pattern):
            return True
    return False

def matches(filename, ignored_patterns, matched_patterns):
    if matches_ignored(filename):
        return False
    for pattern in MARKDOWN_FILES:
        if fnmatch(filename, pattern):
            return True
    return False

def matches_markdown(filename):
    return matches(filename, IGNORED_FILES, MARKDOWN_FILES)

def matches_static(filename):
    return matches(filename, IGNORED_FILES, STATIC_FILES)

def remove_extenison(filename, divider='.'):
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

    assert url.startswith('/')
    assert url.endswith('/')
    return url

def walk_dir(dirname, to_exclude=()):
    dirname = os.path.abspath(dirname)
    for dirpath, dirnames, filenames in os.walk(dirname):
        for filename in filenames:
            abspath = os.path.join(dirpath, filename)
            relpath = remove_prefix(abspath, dirname)
            if abspath in to_exclude:
                continue
            yield abspath, relpath, filename


########## Views ##########

def read_frontmatter_file(filename):
    """Returns (frontmatter dict, contents string)."""
    lines = list(open(filename))

    # Find frontmatter markers
    MARKER = "---\n"
    fm_start = lines.index(MARKER)
    fm_end = lines.index(MARKER, fm_start+1)

    if fm_start != 0:
        raise ValueError()  #TODO

    fm = yaml.load(''.join(lines[fm_start+1:fm_end]))
    if fm is None:
        fm = {}

    #TODO:
    #  - Ignore blank lines, only recognize first marker as first non-blank line.
    #  - No markers present, assumed to be empty frontmatter.

    if type(fm) != dict:
        raise ValueError()  #TODO

    content = ''.join(lines[fm_end+1:])
    return fm, content

class TemplateView():

    def __init__(self, url, collections, template=None, collection=None):
        self.url = url
        self.collections = collections
        self.template = template

        if collection:
            self.collection = collection
        else:
            self.collection = collections.get_collection_by_url(self.url)
            if self.collection:
                self.collection.add(self)

        self.context = self.get_context()

    def __getitem__(self, key):
        return self.context[key]

    def get_context(self):
        # Order is important here: some sources will overwrite others.

        context = {
            "url": self.url,
            "collections": self.collections,
            "collection": self.collection,
            "template": DEFAULT_TEMPLATE,
        }
        context["context"] = context  # Context metavariable

        # Context from collection
        if self.collection:
            context.update(self.collection.context)

        # Template explicitly passed in
        if self.template:
            context["template"] = self.template

        return context

    def get_template(self):
        #TODO: Error if template not specified
        return self.context["template"]

    def __call__(self):
        template = self.get_template()
        try:
            return render_template(template, **self.context)
        except TemplateNotFound as e:
            #TODO: Clarify where the user provided this template, so they can
            #      go fix th eproblem!
            sys.stderr.write('Template not found: "{}"\n'.format(template))
            sys.exit(-1)
        except TemplateError as e:
            #TODO: Prettier error
            sys.stderr.write('Error while processing template "{}" for url "{}"\n'.format(template, self.url))
            sys.stderr.write(e.message+'\n')
            if hasattr(e, "filename"):
                sys.stderr.write("File: {}\n".format(e.filename))
            if hasattr(e, "lineno"):
                sys.stderr.write("Line: {}\n".format(e.lineno))
            sys.stderr.write("\nTemplate Context: ")
            pprint(self.context, stream=sys.stderr)
            sys.exit(-1)

class MarkdownView(TemplateView):

    def __init__(self, url, collections, md_file, **kwargs):
        self.md_file = md_file
        self.frontmatter, self.content = read_frontmatter_file(self.md_file)
        super().__init__(url, collections, **kwargs)

    def get_context(self):
        context = super().get_context()
        context["content"] = self.content

        # Explicitly provided frontmatter overwrides all
        context.update(self.frontmatter)

        # Default title to last part of url
        if "title" not in context:
            context["title"] = self.url.strip("/").split("/")[-1] or "home"

        return context


########## Collections ##########

class Collection():

    def __init__(self, yaml_filename, url=None):

        # Read yaml data
        data = yaml.load(open(yaml_filename))
        if not isinstance(data, dict):
            raise ValueError('Expected dict describing collection, got "{}"'
                    '(in file "{}")'.format(type(data), yaml_filename))
        self.name = data.pop("name", None)
        self.title = data.pop("title", None)
        self.pages = data.pop("pages", [])
        self.context = data.pop("context", {})

        assert url and url.endswith('/') and url.startswith('/')
        self.url = url

        self.items = []

        # Error on unexpected data
        if data:
            #TODO: Better error message
            raise ValueError('Unexpected fields {} in collection'
                    '(in file "{}")'.format(list(data.keys()), yaml_filename))

    def __repr__(self):
        return '<Collection url="{}">'.format(self.url)

    def __iter__(self):
        return self.items.__iter__()

    def add(self, item):
        self.items.append(item)

    def url_matches(self, url):
        if url.endswith('/'):
            url = url[:-1]
        try:
            last_slash = url.rindex('/')
        except ValueError:
            return False
        return self.url == url[:last_slash+1]

    def register_pages(self, app):
        files_used = []
        for page in self.pages:
            page_files_used = self.register_page(page, app)
            if page_files_used:
                files_used.extend(page_files_used)
        return files_used

    def register_page(self, page_dict, app):
        #TODO: Error if "name" not provided
        url = self.url + page_dict["name"]
        if page_dict["name"].endswith("index"):
            url = remove_suffix(url, "index")
        else:
            url += "/"

        #TODO: Unrecognized fields in yaml file should cause error.
        #TODO: Context attribute in yaml

        #TODO: Error if "template" not provided
        md_path = os.path.join(
            os.path.abspath(CONTENTS_DIR),
            self.url[1:] + page_dict["name"] + ".md"
        )
        file_used = None
        if os.path.exists(md_path):
            file_used = md_path
            view = MarkdownView(url, md_file=md_path,
                                        collections=app.collections,
                                        collection=self,
                                        template=page_dict["template"])
        else:
            view = TemplateView(url, collections=app.collections,
                                        collection=self,
                                        template=page_dict["template"])
        app.add_url_rule(url, url, view)
        return [file_used]

class ColllectionSet():
    #TODO: Enforce unique collection names

    def __init__(self, collections=()):
        self.collections = list(collections)

    def __iter__(self):
        return self.collections.__iter__()

    def __getitem__(self, collection_name):
        for collection in self:
            if collection.name == collection_name:
                return collection
        return None

    def __repr__(self):
        return list(self).__repr__()

    def add(self, collection):
        self.collections.append(collection)

    def get_collection_by_url(self, url):
        for collection in self:
            if collection.url_matches(url):
                return collection
        return None


########## Flask App ##########

def build_app():
    app = Flask(__name__)
    collections = ColllectionSet()
    app.collections = collections

    # Setup Markdown Template Filter
    md_parser = Markdown()
    md_convert = lambda text: Markup(md_parser.reset().convert(text))
    app.add_template_filter(md_convert, "markdown")

    # Read all _collection.yaml files
    for abspath, relpath, filename in walk_dir(CONTENTS_DIR):
        if filename == "_collection.yaml":
            url = contents_path_to_url(remove_suffix(relpath, "_collection.yaml"))
            collection = Collection(abspath, url)
            collections.add(collection)

    # Add special collection pages (indexes, tag pages, etc.)
    to_exclude = set()
    for collection in collections:
        files_used = collection.register_pages(app)
        if files_used:
            to_exclude.update(files_used)

    # Walk contents dir
    for abspath, relpath, filename in walk_dir(CONTENTS_DIR, to_exclude):

        # Serve markdown files
        if matches_markdown(filename):
            url = contents_path_to_url(remove_extenison(relpath))

            # Add View
            view = MarkdownView(url, md_file=abspath,
                                collections=collections)
            app.add_url_rule(url, url, view)

        # Serve static files
        elif matches_static(filename):
            pass  #TODO

    return app

def main(app):
    freezer = Freezer(app)
    freezer.freeze()

app = build_app()

if __name__ == "__main__":
    main(app)
