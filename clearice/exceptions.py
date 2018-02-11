
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
