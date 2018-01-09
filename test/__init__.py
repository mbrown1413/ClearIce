
import os
import unittest
import tempfile

import clearice

class BaseTest(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tmp_dir = None
        self.paths_accounted_for = set()

    def create_file(self, path, contents):
        if not self.tmp_dir:
            self.tmp_dir = tempfile.mkdtemp()

        abspath = os.path.join(self.tmp_dir, path)
        self.assertTrue(abspath.startswith(self.tmp_dir))
        self.assertFalse(os.path.exists(abspath))
        os.makedirs(os.path.dirname(abspath), exist_ok=True)
        with open(abspath, 'w', encoding='utf-8') as f:
            f.write(contents)
        self.account_for_file(path)

    def account_for_file(self, path):
        self.paths_accounted_for.add(path)
    def account_for_files(self, paths):
        for path in paths:
            self.account_for_file(path)

    def get_file_contents(self, path):
        self.assertIsNotNone(self.tmp_dir)
        abspath = os.path.join(self.tmp_dir, path)
        self.assertTrue(os.path.exists(abspath))
        self.account_for_file(path)
        with open(abspath, encoding='utf-8') as f:
            content = f.read()
        return content

    def assertFileContents(self, path, expected_contents):
        contents = self.get_file_contents(path)
        self.assertEqual(contents, expected_contents)

    def assertNoLooseFiles(self):
        self.assertIsNotNone(self.tmp_dir)
        for dirpath, dirnames, filenames in os.walk(self.tmp_dir):
            for filename in filenames:

                # Get path relative to self.tmp_dir
                path = os.path.join(dirpath, filename)
                assert path.startswith(self.tmp_dir+'/')
                relpath = path[len(self.tmp_dir)+1:]

                self.assertIn(relpath, self.paths_accounted_for)

    def generate(self):
        os.chdir(self.tmp_dir)
        clearice.main()

    def tearDown(self):
        if self.tmp_dir:
            self.assertNoLooseFiles()


class TestApp(BaseTest):

    def test_urls(self):
        self.create_file("templates/default.html", "{{ content }}")
        self.create_file("contents/index.md", "---\n---\nHello!")
        self.create_file("contents/about.md", "---\n---\nAbout!")
        self.create_file("contents/subdir/foo.md", "---\n---\nfoo!")
        self.create_file("contents/subdir/index.md", "---\n---\nsubdir index")
        self.generate()
        self.assertFileContents("build/index.html", "Hello!")
        self.assertFileContents("build/about/index.html", "About!")
        self.assertFileContents("build/subdir/foo/index.html", "foo!")
        self.assertFileContents("build/subdir/index.html", "subdir index")

    def test_simple_markdown(self):
        self.create_file("templates/default.html", "{{ content | markdown }}")
        self.create_file("contents/index.md", "---\n---\nHello!\n_i_**b**")
        self.generate()
        self.assertFileContents("build/index.html", "<p>Hello!\n<em>i</em><strong>b</strong></p>")

    #def test_frontmatter(self):

class TestCollections(BaseTest):
    pass
