
import unittest
try:
    import coverage
except ImportError:
    coverage = None

if coverage:
    cov = coverage.Coverage()
    cov.start()

unittest.main(module="test", exit=False)

if coverage:
    cov.stop()
    cov.save()
