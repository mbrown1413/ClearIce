import os

from markdown import Markdown
import jinja2
import yaml

from .helpers import walk_dir, normalize_url, remove_suffix
from .exceptions import ConfigError, UrlConflictError, YamlError, TemplateVarUndefined, TemplateError
from . import generators, buildactions

class App():

    def __init__(self, root_dir=None, print_progress=False, **conf_overwrite):
        self.root_dir = os.path.abspath(root_dir) if root_dir else os.getcwd()
        self.print_progress = print_progress
        self.conf_overwrite = conf_overwrite

        self.reset()

    def reset(self):
        self.conf_path = os.path.join(self.root_dir, 'conf.yaml')
        self.conf = self.read_conf()

        self.content_dir = os.path.join(self.root_dir, self.conf['content_dir'])
        self.build_dir = os.path.join(self.root_dir, self.conf['build_dir'])
        self.template_dir = os.path.join(self.root_dir, self.conf['template_dir'])

        self.jinja_env = self.make_jinja_environment()
        self.consumed_files = set()
        self._generators = []
        self.collections = _Collections(self)
        self.url_map = {}  # Maps URLs to Views
        self.has_generated_urls = False
        self.has_built = False

        # Markdown Template Filter
        self.add_template_filter(self.markdown_filter, "markdown")

        if not self.conf['skip_default_generators']:
            self.add_default_generators()

    def read_conf(self):
        conf = {
            'content_dir': 'content',
            'build_dir': 'build',
            'template_dir': 'templates',
            'skip_default_generators': False,
        }

        if os.path.exists(self.conf_path):
            with open(self.conf_path) as f:
                try:
                    conf.update(yaml.load(f))
                except yaml.error.YAMLError as e:
                    raise YamlError(self.conf_path, e) from None

        conf.update(self.conf_overwrite)

        #TODO: Error on extra conf fields
        return conf

    def add_default_generators(self):
        COLLECTION_CONF = "_collection.yaml"
        # Collection generator for each _collection.yaml file
        for abspath, relpath in self.walk_content(patterns=COLLECTION_CONF):
            url = normalize_url(remove_suffix(relpath, COLLECTION_CONF))
            generator = generators.Collection(url, abspath)
            self.add_generator(generator)

        # Markdown page generator
        self.add_generator(generators.MarkdownGenerator())

        # Static File Generator
        static_conf = self.conf.pop("static", {}) or {}
        if static_conf:
            static_gen = generators.StaticFileGeneraor.from_conf(self.conf_path, static_conf)
            self.add_generator(static_gen)

    @jinja2.contextfilter
    def markdown_filter(self, context, value):
        md_parser = Markdown()
        template = self.jinja_env.from_string(value)
        md = template.render(context)
        out = md_parser.convert(md)
        return jinja2.Markup(out)

    def make_jinja_environment(self):
        return jinja2.Environment(
            loader=jinja2.FileSystemLoader(self.template_dir),
            autoescape=True,
            undefined=jinja2.StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render_template(self, template, context):

        # Get template
        try:
            t = self.jinja_env.get_template(template)
        except jinja2.exceptions.TemplateNotFound as e:
            if template == "default.html":
                t = self.jinja_env.from_string("{{ content | markdown }}")
            else:
                raise TemplateError.from_jinja(e, template) from None
        except jinja2.exceptions.TemplateError as e:
            raise TemplateError.from_jinja(e, template) from None

        # Render template
        try:
            return t.render(context)
        except jinja2.exceptions.UndefinedError as e:
            e2 = e
            raise TemplateVarUndefined(t, jinja_exception=e, context=context) from None
        except jinja2.exceptions.TemplateError as e:
            raise TemplateError.from_jinja(e, template) from None

    def get_build_path(self, path):
        absolute = os.path.abspath(os.path.join(self.build_dir, path))
        if os.path.isabs(path) or not absolute.startswith(self.build_dir):
            raise ValueError("Tried to get path {} outside of build directory "
                    "{}".format(absolute, self.build_dir))
        return absolute

    def get_content_path(self, path):
        absolute = os.path.abspath(os.path.join(self.content_dir, path))
        if not absolute.startswith(self.content_dir):
            raise ValueError("Tried to get path {} outside of content directory "
                    "{}".format(absolute, self.content_dir))
        return absolute

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
        if self.has_generated_urls:
            raise RuntimeError("reset() must be called before calling generate_urls() a second time")
        self.has_generated_urls = True

        for generator in self._generators:
            generator(self)
        if self.print_progress:
            print()  # Newline after printing in consume()

    def build_content(self):
        """Yield pages as they are rendered into the build directory."""
        if self.has_built:
            raise RuntimeError("reset() must be called before calling build_content() a second time")
        self.has_built = True

        # Create build dir
        if not os.path.isdir(self.build_dir):
            os.makedirs(self.build_dir)

        # Record existing files in build dir
        existing_files = set()
        for abspath, relpath in walk_dir(self.build_dir):
            existing_files.add(abspath)

        # Render all urls
        written_files = set()
        for url, view in self.url_map.items():
            filename = self._build_url(url, view)
            written_files.add(filename)
            yield url

        # Remove files that existed before
        for filename in existing_files - written_files:
            os.remove(filename)
            parent = os.path.dirname(filename)
            if not os.listdir(parent):
                os.removedirs(parent)

    def _build_url(self, url, view):

        # Remove leading '/'
        assert url[0] == '/'
        url = url[1:]

        # A view can be:
        #   - Instance of `buildactions.BuildAction`
        #       view.do() is called to perform the action.
        #   - String
        #       Acts as if `buildactions.Html(view)` were returned.
        #   - Any callable
        #       Calls the view, then acts accordingly like one of the above.
        if callable(view):
            view = view()
        if isinstance(view, buildactions.BuildAction):
            action = view
        elif isinstance(view, str):
            action = buildactions.Html(view)
        else:
            raise RuntimeError("Could not resolve action from view {}".format(view))

        out_path = self.get_build_path(url)
        file_written = action.do(self, out_path)
        if not file_written:
            file_written = out_path

        return file_written

    @property
    def needs_reset(self):
        return self.has_built or self.has_generated_urls

    def generate(self):
        """The main no-frills entry point to generate content."""
        if self.needs_reset:
            raise RuntimeError("reset() must be called before calling generate() a second time")

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
        raise AttributeError('Collection "{}" not found'.format(name))

    def __len__(self):
        return sum([1 for collection in self])
