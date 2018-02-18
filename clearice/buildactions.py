
import os
import shutil


class BuildAction():

    def do(self, app, dest):
        raise NotImplementedError()  # pragma: nocover

    @staticmethod
    def makedirs(dest):
        dirname = os.path.dirname(dest)
        if not os.path.isdir(dirname):
            os.makedirs(dirname)

class File(BuildAction):

    def __init__(self, content):
        self.content = content

    def do(self, app, dest):
        self.makedirs(dest)
        with open(dest, 'w') as f:
            f.write(self.content)

class Html(File):

    def do(self, app, dest):

        # Add index.html filename
        if not dest.endswith('/'):
            dest += '/'
        dest += 'index.html'

        super().do(app, dest)
        return dest

class Copy(BuildAction):

    def __init__(self, src):
        self.src = src

    def do(self, app, dest):
        self.makedirs(dest)
        shutil.copy(app.get_content_path(self.src), dest)

class Link(BuildAction):

    def __init__(self, src, hard=False, absolute=False):
        self.src = src
        self.hard = hard
        self.absolute = absolute
        if self.hard and self.absolute:
            raise ValueError("Links cannot be both hard and absolute.")

    def do(self, app, dest):
        self.makedirs(dest)
        if self.hard:
            os.link(app.get_content_path(self.src), dest)
        elif self.absolute:
            os.symlink(app.get_content_path(self.src), dest)
        else:
            os.symlink(
                os.path.relpath(app.get_content_path(self.src), os.path.dirname(dest)),
                dest
            )
