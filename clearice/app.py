import os

from markdown import Markdown
import jinja2

from .helpers import walk_dir, normalize_url, remove_suffix
from .exceptions import ConfigError, UrlConflictError
from . import generators

class App():

    def __init__(self, root_dir=None, print_progress=False, skip_default_generators=False):
        self.root_dir = os.path.abspath(root_dir) if root_dir else os.getcwd()
        self.print_progress = print_progress

        self.content_dir = os.path.join(self.root_dir, "content")
        self.build_dir = os.path.join(self.root_dir, "build")
        self.template_dir = os.path.join(self.root_dir, "templates")

        self.jinja_env = self.make_jinja_environment()
        self.consumed_files = set()
        self._generators = []
        self.collections = _Collections(self)
        self.url_map = {}  # Maps URLs to Views

        # Markdown Template Filter
        md_parser = Markdown()
        md_convert = lambda text: jinja2.Markup(md_parser.reset().convert(text))
        self.add_template_filter(md_convert, "markdown")

        if not skip_default_generators:
            self.add_default_generators()

    def add_default_generators(self):
        COLLECTION_CONF = "_collection.yaml"
        # Collection generator for each _collection.yaml file
        for abspath, relpath in self.walk_content(patterns=COLLECTION_CONF):
            url = normalize_url(remove_suffix(relpath, COLLECTION_CONF))
            generator = generators.Collection(url, abspath)
            self.add_generator(generator)

        # Markdown page generator
        self.add_generator(generators.MarkdownGenerator())

    def make_jinja_environment(self):
        return jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.template_dir),
            autoescape=True,
        )

    def render_template(self, template_name_or_list, context):
        t = self.jinja_env.get_or_select_template(template_name_or_list)
        return t.render(context)

    def render_template_string(self, source, context):
        t = self.jinja_env.from_string(source)
        return t.render(context)

    def walk_content(self, include_consumed=False, **kwargs):
        files = walk_dir(
            root=self.content_dir,
            **kwargs,
        )
        for abspath, relpath in files:
            if include_consumed or not self.is_consumed(abspath):
                yield abspath, relpath

    @property
    def n_urls(self):
        return len(self.url_map)

    def add_template_filter(self, func, name):
        #TODO: Enable use as decorator, like flask
        self.jinja_env.filters[name] = func

    def add_url(self, url, view):
        #TODO: Add name for reverse lookup
        #TODO: Option to not care about overwriting url
        if url in self.url_map:
            raise UrlConflictError
        self.url_map[url] = view

    def consume(self, abspath):
        assert os.path.isabs(abspath)
        self.consumed_files.add(abspath)

        if self.print_progress:
            print("\rProcessed {} files".format(len(self.consumed_files)), end="")  # pragma: nocover

    def is_consumed(self, abspath):
        assert os.path.isabs(abspath)
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
            print()  # Newline after printing in consume()

    def build_content(self):
        """Yield pages as they are rendered into the build directory."""

        # Create build dir
        if not os.path.isdir(self.build_dir):
            os.makedirs(self.build_dir)

        # Record existing files in build dir
        existing_files = set()
        for abspath, relpath in walk_dir(self.build_dir):
            existing_files.add(abspath)

        # Render all urls
        written_files = set()
        for url, view_func in self.url_map.items():
            filename = self._build_url(url, view_func)
            written_files.add(filename)
            yield url

        # Remove files that existed before
        for filename in existing_files - written_files:
            os.remove(filename)
            parent = os.path.dirname(filename)
            if not os.listdir(parent):
                os.removedirs(parent)

    def _build_url(self, url, view_func):

        assert url[0] == '/'
        url = url[1:]  # Remove leading '/'
        if len(url) == 0 or url[-1] == '/':  # Add index.html filename if needed
            url = url+'index.html'
        filename = os.path.join(self.build_dir, url)

        # Make directories
        dirname = os.path.dirname(filename)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)

        # Write File
        content = view_func()
        with open(filename, 'w') as f:
            f.write(content)

        return filename

    def generate(self):
        """The main no-frills entry point to generate content."""
        self.generate_urls()
        for url in self.build_content():
            pass

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
