"""Measured-fact validation fixtures; not live OCI isolation evidence."""
import backend_test_support
import copy
import json
import unittest

from test_authority_task_admission import fixture
from trusted_ci_policy import Refusal


class WorkerFactContracts(unittest.TestCase):
    def test_kernel_probe_and_engine_mount_readback_are_both_required(self):
        import worker_facts
        _, _, binding, _, _, receipt = fixture()
        expected = receipt['isolation']
        class Box:
            deployment = binding['deployment']
            facts = copy.deepcopy(expected)
            mounts = [dict(Type='volume', Destination='/work', RW=True),
                      dict(Type='bind', Destination='/run/agentic-model', RW=False)]
            def inspect(self):
                return dict(HostConfig=dict(Tmpfs={'/tmp':'rw', '/home/agentic':'rw'}), Mounts=self.mounts)
            def run(self, argv, cwd):
                if argv[0] == 'stat': return 0, 'ext4\n'
                self.script = argv[-1]
                return 0, json.dumps({k:v for k,v in self.facts.items() if k not in
                    ('work_filesystem', 'writable_mounts', 'host_mounts')})
        box = Box()
        self.assertEqual(worker_facts.measure(box), expected)
        self.assertIn('/proc/self/status', box.script)
        self.assertIn('/sys/fs/cgroup/memory.max', box.script)
        self.assertIn('169.254.169.254', box.script)
        for key, bad in [('uid',0), ('memory_max',1), ('cap_eff','f'*16),
                         ('credential_probes',dict(expected['credential_probes'], github_credentials='available'))]:
            box.facts = dict(copy.deepcopy(expected), **{key:bad})
            with self.subTest(key=key), self.assertRaises(Refusal): worker_facts.measure(box)
        box.facts = copy.deepcopy(expected)
        box.mounts = [*box.mounts, dict(Type='bind', Destination='/authority', RW=True)]
        with self.assertRaises(Refusal): worker_facts.measure(box)


if __name__ == '__main__': unittest.main()
