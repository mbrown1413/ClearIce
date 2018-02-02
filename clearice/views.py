import os

from datetime import datetime

from flask import render_template
import yaml
import jinja2.exceptions

from .helpers import remove_extension
from .exceptions import TemplateError, FrontmatterError, TemplateNotFound

DEFAULT_TEMPLATE = "default.html"

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
