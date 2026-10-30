"""Run a nonempty selected unittest suite from one declared sealed test file."""
from pathlib import Path
import sys
import unittest

path = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(path.parent))
sys.path.insert(0, str(path.parents[1]))
suite = unittest.defaultTestLoader.discover(str(path.parent), pattern=path.name)
if len(sys.argv) > 2:
    selected = sys.argv[2]
    def cases(value):
        for test in value:
            if isinstance(test, unittest.TestSuite):
                yield from cases(test)
            elif selected in test.id():
                yield test
    suite = unittest.TestSuite(cases(suite))
if suite.countTestCases() == 0:
    raise SystemExit('empty sealed acceptance suite')
raise SystemExit(0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1)
