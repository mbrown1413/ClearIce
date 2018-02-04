
import os
import unittest
import tempfile

import clearice

class BaseTest(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tmp_dir = None
        self.paths_accounted_for = set()
        self.app = None  # Set by generate()

    def write_file(self, path, content):
        if not self.tmp_dir:
            self.tmp_dir = tempfile.mkdtemp()

        abspath = os.path.join(self.tmp_dir, path)
        self.assertTrue(abspath.startswith(self.tmp_dir))
        os.makedirs(os.path.dirname(abspath), exist_ok=True)
        with open(abspath, 'w', encoding='utf-8') as f:
            f.write(content)
        self.account_for_file(path)

    def account_for_file(self, path):
        self.paths_accounted_for.add(path)
    def account_for_files(self, paths):
        for path in paths:
            self.account_for_file(path)

    def read_file(self, path):
        self.assertIsNotNone(self.tmp_dir)
        abspath = os.path.join(self.tmp_dir, path)
        self.assertTrue(os.path.exists(abspath))
        self.account_for_file(path)
        with open(abspath, encoding='utf-8') as f:
            content = f.read()
        return content

    def assertFileContents(self, path, expected_contents):
        content = self.read_file(path)
        self.assertEqual(content, expected_contents)

    def assertNoLooseFiles(self):
        self.assertIsNotNone(self.tmp_dir)
        for dirpath, dirnames, filenames in os.walk(self.tmp_dir):
            for filename in filenames:

                # Get path relative to self.tmp_dir
                path = os.path.join(dirpath, filename)
                assert path.startswith(self.tmp_dir+'/')
                relpath = path[len(self.tmp_dir)+1:]

                self.assertIn(relpath, self.paths_accounted_for)

    def assertGenerateRaises(self, *args, **kwargs):
        with self.assertRaisesRegex(*args, **kwargs):
            self.generate()

    def generate(self, **kwargs):
        if "root_path" not in kwargs:
            kwargs["root_path"] = self.tmp_dir
        self.app = clearice.app.App(**kwargs)
        self.app.generate()
        return self.app

    def tearDown(self):
        if self.tmp_dir:
            self.assertNoLooseFiles()
