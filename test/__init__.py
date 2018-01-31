
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

    def generate(self):
        os.chdir(self.tmp_dir)
        self.app = clearice.main(catch_exceptions=False)
        return self.app

    def tearDown(self):
        if self.tmp_dir:
            self.assertNoLooseFiles()


class TestApp(BaseTest):

    def test_urls(self):
        self.write_file("templates/default.html", "{{ content }}")
        self.write_file("content/index.md", "---\n---\nHello!")
        self.write_file("content/about.md", "---\n---\nAbout!")
        self.write_file("content/subdir/foo.md", "---\n---\nfoo!")
        self.write_file("content/subdir/index.md", "---\n---\nsubdir index")
        self.generate()
        self.assertFileContents("build/index.html", "Hello!")
        self.assertFileContents("build/about/index.html", "About!")
        self.assertFileContents("build/subdir/foo/index.html", "foo!")
        self.assertFileContents("build/subdir/index.html", "subdir index")

    def test_mankdown_simple(self):
        self.write_file("templates/default.html", "{{ content | markdown }}")
        self.write_file("content/index.md", "---\n---\nHello!\n_i_**b**")
        self.generate()
        self.assertFileContents("build/index.html", "<p>Hello!\n<em>i</em><strong>b</strong></p>")

    def test_frontmatter_simple(self):
        self.write_file("templates/default.html", "{{ content }}{{ var1 }}")
        self.write_file("content/index.md", "---\nvar1: val1\n---\nHello!\n")
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
                self.write_file("content/index.md", test)  # No delimiters
                self.assertFileContents("content/index.md", test)
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
                self.write_file("content/index.md", test)  # No delimiters
                with self.assertRaises(clearice.FrontmatterError):
                    self.generate()

    def test_frontmatter_parse_empty(self):
        #  Empty frontmatter yaml gives empty frontmatter dict
        self.write_file("templates/default.html", "{{ context.frontmatter | safe }}")
        self.write_file("content/index.md", "---\n\n---\n")
        self.generate()
        self.assertFileContents("build/index.html", "{}")

    def test_frontmatter_parse_errors(self):
        self.write_file("templates/default.html", "{{ context.frontmatter | safe }}")
        tests = [
            "-item1\n-item2",
        ]
        for fm in tests:
            with self.subTest(frontmatter=fm):
                self.write_file("content/index.md", "---\n{}\n---\n".format(fm))
                with self.assertRaises(clearice.FrontmatterError):
                    self.generate()

        # TODO: Not dict
        # TODO: Parsing
        pass

    def test_ignored_files(self):
        self.write_file("templates/default.html", "{{ content }}")
        self.write_file("content/.index.md.swp", "---\n\n---\nblah")
        self.write_file("content/.secret", "---\n\n---\nblah")
        self.write_file("content/index.md~", "---\n\n---\nblah")
        self.generate()
        self.assertNoLooseFiles()

    def test_context(self):
        self.write_file("content/pagename.md", "---\nfmvar: blah\n---\nblah")
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
        self.write_file("content/index.md", "---\ntemplate: nonexistant.html\n---")
        with self.assertRaises(clearice.TemplateNotFound):
            self.generate()

    def test_template_parse_error(self):
        self.write_file("templates/default.html", "{% }}")
        self.write_file("content/index.md", "---\n---")
        with self.assertRaises(clearice.TemplateError):
            self.generate()

    def test_template_var_not_found(self):

        # Undefined context fine if not put through filter...
        self.write_file("templates/default.html", "{{ blah }}")
        self.write_file("content/index.md", "---\n---")
        self.generate()
        self.assertFileContents("build/index.html", "")

        # ...but errors when testing attributes
        self.write_file("templates/default.html", "{{ blah.foo }}")
        with self.assertRaises(clearice.TemplateError):
            self.generate()

    def test_filename_date_and_name(self):
        self.write_file("content/blog/_collection.yaml", "")
        self.write_file("templates/default.html",
                "{{ date }}, {{ date.strftime('%A') }}, {{ slug }}")
        self.write_file("content/blog/2020-01-02_post_name.md", "---\n---")
        self.generate()
        self.assertFileContents("build/blog/2020-01-02_post_name/index.html",
                "2020-01-02, Thursday, post_name")

    def test_date_from_frontmatter(self):
        self.write_file("content/blog/_collection.yaml", "")
        self.write_file("templates/default.html",
                "{{ date }}, {{ date.strftime('%A') }}")
        self.write_file("content/blog/2000-01-01_post.md",
                "---\ndate: 2020-01-02\n---")  # Frontmatter overwrites filename date
        self.generate()
        self.assertFileContents("build/blog/2000-01-01_post/index.html",
                "2020-01-02, Thursday") #TODO: day of week is locale specific

    def test_invalid_dates(self):

        # Cannot parse date in filename results in no date context
        self.write_file("content/blog/_collection.yaml", "")
        self.write_file("templates/default.html",
                "{{ date }}, {{ slug }}")
        self.write_file("content/blog/202A-01-02_post_name.md", "---\n---")
        self.generate()
        self.assertFileContents("build/blog/202A-01-02_post_name/index.html",
                ", 202A-01-02_post_name")

        # Date in frontmatter out of month range
        self.write_file("templates/default.html",
                "{{ date }}, {{ date.day }}, {{ slug }}")
        self.write_file("content/blog/post.md", '---\ndate: 2000-01-38\n---')
        with self.assertRaises(clearice.FrontmatterError):
            self.generate()

        # Date in frontmatter as string is fine
        self.write_file("templates/default.html",
                "{{ date }}, {{ slug }}")
        self.write_file("content/blog/post.md", '---\ndate: "2000-01-38"\n---')
        self.generate()
        self.assertFileContents("build/blog/post/index.html",
                "2000-01-38, post")

class TestCollections(BaseTest):

    def test_no_items(self):
        self.write_file("content/blog/_collection.yaml", """
            name: blog
            pages:
                - title: index
                  template: test_page.html
        """)
        self.write_file("templates/test_page.html",
                "{{ collection | length }}")
        self.generate()
        self.assertFileContents("build/blog/index.html", "0")

    def test_simple(self):
        self.write_file("content/blog/_collection.yaml", """
            name: blog
        """)
        self.write_file("templates/default.html",
                "{{ title }}")
        self.write_file("content/blog/item1.md",
                "---\ntitle: Item 1\n---")
        self.write_file("content/blog/item2.md",
                "---\ntitle: Item 2\n---")
        self.generate()
        self.assertFileContents("build/blog/item1/index.html", "Item 1")
        self.assertFileContents("build/blog/item2/index.html", "Item 2")

    def test_blank_yaml(self):
        self.write_file("content/blog/_collection.yaml", "")
        self.write_file("templates/default.html",
                "{{ title }}")
        self.write_file("content/blog/item1.md",
                "---\ntitle: Item 1\n---")
        self.write_file("content/blog/item2.md",
                "---\ntitle: Item 2\n---")
        self.generate()
        self.assertFileContents("build/blog/item1/index.html", "Item 1")
        self.assertFileContents("build/blog/item2/index.html", "Item 2")

    def test_yaml_empty_values(self):
        # When values like "context:" are empty, they return None. Are
        # these cases handled correctly when we're expecting a dict or
        # string?

        self.write_file("content/blog/item1.md", "---\n---")

        tests = [  # (yaml, template, expected output)
            ("name:", "{{ collection.name }}", ""),
            ("pages:", "{{ collection.pages | length }}", "0"),
            ("context:", "{{ collection.context }}", "{}"),
            ("order:", "", ""),  # Just assert doesn't error
        ]

        for yaml_txt, template_txt, expected in tests:
            with self.subTest(yaml=yaml_txt, template=template_txt, expected=expected):
                self.write_file("content/blog/_collection.yaml", yaml_txt)
                self.write_file("templates/default.html", template_txt)
                self.generate()
                self.assertFileContents("build/blog/item1/index.html", expected)

    def test_bad_config(self):

        # YAML parsing error
        self.write_file("content/blog/_collection.yaml", "blah: -")
        with self.assertRaises(clearice.YamlError):
            self.generate()

        # Valid YAML, bad config
        yaml_to_test = [
            """
                - config_is
                - not_a
                - dictionary
            """,
            """
                name: blog
                unexpected_field: foo
                pages:
                    - title: index
                      template: test_page.html
            """
        ]
        for yaml_str in yaml_to_test:
            with self.subTest(yaml=yaml_str):
                self.write_file("content/blog/_collection.yaml", yaml_str)
                self.write_file("templates/default.html", "{{ url }}")
                with self.assertRaises(clearice.ConfigError):
                    self.generate()

    def test_item_order(self):

        # Order by title. BBB comes before CCC
        self.write_file("content/blog/_collection.yaml", """
            name: blog
            order: title
        """)
        self.write_file("templates/default.html",
                "{{ title }}. {% for item in collection %}{{ item.title }} {% endfor %}")
        self.write_file("content/blog/item1.md",
                "---\ntitle: BBB\n---")
        self.write_file("content/blog/item2.md",
                "---\ntitle: CCC\n---")
        self.generate()
        self.assertFileContents("build/blog/item1/index.html", "BBB. BBB CCC ")
        self.assertFileContents("build/blog/item2/index.html", "CCC. BBB CCC ")

        # Now change CCC to AAA. AAA comes before BBB
        self.write_file("content/blog/item2.md",
                "---\ntitle: AAA\n---")
        self.generate()
        self.assertFileContents("build/blog/item1/index.html", "BBB. AAA BBB ")
        self.assertFileContents("build/blog/item2/index.html", "AAA. AAA BBB ")

    def test_item_order_date(self):
        self.write_file("content/blog/_collection.yaml", """
            name: blog
            order: date
        """)
        self.write_file("templates/default.html",
                "{{ a }}. {% for item in collection %}{{ item.a }} {% endfor %}")
        self.write_file("content/blog/item1.md",
                "---\ndate: 2018-01-26\na: fourth\n---")
        self.write_file("content/blog/item2.md",
                "---\ndate: 2018-01-22\na: second\n---")
        self.write_file("content/blog/item3.md",
                "---\ndate: 2018-01-20\na: first\n---")
        self.write_file("content/blog/item4.md",
                "---\ndate: 2018-01-24\na: third\n---")
        self.generate()
        self.assertFileContents("build/blog/item1/index.html", "fourth. first second third fourth ")
        self.assertFileContents("build/blog/item2/index.html", "second. first second third fourth ")
        self.assertFileContents("build/blog/item3/index.html", "first. first second third fourth ")
        self.assertFileContents("build/blog/item4/index.html", "third. first second third fourth ")

        # Now switch first to come last
        self.write_file("content/blog/item3.md",
                "---\ndate: 2222-01-20\na: first\n---")
        self.generate()
        self.assertFileContents("build/blog/item1/index.html", "fourth. second third fourth first ")
        self.assertFileContents("build/blog/item2/index.html", "second. second third fourth first ")
        self.assertFileContents("build/blog/item3/index.html", "first. second third fourth first ")
        self.assertFileContents("build/blog/item4/index.html", "third. second third fourth first ")

    def test_non_item_file(self):
        self.write_file("content/blog/_collection.yaml", """
            name: blog
            order: title
            pages:
                - title: index
                  template: blog/index.html
        """)
        self.write_file("templates/default.html",
                "{{ title }}")
        self.write_file("templates/blog/index.html",
                "{% for post in collections.blog %}{{ post.url }} {% endfor %}")
        self.write_file("content/blog/item1.md",
                "---\ntitle: Item 1\n---")
        self.write_file("content/blog/item2.md",
                "---\ntitle: Item 2\n---")
        self.write_file("content/blog/item3/index.md", "---\ntitle: Item 3\n---")
        self.write_file("content/blog/item3/supplimental_content.md", "---\n---")
        self.write_file("content/blog/not_an_item.yaml", "")
        self.generate()
        self.assertFileContents("build/blog/item1/index.html", "Item 1")
        self.assertFileContents("build/blog/item2/index.html", "Item 2")
        self.assertFileContents("build/blog/item3/index.html", "Item 3")
        self.assertFileContents("build/blog/item3/supplimental_content/index.html", "")
        self.assertFileContents("build/blog/index.html",
                "/blog/item1/ /blog/item2/ /blog/item3/ ")

        # We don't copy over unknown files. In the future, specific unhandled
        # data file extensions will be copied though.
        self.assertFalse(self.app.is_consumed("blog/blah.yaml"))

    def test_blank_yaml(self):
        self.write_file("content/blog/_collection.yaml", "")
        self.write_file("templates/default.html",
                "{{ title }}")
        self.write_file("content/blog/item1.md",
                "---\ntitle: Item 1\n---")
        self.write_file("content/blog/item2.md",
                "---\ntitle: Item 2\n---")
        self.generate()
        self.assertFileContents("build/blog/item1/index.html", "Item 1")
        self.assertFileContents("build/blog/item2/index.html", "Item 2")



    def test_pages(self):
        self.write_file("content/blog/_collection.yaml", """
            name: blog
            pages:
                - title: index
                  template: page.html
                  context:
                    foo: bar
        """)

        # No markdown content
        self.write_file("templates/page.html",
                "{{ url }}\n{{ foo }}\n{{ content|markdown }}")
        self.generate()
        self.assertFileContents("build/blog/index.html", "/blog/\nbar\n")

        # With markdown content
        self.write_file("content/blog/index.md", "---\n---\n_blah_")
        self.generate()
        self.assertFileContents("build/blog/index.html",
                "/blog/\nbar\n<p><em>blah</em></p>")

    def test_pages_with_path(self):
        # Pages that have a title with a "/" in it.
        self.write_file("content/blog/_collection.yaml", """
            pages:
                - title: index
                - title: tags
                - title: subdir/page1
                - title: subdir/page2/
                - title: subdir//page3//
        """)

        self.write_file("templates/default.html", "{{ url }}")
        self.generate()
        self.assertFileContents("build/blog/index.html", "/blog/")
        self.assertFileContents("build/blog/tags/index.html", "/blog/tags/")
        self.assertFileContents("build/blog/subdir/page1/index.html", "/blog/subdir/page1/")
        self.assertFileContents("build/blog/subdir/page2/index.html", "/blog/subdir/page2/")
        self.assertFileContents("build/blog/subdir/page3/index.html", "/blog/subdir/page3/")

    def test_page_bad_config(self):
        yaml_to_test = [
            """
                pages:
                    - title: /subdir/page1
            """,
            """
                pages:
                    - foo: bar
            """,
            """
                pages:
                    -
            """,
            """
                pages:
                    - title: foo
                    - title: foo
            """,
            """
                pages:
                    - title:
                        foo: bar
                    - title: foo
            """,
            """
                pages:
                    - title: index
                      extraneous_field: foo
            """,
            """
                pages:
                    not_a: list
            """,
            """
                pages:
                    - not_a_dict
            """,
        ]
        for yaml_str in yaml_to_test:
            with self.subTest(yaml=yaml_str):
                self.write_file("content/blog/_collection.yaml", yaml_str)
                self.write_file("templates/default.html", "{{ url }}")
                with self.assertRaises(clearice.ConfigError):
                    self.generate()

    def test_extra_yaml_keys(self):
        tests = [
            """
                name: blog
                extraneous_field: foo
            """,
            """
                name: blog
                pages:
                    extraneous_field: foo
            """,
        ]
        for yaml_txt in tests:
            with self.subTest(config=yaml_txt):
                self.write_file("content/blog/_collection.yaml", yaml_txt)
                with self.assertRaises(clearice.ConfigError):
                    self.generate()

    def test_name(self):
        self.write_file("content/blog1/_collection.yaml", """
            name: blog1
        """)
        self.write_file("content/blog2/_collection.yaml", "")
        self.write_file("content/index.md", "---\n---")
        self.write_file("templates/default.html",
                "{{ collections.blog1.url }}\n"
                "{{ collections|length}}\n"
                "{% for c in collections %}Url: {{ c.url }}\n{% endfor %}")
        self.generate()
        self.assertFileContents("build/index.html",
                "/blog1/\n"
                "2\n"
                "Url: /blog2/\n"  # Order is actually arbitrary here
                "Url: /blog1/\n")

    def test_duplicate_name(self):
        # ConfigError when two collections have the same name
        self.write_file("content/blog1/_collection.yaml", """
            name: blog
        """)
        self.write_file("content/blog2/_collection.yaml", """
            name: blog
        """)
        with self.assertRaises(clearice.ConfigError):
            self.generate()

    def test_collection_name_not_found(self):
        self.write_file("content/blog1/_collection.yaml", """
            name: blog
        """)
        self.write_file("templates/default.html", "{{ collections.notexist }}")
        self.write_file("content/index.md", "---\n---")
        self.generate()
        self.assertFileContents("build/index.html", "None")

    def test_context(self):
        self.write_file("content/blog1/_collection.yaml", """
            name: blog1
            context:
                foo: bar
            pages:
                - title: index
                  context:
                      page_data: blah
        """)
        self.write_file("content/blog2/_collection.yaml", """
            name: blog2
        """)
        self.write_file("templates/default.html",
                "{{ url }}, {{ foo }}, {{ collection.url }}, {{ page_data }}, {{ content }}\n"
                "{% for c in collections %}{{ c.name }} {% endfor %}")
        self.write_file("content/blog1/item.md", "---\npage_data: blah\n---\n"
                "content!")
        self.generate()

        self.assertFileContents("build/blog1/index.html",
                "/blog1/, bar, /blog1/, blah, \n"
                "blog2 blog1 ")
        self.assertFileContents("build/blog1/item/index.html",
                "/blog1/item/, bar, /blog1/, blah, content!\n"
                "blog2 blog1 ")

    def test_url_format(self):
        self.write_file("content/blog/_collection.yaml", """
            name: blog
            context:
                foo: bar
            url_format: "{{ foo }}/{{ date }}/{{ page_data }}"
        """)
        self.write_file("templates/default.html",
                "{{ url }}")
        self.write_file("content/blog/item.md", "---\npage_data: blah\ndate: 2012-12-21\n---\n")
        self.generate()

        self.assertFileContents("build/blog/bar/2012-12-21/blah/index.html",
                "/blog/bar/2012-12-21/blah/")

    def test_url_format_errors(self):
        formats = [
            "{%",
            "{{ blah|blah }}",
            "/this/",
        ]
        for fmt in formats:
            with self.subTest(fmt=fmt):
                self.write_file("content/blog/_collection.yaml", """
                    url_format: "{}"
                """.format(fmt))
                self.write_file("templates/default.html", "")
                self.write_file("content/blog/item.md", "---\n---")
                with self.assertRaises(clearice.ConfigError):
                    self.generate()
