"""Held producer composition; all GitHub/OCI effects are local fixtures."""
import backend_test_support
import copy
import json
import unittest
from unittest.mock import patch

import authority_release
import control_rendezvous
import service
from trusted_ci_policy import Refusal, digest
from test_authority_broker_evidence import fixture


class ProducerServiceContracts(unittest.TestCase):
    def test_production_pre_readiness_wait_keeps_120_second_budget(self):
        registry,source,api,binding,identities,snapshot,locators,clock=fixture()
        now=[binding['fence']['pending']['created']]
        class Empty:
            def pages(self,*args): return []
        with self.assertRaisesRegex(Refusal,'readiness unavailable'):
            service._wait_broker_ready(Empty(),registry,binding,lambda:now[0],lambda:None,
                                      lambda seconds:now.__setitem__(0,now[0]+seconds))
        self.assertEqual(now[0],binding['fence']['pending']['created']+120)

    def test_new_public_roles_hold_before_input_or_authentication(self):
        class Unreadable:
            @property
            def buffer(self): raise AssertionError('read before hold')
        for role in ('discover', 'prepare', 'verify', 'publication-controls', 'publish',
                     'proof', 'broker', 'controls', 'final-proof', 'finalize','case-host-denial'):
            with self.subTest(role=role), patch.object(service.sys, 'argv', ['service.py', role, 'node']), \
                 patch.object(service.sys, 'stdin', Unreadable()):
                with self.assertRaises(authority_release.Held): service.main()

    def test_publication_observation_has_own_closed_producer_and_no_broker_nonce(self):
        registry, source, api, binding, identities, snapshot, locators, clock = fixture()
        facts = dict(schema_version=2, deployment_digest=binding['deployment_digest'],
            generation=binding['deployment']['generation'], base=snapshot['base'], controls_digest='b'*64,
            owners_digest='b'*64, access_digest='c'*64, automation_digest='d'*64, coding_bot_id=18,
            isolation_established=False, enforcement_active=False,
            required_checks=[dict(context=binding['deployment']['policy']['check_name'], integration_id=42)])
        value = service._publication_observation(binding, snapshot, 1090, 1091, facts)
        proof = dict(role='publication-controls', key=snapshot['pr'], run_id=99, attempt=1,
            job_started=1089, artifact_created=1092, job_completed=1093)
        self.assertEqual(service._validate_publication_observation(value, binding, snapshot, proof, 1094), facts)
        self.assertNotIn('ready_nonce', value)
        for defect in ('role', 'attempt', 'stale', 'operation', 'base', 'cleanup'):
            changed, producer, now = copy.deepcopy(value), dict(proof), 1094
            if defect == 'role': producer['role'] = 'controls'
            if defect == 'attempt': producer['attempt'] = 2
            if defect == 'stale': now = 1391
            if defect == 'operation': changed['operation_id'] = 'f'*32
            if defect == 'base': changed['result']['base'] = 'f'*40
            if defect == 'cleanup': producer['job_completed'] = 1091
            with self.subTest(defect=defect), self.assertRaises(Refusal):
                service._validate_publication_observation(changed, binding, snapshot, producer, now)

    def test_source_borrowing_supports_existing_issuer_and_merger_domains(self):
        from test_authority_app_proofs import AppAPI, AuthorityReader
        _, _, _, b, identities, _, _, _ = fixture()
        for purpose in ('reader', 'admin', 'issuer', 'merge'):
            root = AppAPI(b['deployment'], identities, purpose)
            calls, post = [], root.post
            def mint(path, body):
                calls.append(body)
                return post(path, body)
            root.post = mint
            with service._source_token(purpose, root, AuthorityReader(), b['deployment'], identities,
                                       b['configuration_revision'], lambda:1090, token_factory=root.token_api):
                pass
            self.assertEqual(set(root.visible), set(root.revoked))
            self.assertEqual(calls[-1]['permissions']['pull_requests'], 'read')


if __name__ == '__main__': unittest.main()
