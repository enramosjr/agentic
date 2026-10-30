"""Disposable test-integrity probe: dropped cleanup writes must not pass guards."""
import importlib.util
import inspect
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / '.ai/scripts/tests'))
spec = importlib.util.spec_from_file_location('semantic_restoration_probe', root / '.ai/scripts/tests/test_assurance_inputs.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
write_bytes = Path.write_bytes


def drop_cleanup_write(path, data):
    if any(frame.function == '_callCleanup' for frame in inspect.stack()):
        return len(data)
    return write_bytes(path, data)


for cls, method in ((module.SemanticLensDependencyTests, 'test_reachable_added_dependencies_require_review'),
                    (module.SemanticLensControlTests, 'test_confirmed_broken_variants_fail_intended_criteria')):
    result = unittest.TestResult()
    with patch.object(Path, 'write_bytes', drop_cleanup_write):
        cls(method).run(result)
    assert result.testsRun == 1, result.testsRun
    assert not result.errors, result.errors
    assert result.failures, 'restoration guard accepted dropped cleanup writes: ' + cls.__name__
    assert all('2 != 1' in detail for _, detail in result.failures), result.failures
    print(cls.__name__ + ': dropped restoration writes rejected')
