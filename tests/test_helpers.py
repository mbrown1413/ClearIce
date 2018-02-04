
import unittest

from clearice import helpers

class TestHelpers(unittest.TestCase):

    def test_normalize_url(self):
        tests = [
            # Does not remove filename extensions
            ("/blah/this.md", "/blah/this.md/"),
            # Removes leading .
            ("./blah/this/", "/blah/this/"),
            # If index file, remove filename
            ("/blah/index", "/blah/"),
            ("/blah/index/", "/blah/index/"),
            # Ensures starts/ends with /
            ("blah/this", "/blah/this/"),
            # Exactly one '/' between each part
            ("/blah///foo///////this/", "/blah/foo/this/"),
        ]
        for url_in, url_out in tests:
            with self.subTest(url_in=url_in, url_out=url_out):
                result = helpers.normalize_url(url_in)
                self.assertEqual(result, url_out)
