"""Actual worker build-context export, without an engine, image build or model."""
import backend_test_support
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_authority_codex_harness import configured
from trusted_ci_policy import Refusal
import build_coding


class CodingBundleContracts(unittest.TestCase):
    def test_exact_context_closure_and_extracted_worker_hold(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / 'codex'
            binary.write_bytes(b'\x7fELFsynthetic-context-only-binary')
            d = configured()
            d['resources']['codex_sha'] = hashlib.sha256(binary.read_bytes()).hexdigest()
            destination = root / 'context'
            document = root / 'deployment.json'
            document.write_text(json.dumps(d))
            invoked = subprocess.run([sys.executable, '-I', str(Path(build_coding.__file__)), '--deployment', str(document),
                '--binary', str(binary), '--output', str(destination)], cwd=root, capture_output=True, timeout=15)
            self.assertEqual(invoked.returncode, 0, invoked.stderr)
            result = json.loads(invoked.stdout)
            self.assertFalse(result['image_built'])
            self.assertFalse(result['enforcement_active'])
            manifest = json.loads((destination / 'coding-manifest.json').read_bytes())
            self.assertEqual(manifest['base_image'], d['policy']['image'])
            self.assertEqual(manifest['codex_sha256'], d['resources']['codex_sha'])
            for name, fingerprint in manifest['files'].items():
                self.assertEqual(hashlib.sha256((destination / name).read_bytes()).hexdigest(), fingerprint)
            self.assertFalse(any('test_' in name or 'private-setup' in name or '.git/' in name for name in manifest['files']))
            held = subprocess.run([sys.executable, '-I', str(destination / 'deploy/authority/coding_stdio.py'), '--stdio'],
                cwd=root, input=b'not a bootstrap', capture_output=True, timeout=15)
            self.assertEqual(held.returncode, 1)
            self.assertIn(b'refused', held.stderr)
            self.assertNotIn(b'Traceback', held.stderr)
            with self.assertRaises(Refusal): build_coding.build(backend_test_support.ROOT, d, binary, destination)

    def test_bad_binary_pin_fails_before_creating_context(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / 'codex'
            binary.write_bytes(b'\x7fELFwrong binary')
            with self.assertRaises(Refusal):
                build_coding.build(backend_test_support.ROOT, configured(), binary, root / 'context')
            self.assertFalse((root / 'context').exists())

    def test_recipe_copies_only_the_explicit_software_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            binary = root / 'codex'
            binary.write_bytes(b'\x7fELFcontext-only fixture')
            d = configured()
            d['resources']['codex_sha'] = hashlib.sha256(binary.read_bytes()).hexdigest()
            destination = root / 'context'
            build_coding.build(backend_test_support.ROOT, d, binary, destination)
            (destination / '.env').write_text('unlisted fixture must not be copied')
            copies = [(json.loads(line[5:])) for line in (destination / 'Containerfile').read_text().splitlines()
                      if line.startswith('COPY ')]
            self.assertEqual({source for source, _ in copies}, set(build_coding.FILES) | {'bin/codex', 'coding-manifest.json'})
            self.assertTrue(all(target == '/opt/agentic/' + source for source, target in copies))


if __name__ == '__main__': unittest.main()
