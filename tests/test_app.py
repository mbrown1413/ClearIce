
import clearice

from .base import BaseTest

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
                with self.assertRaises(clearice.exceptions.FrontmatterError):
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
            "-",
        ]
        for fm in tests:
            with self.subTest(frontmatter=fm):
                self.write_file("content/index.md", "---\n{}\n---\n".format(fm))
                with self.assertRaises(clearice.exceptions.FrontmatterError):
                    self.generate()

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
        self.assertTrue(lines[1].startswith("<App"))
        self.assertEqual(lines[2], "default.html")
        self.assertEqual(lines[3][0], "{")
        self.assertEqual(lines[3][-1], "}")
        self.assertEqual(lines[4], "{'fmvar': 'blah'}")

    def test_template_not_found(self):
        self.write_file("content/index.md", "---\ntemplate: nonexistant.html\n---")
        with self.assertRaises(clearice.exceptions.TemplateNotFound):
            self.generate()

    def test_template_parse_error(self):
        self.write_file("templates/default.html", "{% }}")
        self.write_file("content/index.md", "---\n---")
        with self.assertRaises(clearice.exceptions.TemplateError):
            self.generate()

    def test_template_var_not_found(self):

        # Undefined context fine if not put through filter...
        self.write_file("templates/default.html", "{{ blah }}")
        self.write_file("content/index.md", "---\n---")
        self.generate()
        self.assertFileContents("build/index.html", "")

        # ...but errors when testing attributes
        self.write_file("templates/default.html", "{{ blah.foo }}")
        with self.assertRaises(clearice.exceptions.TemplateError):
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
        with self.assertRaises(clearice.exceptions.FrontmatterError):
            self.generate()

        # Date in frontmatter as string is fine
        self.write_file("templates/default.html",
                "{{ date }}, {{ slug }}")
        self.write_file("content/blog/post.md", '---\ndate: "2000-01-38"\n---')
        self.generate()
        self.assertFileContents("build/blog/post/index.html",
                "2000-01-38, post")
