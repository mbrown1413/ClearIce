
import os
import unittest
import tempfile

import clearice

class BaseTest(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tmp_dir = None
        self.paths_accounted_for = set()

    def write_file(self, path, contents):
        if not self.tmp_dir:
            self.tmp_dir = tempfile.mkdtemp()

        abspath = os.path.join(self.tmp_dir, path)
        self.assertTrue(abspath.startswith(self.tmp_dir))
        os.makedirs(os.path.dirname(abspath), exist_ok=True)
        with open(abspath, 'w', encoding='utf-8') as f:
            f.write(contents)
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
        contents = self.read_file(path)
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
        clearice.main(catch_exceptions=False)

    def tearDown(self):
        if self.tmp_dir:
            self.assertNoLooseFiles()


class TestApp(BaseTest):

    def test_urls(self):
        self.write_file("templates/default.html", "{{ content }}")
        self.write_file("contents/index.md", "---\n---\nHello!")
        self.write_file("contents/about.md", "---\n---\nAbout!")
        self.write_file("contents/subdir/foo.md", "---\n---\nfoo!")
        self.write_file("contents/subdir/index.md", "---\n---\nsubdir index")
        self.generate()
        self.assertFileContents("build/index.html", "Hello!")
        self.assertFileContents("build/about/index.html", "About!")
        self.assertFileContents("build/subdir/foo/index.html", "foo!")
        self.assertFileContents("build/subdir/index.html", "subdir index")

    def test_mankdown_simple(self):
        self.write_file("templates/default.html", "{{ content | markdown }}")
        self.write_file("contents/index.md", "---\n---\nHello!\n_i_**b**")
        self.generate()
        self.assertFileContents("build/index.html", "<p>Hello!\n<em>i</em><strong>b</strong></p>")

    def test_frontmatter_simple(self):
        self.write_file("templates/default.html", "{{ content }}{{ var1 }}")
        self.write_file("contents/index.md", "---\nvar1: val1\n---\nHello!\n")
        self.generate()
        self.assertFileContents("build/index.html", "Hello!\nval1")

    def test_frontmatter_delimiter(self):
        self.write_file("templates/default.html", "{{ content }}")
        self.account_for_file("build/index.html")
        tests = [
            "---\n---",  # No newline at end
            "---\n---\nblah",  # Normal
            "\n\n---\n---\nblah",  # Preceeding blank lines
            "\n   \n \t \n---\n---\nblah",  # With whitespace
        ]
        for test in tests:
            with self.subTest(md=test):
                self.write_file("contents/index.md", test)  # No delimiters
                self.assertFileContents("contents/index.md", test)
                self.generate()

    def test_frontmatter_delimiter_errors(self):
        self.write_file("templates/default.html", "{{ content }}")
        self.account_for_file("build/index.html")
        tests = [
            "",  # No frontmatter
            "blah",  # No frontmatter
            "---A\n---\n",
            "---\n---A\n",
            "a\n---\n---\n",  # Delimiters must be first
            "  \n  \ta\n---\n---\n",  # Delimiters must be first
        ]
        for test in tests:
            with self.subTest(md=test):
                self.write_file("contents/index.md", test)  # No delimiters
                with self.assertRaises(clearice.FrontmatterError):
                    self.generate()

    def test_frontmatter_parse_empty(self):
        #  Empty frontmatter yaml gives empty frontmatter dict
        self.write_file("templates/default.html", "{{ context.frontmatter | safe }}")
        self.write_file("contents/index.md", "---\n\n---\n")
        self.generate()
        self.assertFileContents("build/index.html", "{}")

    def test_frontmatter_parse_errors(self):
        self.write_file("templates/default.html", "{{ context.frontmatter | safe }}")
        tests = [
            "-item1\n-item2",
        ]
        for fm in tests:
            with self.subTest(frontmatter=fm):
                self.write_file("contents/index.md", "---\n{}\n---\n".format(fm))
                with self.assertRaises(clearice.FrontmatterError):
                    self.generate()

        # TODO: Not dict
        # TODO: Parsing
        pass

    def test_ignored_files(self):
        self.write_file("templates/default.html", "{{ content }}")
        self.write_file("contents/.index.md.swp", "---\n\n---\nblah")
        self.write_file("contents/.secret", "---\n\n---\nblah")
        self.write_file("contents/index.md~", "---\n\n---\nblah")
        self.generate()
        self.assertNoLooseFiles()

    def test_context(self):
        self.write_file("contents/pagename.md", "---\nfmvar: blah\n---\nblah")
        ctx_vars = ["url", "app", "template", "context", "frontmatter"]
        template = '\n'.join(map(lambda v: "{{ "+v+" | safe }}", ctx_vars))
        self.write_file("templates/default.html", template)
        self.generate()

        lines = self.read_file("build/pagename/index.html").split('\n')
        self.assertEqual(lines[0], "/pagename/")
        self.assertTrue(lines[1].startswith("<StaticGenApp"))
        self.assertEqual(lines[2], "default.html")
        self.assertEqual(lines[3][0], "{")
        self.assertEqual(lines[3][-1], "}")
        self.assertEqual(lines[4], "{'fmvar': 'blah'}")

    def test_template_not_found(self):
        self.write_file("contents/index.md", "---\ntemplate: nonexistant.html\n---")
        with self.assertRaises(clearice.TemplateNotFound):
            self.generate()

    @unittest.skip("Test not written")
    def test_template_parse_error(self):
        pass

    @unittest.skip("Test not written")
    def test_template_var_not_found(self):
        pass

    @unittest.skip("Test not written")
    def test_filename_date_and_name(self):
        pass

    @unittest.skip("Test not written")
    def test_filename_date_and_name_errors(self):
        pass

class TestCollections(BaseTest):

    def test_no_items(self):
        self.write_file("contents/blog/_collection.yaml", """
            name: blog
            pages:
                - name: index
                  template: test_page.html
        """)
        self.write_file("templates/test_page.html",
                "{{ collection | length }}")
        self.generate()
        self.assertFileContents("build/blog/index.html", "0")

    def test_simple(self):
        self.write_file("contents/blog/_collection.yaml", """
            name: blog
        """)
        self.write_file("templates/default.html",
                "{{ title }}")
        self.write_file("contents/blog/item1.md",
                "---\ntitle: Item 1\n---")
        self.write_file("contents/blog/item2.md",
                "---\ntitle: Item 2\n---")
        self.generate()
        self.assertFileContents("build/blog/item1/index.html", "Item 1")
        self.assertFileContents("build/blog/item2/index.html", "Item 2")

    def test_yaml_empty_values(self):
        # When values like "context:" are empty, they return None. Are
        # these cases handled correctly when we're expecting a dict or
        # string?

        self.write_file("contents/blog/item1.md", "---\n---")

        tests = [  # (yaml, template, expected output)
            ("name:", "{{ collection.name }}", ""),
            ("pages:", "{{ collection.pages | length }}", "0"),
            ("context:", "{{ collection.context }}", "{}"),
            ("order:", "", ""),  # Just assert doesn't error
            ("require_date:", "", ""),  # Just assert doesn't error
        ]

        for yaml_txt, template_txt, expected in tests:
            with self.subTest(yaml=yaml_txt, template=template_txt, expected=expected):
                self.write_file("contents/blog/_collection.yaml", yaml_txt)
                self.write_file("templates/default.html", template_txt)
                self.generate()
                self.assertFileContents("build/blog/item1/index.html", expected)

    def test_collection_yaml_errors(self):
        # Test if errors raised by yaml parsing are caught correctly
        self.write_file("contents/blog/_collection.yaml", "blah: -")
        with self.assertRaises(clearice.YamlDataError):
            self.generate()

    @unittest.skip("Test not written")
    def test_item_order(self):
        self.generate()

    def test_item_order_date(self):

        # Order by title. BBB comes before CCC
        self.write_file("contents/blog/_collection.yaml", """
            name: blog
            order: title
        """)
        self.write_file("templates/default.html",
                "{{ title }}. {% for item in collection.items %}{{ item.title }} {% endfor %}")
        self.write_file("contents/blog/item1.md",
                "---\ntitle: BBB\n---")
        self.write_file("contents/blog/item2.md",
                "---\ntitle: CCC\n---")
        self.generate()
        self.assertFileContents("build/blog/item1/index.html", "BBB. BBB CCC ")
        self.assertFileContents("build/blog/item2/index.html", "CCC. BBB CCC ")

        # Now change CCC to AAA. AAA comes before BBB
        self.write_file("contents/blog/item2.md",
                "---\ntitle: AAA\n---")
        self.generate()
        self.assertFileContents("build/blog/item1/index.html", "BBB. AAA BBB ")
        self.assertFileContents("build/blog/item2/index.html", "AAA. AAA BBB ")

    @unittest.skip("Test not written")
    def test_pages(self):
        pass

    @unittest.skip("Test not written")
    def test_pages_with_path(self):
        # Pages that have name with a "/" in it.
        pass

    @unittest.skip("Test not written")
    def test_page_no_name(self):
        pass

    @unittest.skip("Test not written")
    def test_pages_context(self):
        pass

    @unittest.skip("Test not written")
    def test_extra_yaml_keys(self):
        #TODO: Test both extra keys in top-level and in "pages"
        pass

    @unittest.skip("Test not written")
    def test_pages_content(self):
        pass

    @unittest.skip("Test not written")
    def test_name(self):
        # TODO: _collection.yaml with and without "name"
        pass

    @unittest.skip("Test not written")
    def test_context(self):
        # TODO: template context: collections, collection
        # TODO: explicitly provided in yaml "context"
        # TODO: Test in page and item context
        pass
