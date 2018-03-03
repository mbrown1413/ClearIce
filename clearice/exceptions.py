
import jinja2

from . import helpers

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
        if self.filename:
            return 'Configuration error in "{}"\n' \
                    '{}'.format(self.filename, self.msg)
        else:
            return 'Configuration error: {}'.format(self.msg)

class UrlConflictError(ClearIceException): pass

class TemplateError(ClearIceException):
    #TODO: Include context? It's helpful on variable undefined error.

    def __init__(self, template, url=None, msg=None, filename=None, lineno=None):
        if isinstance(template, jinja2.Template):
            self.template = template.name
            self.template_obj = template
        else:
            self.template = template
            self.template_obj = None
        self.url = url
        self.msg = msg
        self.filename = filename
        self.lineno = lineno

    def __str__(self):
        url_msg = ' for url '+self.url if self.url else ""
        file_msg = "in "+self.filename if self.filename else ""
        line_msg = " on line "+str(self.lineno) if self.lineno is not None else ""
        msg = ':\n'+self.msg if self.msg else ''
        return 'Error while processing template {}{}{}{}{}'.format(self.template, url_msg, file_msg, line_msg, msg)

    @classmethod
    def from_jinja(cls, e, template, url=None):
        if isinstance(e, jinja2.exceptions.TemplateNotFound):
            return TemplateNotFound(template, url)

        return cls(
            template, url,
            e.message,
            e.filename if hasattr(e, "filename") else None,
            e.lineno if hasattr(e, "lineno") else None,
        )

class TemplateVarUndefined(TemplateError):

    def __init__(self, *args, **kwargs):
        self.context = kwargs.pop('context', None)
        self.jinja_exception = kwargs.pop('jinja_exception', None)
        super().__init__(*args, **kwargs)

        # Format message
        self.msg = "Undefined Variable Reference"
        if self.context:
            fmt = 'Undefined variable "{}" in "{}" on line {}'
            undef_strs = []
            for var, filename, lineno in self.get_undef():
                s = fmt.format(var, filename, lineno)
                undef_strs.append(s)
            self.msg = '\n'.join(undef_strs)

        # Sometimes jinja doesn't give enough information to pinpoint the
        # error, like when an attribute is not found on a template variable
        # that is defined. If we think this is the case, just add the jinja
        # exception to the message.
        if not str(self.jinja_exception).endswith('is undefined'):
            self.msg += '\n'+str(self.jinja_exception)

    def get_undef(self):
        if self.context:
            uvars = helpers.get_undefined_template_vars(self.template_obj, self.context)
            yield from uvars

class TemplateNotFound(TemplateError):

    def __init__(self, *args, **kwargs):
        kwargs['msg'] = 'Template not found'
        super().__init__(*args, **kwargs)

class YamlError(ClearIceException):

    def __init__(self, filename, underlying_exception=None):
        self.filename = filename
        self.e = underlying_exception

    def __str__(self):
        long_desc = ":\n{}".format(self.e) if self.e else ""
        return 'Error reading yaml file "{}"{}'.format(self.filename, long_desc)
