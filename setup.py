
from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name="clearice",
    version="0.1",
    description="Static site generator that is both simple and flexible.",
    long_description=long_description,
    #url="",  #TODO
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
    test_suite="test",
    license="LICENSE.txt",
    install_requires=[
        "Flask",
        "Frozen-Flask",
        "pyyaml",
        "markdown",
    ],
    entry_points={
        "console_scripts": [
            "clearice=clearice.cli:main",
        ],
    },
)
