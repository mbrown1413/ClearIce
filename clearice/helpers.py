
import os
from fnmatch import fnmatch

IGNORED_FILES = [".*", "*~"]

def remove_extension(filename, divider='.'):
    return filename[:filename.rfind(divider)]

def remove_suffix(s, suffix):
    assert s.endswith(suffix)
    return s[:-len(suffix)]

def remove_prefix(s, prefix):
    assert s.startswith(prefix)
    return s[len(prefix):]

def normalize_url(path):
    url = path

    # Does not remove filename extensions
    #   /blah/this.md -> /blah/this.md/

    # Removes leading .
    #   ./blah/this/ -> /blah/this/
    if url.startswith("./"):
        url = url[1:]

    # If index file, remove filename
    #  /blah/index -> /blah/
    #  /blah/index/ -> /blah/index/
    if url.endswith("/index"):
        url = url[:-5]

    # Ensures starts/ends with /
    #   blah/this -> /blah/this/
    if not url.startswith("/"):
        url = '/' + url
    if not url.endswith("/"):
        url = url + '/'

    # Exactly one '/' between each part
    while '//' in url:
        url = url.replace('//', '/')

    assert url.startswith('/') and url.endswith('/')
    return url

def fnmatch_one_of(filename, patterns):
    for pattern in patterns:
        if fnmatch(filename, pattern):
            return True
    return False

def walk_dir(root, subdir="", patterns=None):
    """Recursively lists all files the root directory.

    Args:
        root: The directory to walk.
        subdir: If not `None`, only return files the directory "root/subdir/".
            Relative paths will still be relative to `root`.
        patterns: A list of glob-style filename strings. If given, only
            filenames that match one of these patterns will be returned. Also
            accepts a single string as a shortcut for a 1-item list.

    Returns: [(abspath, relpath, filename), ...]
        abspath: Absolute path of file, via `os.path.abspath()`.
        relpath: Relative path of file from the root.
        filename: Name of the file.
    """
    root = os.path.abspath(root)
    if isinstance(patterns, str):
        patterns = [patterns]
    assert subdir is None or not subdir.startswith('/')
    for dirpath, dirnames, filenames in os.walk(os.path.join(root, subdir)):
        for filename in filenames:

            if fnmatch_one_of(filename, IGNORED_FILES):
                continue
            if patterns and not fnmatch_one_of(filename, patterns):
                continue

            abspath = os.path.join(dirpath, filename)
            relpath = remove_prefix(abspath, root)
            yield abspath, relpath
