
from setuptools import setup, find_packages
from codecs import open
from os import path
import sys

here = path.abspath(path.dirname(__file__))

try:
    import pypandoc
    long_description = pypandoc.convert_file('README.md', 'rst')
except ImportError:
    if 'upload' in sys.argv[1:]:
        print('Package "pypandoc" required to upload.')
        raise
    long_description = open('README.md').read()

setup(
    name="clearice",
    version="0.1",
    description="Static site generator that is both simple and flexible.",
    long_description=long_description,
    url="https://github.com/mbrown1413/ClearIce",
    author="Michael S. Brown",
    author_email="michael@msbrown.net",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Console",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.5",
        "Topic :: Internet :: WWW/HTTP",
        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
    ],
    keywords=["generator", "static website", "html"],
    packages=["clearice"],
    license="LICENSE.txt",
    install_requires=[
        "pyyaml",
        "markdown",
        "click",
    ],
    entry_points={
        "console_scripts": [
            "clearice=clearice.cli:main",
        ],
    },
)
