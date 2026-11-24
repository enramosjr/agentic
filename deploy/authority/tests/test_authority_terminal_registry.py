"""Terminal-only CAS and exact lost-ack recovery, without merge authorization."""
import backend_test_support
import copy
import unittest

from test_authority_registry import RegistryHost, coordinates, intent
from trusted_ci_policy import Refusal, digest
import registry


def fixture():
    host = RegistryHost()
    store = registry.Registry(host, coordinates())
    store.write(None, intent())
    binding = store.binding()
    d = binding['deployment']
    operation = dict(kind='merge', operation_id='1' * 32, scope_digest=None,
        repository_id=d['policy']['repository_id'], target=d['policy']['target'],
        configuration_revision=binding['configuration_revision'], deployment_digest=digest(d),
        workflow_sha='a' * 40, run_id=99, attempt=1, created=1000, execution_deadline=1300,
        pr=7, head='2' * 40, base='3' * 40, merge='4' * 40)
    before = store.acquire_operation(binding['branch_head'], binding['configuration_revision'], operation)
    terminal = dict(operation_id='1' * 32, sequence=1, kind='not-submitted', receipt_digest='f' * 64)
    host.writes.clear()
    return host, store, before, terminal


class TerminalRegistryContracts(unittest.TestCase):
    def test_terminal_cleanup_survives_default_software_drift_without_repinning(self):
        host, store, before, terminal = fixture()
        host.refs['main'] = 'e' * 40
        host.commits['e' * 40] = copy.deepcopy(host.commits['a' * 40])
        after = store.finalize_operation(before['branch_head'], terminal)
        self.assertIsNone(after['fence']['pending'])
        self.assertEqual(after['deployment'], before['deployment'])
        self.assertEqual(after['configuration_revision'], before['configuration_revision'])
        self.assertEqual(after['fence']['completed'], [terminal])
        with self.assertRaises(Refusal): store.binding()

    def test_exact_lost_ack_recovers_without_second_write(self):
        host, store, before, terminal = fixture()
        host.lose_ack = True
        after = store.finalize_operation(before['branch_head'], terminal)
        self.assertEqual(after['fence']['completed'], [terminal])
        self.assertEqual(len([w for w in host.writes if w[0].endswith('/git/commits')]), 1)

    def test_matching_state_on_different_pointer_never_counts_as_our_commit(self):
        host, store, before, terminal = fixture()
        real = host.fetch
        def replace(path, **kwargs):
            result = real(path, **kwargs)
            if kwargs.get('method') == 'PATCH':
                own = host.refs['agentic-registry']
                host.commits['e' * 40] = copy.deepcopy(host.commits[own])
                host.refs['agentic-registry'] = 'e' * 40
                raise OSError('synthetic different pointer')
            return result
        host.fetch = replace
        with self.assertRaises(Refusal): store.finalize_operation(before['branch_head'], terminal)
        self.assertEqual(host.refs['agentic-registry'], 'e' * 40)


if __name__ == '__main__': unittest.main()
