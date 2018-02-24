
import clearice

from .base import BaseTest

class TestStaticFiles(BaseTest):

    def test_no_conf(self):
        """Files aren't copied by default"""
        self.write_file("content/file.txt", "file content")
        self.generate()
        self.assertFileNotExists("build/file.txt")

    def test_basic(self):
        self.write_file("content/file.txt", "file content")
        self.write_file("conf.yaml", """
            static:
                patterns:
                    - "*.txt"
        """)
        self.generate()
        self.assertIsNormalFile("build/file.txt")
        self.assertFileContents("build/file.txt", "file content")

    def test_link(self):
        self.write_file("content/file.txt", "file content")
        self.write_file("conf.yaml", """
            static:
                patterns:
                    - "*.txt"
                link: true
        """)
        self.generate()
        self.assertSoftLink("build/file.txt", "content/file.txt", is_relative=True)
        self.assertFileContents("build/file.txt", "file content")

    def test_link_size1(self):
        self.write_file("content/small.txt", "small")
        self.write_file("content/large.txt", "LARGE"*50)
        self.write_file("conf.yaml", """
            static:
                link_above: 100 B
                patterns:
                    - "*.txt"
        """)
        self.generate()

        self.assertIsNormalFile("build/small.txt")
        self.assertFileContents("build/small.txt", "small")

        self.assertSoftLink("build/large.txt", "content/large.txt", is_relative=True)
        self.assertFileContents("build/large.txt", "LARGE"*50)

    def test_link_size2(self):
        self.write_file("content/small.txt", "s"*1024)
        self.write_file("content/large.txt", "l"*1025)
        self.write_file("conf.yaml", """
            static:
                link_above: 1 kb
                patterns:
                    - "*.txt"
        """)
        self.generate()

        self.assertIsNormalFile("build/small.txt")
        self.assertFileContents("build/small.txt", "s"*1024)

        self.assertSoftLink("build/large.txt", "content/large.txt", is_relative=True)
        self.assertFileContents("build/large.txt", "l"*1025)

    def test_link_hard(self):
        self.write_file("content/file.txt", "file content")
        self.write_file("conf.yaml", """
            static:
                patterns:
                    - "*.txt"
                link: true
                link_type: hard
        """)
        self.generate()
        self.assertIsHardLink("build/file.txt")
        self.assertFileContents("build/file.txt", "file content")

    def test_link_conf_errors(self):
        tests = [
            ("""
                static:
                    link_above: 100 zillion
            """, "Unrecognized file size: 100 zillion"),
            ("""
                static:
                    link: blah
            """, 'static link option must be true or false'),
            ("""
                static:
                    foo: bar
            """, 'Unexpected field "foo" in static config'),
            ("""
                static:
                    - list when it
                    - should be a map
            """, 'Expected static option to be a dict, got "<class \'list\'>"'),
            ("""
                static:
                    patterns:
                        this: is a map
                        should: be a list
            """, 'static patterns must be a list of strings'),
            ("""
                static:
                    link_type: geort
            """, 'Unrecognized link_type "geort", must be "soft" or "hard"'),
        ]
        for conf, error_msg in tests:
            self.write_file("conf.yaml", conf)
            self.assertGenerateRaises(
                clearice.exceptions.ConfigError,
                error_msg
            )

    def test_all_link_options(self):
        """Every combination of `link` and `link_above` options."""
        l = self.assertIsSoftLink
        f = self.assertIsNormalFile
        tests = [  # (link, link_above, small file assert, large file assert)
            (None,    None,     f, f),
            ('false', None,     f, f),
            ('true',  None,     l, l),
            (None,    '0',      l, l),
            ('false', '0',      f, f),
            ('true',  '0',      l, l),
            (None,    '100 B',  f, l),
            ('false', '100 B',  f, f),
            ('true',  '100 B',  f, l),
            (None,    '100 MB', f, f),
            ('false', '100 MB', f, f),
            ('true',  '100 MB', f, f),
        ]
        self.write_file("content/small.txt", "small")
        self.write_file("content/large.txt", "LARGE"*50)
        for link, link_above, small_assert, large_assert in tests:
            link_line = "" if link is None else "link: "+link
            above_line = "" if link_above is None else "link_above: "+link_above
            self.write_file("conf.yaml", """
                static:
                    patterns:
                        - "*.txt"
                    {}
                    {}
            """.format(link_line, above_line))
            self.generate()

            small_assert("build/small.txt")
            large_assert("build/large.txt")
            self.assertFileContents("build/small.txt", "small")
            self.assertFileContents("build/large.txt", "LARGE"*50)
