
import os
import stat

import clearice

from .base import BaseTest

class TestBuildActions(BaseTest):

    def setUp(self):
        super().setUp()
        self.write_file("content/file", "file content")
        self.make_app(skip_default_generators=True)

    def test_file(self):
        action = clearice.buildactions.File("blah")

        self.app.add_url("/file", action)
        self.generate()

        self.assertFileContents("build/file", "blah")
        self.assertTrue(os.path.isfile(os.path.join(self.tmp_dir, "build/file")))

    def test_html(self):
        action = clearice.buildactions.Html("blah")

        self.app.add_url("/file", action)
        self.generate()

        self.assertFileContents("build/file/index.html", "blah")
        self.assertTrue(os.path.isfile(os.path.join(self.tmp_dir, "build/file/index.html")))

    def test_copy(self):
        action = clearice.buildactions.Copy("file")

        self.app.add_url("/file", action)
        self.generate()

        self.assertFileContents("build/file", "file content")
        self.assertTrue(os.path.isfile(os.path.join(self.tmp_dir, "build/file")))

    def test_link_soft(self):
        action = clearice.buildactions.Link("file")

        self.app.add_url("/file", action)
        self.generate()

        self.assertFileContents("build/file", "file content")
        self.assertSoftLink("build/file", "content/file", is_relative=True)

    def test_link_soft_absolute(self):
        action = clearice.buildactions.Link("file", absolute=True)

        self.app.add_url("/file", action)
        self.generate()

        self.assertFileContents("build/file", "file content")
        self.assertSoftLink("build/file", "content/file", is_relative=False)

    def test_link_hard(self):
        action = clearice.buildactions.Link("file", hard=True)

        self.app.add_url("/file", action)
        self.generate()

        self.assertFileContents("build/file", "file content")
        self.assertIsHardLink("build/file")
