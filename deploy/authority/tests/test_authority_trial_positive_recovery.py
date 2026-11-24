"""One-shot positive role storage fault controls; no synthetic acceptance claim."""
import backend_test_support
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from authority_private import Store
from trusted_ci_policy import Refusal,digest
import trial_broker_positive as positive_case
import test_authority_private_setup as private_fixture


class PositiveIssuance(unittest.TestCase):
    def test_lost_ack_consumes_original_job_even_after_marker_deletion(self):
        for fault in ('upload','mint'):
            with self.subTest(fault=fault),private_fixture.PrivateSetupContracts().temporary() as folder:
                link=dict(kind=positive_case.GRANT,revision='a'*40)
                grant=dict(preview=dict(expires=500,pin=dict(workflow_sha='b'*40),roles=dict(broker='broker (7)')))
                snapshot=dict(pr=7,run_id=99,run_attempt=1)
                request=dict(operation_id='c'*32,sequence=1,snapshot=snapshot)
                job=dict(run_id=99,attempt=1,job_id=17,workflow_sha='b'*40)
                root=Path(folder)/('agentic-positive-'+digest(dict(grant=link,role='broker',operation=request['operation_id'])))
                store=Store(root)
                reserved=store.write(None,dict(phase='reserved',nonce='original-native-owner'))
                bound=dict(job=job,scratch=str(Path(folder).resolve()),reserved=reserved)
                a=SimpleNamespace(candidate=dict(name='positive'),worker=None,record=dict(task_id='d'*32),request=request,
                    binding=dict(deployment=dict(policy=dict(authority_repository='owner/authority'))),
                    clock=lambda:100,guard=lambda:None,_state=lambda:dict(),_positive=None)
                case=dict(request=request)
                artifacts=[]; uploads=[]; mints=[]
                api=SimpleNamespace(pages=lambda *args:artifacts)
                def upload(name,document):
                    uploads.append(json.loads(document)); artifacts.append(dict(name=name,id=1))
                    if fault=='upload': raise OSError('unknown upload acknowledgement')
                    return 1
                def attempt(scratch=folder):
                    positive_case.begin(a,api,dict(RUNNER_TEMP=scratch),'broker',upload)
                    mints.append(True)
                    raise OSError('unknown actual mint acknowledgement')
                with patch.object(positive_case,'original',return_value=None),patch.object(positive_case,'_case',return_value=case),\
                     patch.object(positive_case,'grant_link',return_value=link),patch.object(positive_case,'authenticate_grant',return_value=grant),\
                     patch.object(positive_case,'job_link',return_value=dict(kind=positive_case.JOB,revision='e'*40)),\
                     patch.object(positive_case,'authenticate_job',return_value=bound),patch.object(positive_case,'guard',return_value=None),\
                     patch.object(__import__('provenance'),'admit_job',return_value=dict(run_id=99,id=17,head_sha='b'*40)),\
                     patch.object(__import__('provenance'),'live_positive_issuance',side_effect=lambda *args:dict(document=uploads[-1])):
                    with self.assertRaises(OSError): attempt()
                    artifacts.clear(); a._positive=None
                    with self.assertRaisesRegex(Refusal,'missing or consumed'): attempt()
                    with private_fixture.PrivateSetupContracts().temporary() as other:
                        with self.assertRaisesRegex(Refusal,'RUNNER_TEMP changed'): attempt(other)
                    self.assertEqual(len(uploads),1)
                    self.assertEqual(len(mints),int(fault=='mint'))

    def test_historical_positive_receipts_have_no_append_capability(self):
        from merge_receipts import ActionsReceipts
        store=ActionsReceipts.__new__(ActionsReceipts)
        store.recovery=True; store.uploader=lambda *args:self.fail('historical evidence gained upload authority')
        with self.assertRaises(Refusal): store.append('dispatch',{})


if __name__=='__main__': unittest.main()
