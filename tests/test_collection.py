
import clearice

from .base import BaseTest

class TestCollection(BaseTest):

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
        self.assertGenerateRaises(
            clearice.exceptions.YamlError,
            "\nsequence entries are not allowed here\n"
        )

        # Valid YAML, bad config
        to_test = [
            ("""
                - config_is
                - not_a
                - dictionary
            """, "Expected dict describing collection"),
            ("""
                name: blog
                unexpected_field: foo
                pages:
                    - title: index
                      template: test_page.html
            """, "Unexpected fields")
        ]
        for yaml_str, failure_regex in to_test:
            with self.subTest(yaml=yaml_str):
                self.write_file("content/blog/_collection.yaml", yaml_str)
                self.write_file("templates/default.html", "{{ url }}")
                self.assertGenerateRaises(
                    clearice.exceptions.ConfigError,
                    failure_regex
                )

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
        to_test = [
            ("""
                pages:
                    - title: /subdir/page1
            """, 'Collection page names cannot start with a "/"'),
            ("""
                pages:
                    - foo: bar
            """, "Collection pages must have a title"),
            ("""
                pages:
                    -
            """, "Expected dict describing page"),
            ("""
                pages:
                    - title: foo
                    - title: foo
            """, 'Page title "foo" with url "/blog/foo/" conflicts with an existing url.'),
            ("""
                pages:
                    - title:
                        foo: bar
                    - title: foo
            """, "Page title must be a non-zero length string"),
            ("""
                pages:
                    - title: index
                      extraneous_field: foo
            """, "Unexpected fields in collection page"),
            ("""
                pages:
                    not_a: list
            """, '"pages" field must be a list'),
            ("""
                pages:
                    - not_a_dict
            """, "Expected dict describing page"),
        ]
        for yaml_str, failure_regex in to_test:
            with self.subTest(yaml=yaml_str):
                self.write_file("content/blog/_collection.yaml", yaml_str)
                self.write_file("templates/default.html", "{{ url }}")
                self.assertGenerateRaises(
                    clearice.exceptions.ConfigError,
                    failure_regex,
                )

    def test_extra_yaml_keys(self):
        tests = [
            ("""
                name: blog
                extraneous_field: foo
            """, "Unexpected field"),
            ("""
                name: blog
                pages:
                    - title: blah
                      extraneous_field: foo
            """, "Unexpected fields in collection page:"),
        ]
        for yaml_txt, failure_regex in tests:
            with self.subTest(config=yaml_txt):
                self.write_file("content/blog/_collection.yaml", yaml_txt)
                self.assertGenerateRaises(
                    clearice.exceptions.ConfigError,
                    failure_regex
                )

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
        self.assertGenerateRaises(
            clearice.exceptions.ConfigError,
            "Configuration error: Cannot have two generators with the same name \"blog\""
        )

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
            ("{%",              "Error with url format: tag name expected"),
            ("{{ blah|blah }}", "Error with url format: no filter named 'blah'"),
            ("/this/",          'Collection url formats are relative to the collection root, they cannot start with a "/"'),
        ]
        for fmt, failure_regex in formats:
            with self.subTest(fmt=fmt):
                self.write_file("content/blog/_collection.yaml", """
                    url_format: "{}"
                """.format(fmt))
                self.write_file("templates/default.html", "")
                self.write_file("content/blog/item.md", "---\n---")
                self.assertGenerateRaises(
                    clearice.exceptions.ConfigError,
                    failure_regex
                )
