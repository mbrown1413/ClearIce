
import unittest
from setuptools.command.test import ScanningLoader

try:
    import coverage
except ImportError:
    coverage = None
if coverage:
    cov = coverage.Coverage()
    cov.start()

unittest.main(
    module="test",
    testLoader=ScanningLoader(),
    exit=False
)

if coverage:
    cov.stop()
    cov.save()
