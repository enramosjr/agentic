"""History dependency traversal components; no native acceptance is modeled."""
import backend_test_support
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from registry import trial_reference
from trusted_ci_policy import Refusal
import trial_case


class HistoryWalkContracts(unittest.TestCase):
    def fixture(self):
        history=[]; documents={}; refs={}; visits=[]
        record=dict(task_id='a'*32)
        for index,name in enumerate(trial_case.CASE_CHAIN[:13]):
            candidate=dict(name=name)
            if name in ('bad-acceptance','replaced-checks','forged-records'):
                candidate['transition']=dict(intent=dict(phase='negative'))
            if name in ('new-head','new-base','policy-transition'):
                old=dict(revision=f'{100+index:040x}',terminal={})
                candidate['transition']=dict(intent=dict(phase='current',prior=old))
                documents[old['revision']]=dict(kind='trial-case-handoff',task_id=record['task_id'],
                    candidate=dict(name=name,transition=dict(intent=dict(phase='prior'))),history=copy.deepcopy(history),worker={},
                    execution=dict(publication_revision=f'{1100+index:040x}'),launch=dict(revision=f'{2100+index:040x}'))
            entry=dict(revision=f'{index+1:040x}',terminal={})
            documents[entry['revision']]=dict(kind='trial-case-handoff',task_id=record['task_id'],candidate=candidate,
                history=copy.deepcopy(history),worker={},execution=dict(publication_revision=f'{1000+index:040x}'),
                launch=dict(revision=f'{2000+index:040x}'))
            history.append(entry)
        for revision,value in documents.items():
            refs[trial_reference(value)]=revision
            refs[trial_reference(dict(value,execution=None))]=value['execution']['publication_revision']
            refs[trial_reference(dict(value,kind='trial-case-ready',execution=None))]=value['launch']['revision']
        def blob(revision,path):
            visits.append(revision)
            return copy.deepcopy(documents[revision]),None
        return SimpleNamespace(blob=blob,ref=lambda name:refs[name]),record,history,documents,refs,visits

    def test_each_current_and_prior_node_is_validated_once_per_guard_call(self):
        original,record,history,documents,refs,visits=self.fixture()
        source=object()
        with patch.object(__import__('trial_mutation'),'authenticate',return_value=(dict(preview=dict(baseline={})),None)),\
             patch.object(__import__('trial_mutation'),'validate',return_value={}) as validate:
            trial_case.history_guard(original,record,history,lambda:100,None,source)
            self.assertEqual(len(visits),len(documents))
            self.assertEqual(validate.call_count,3)
            visits.clear(); validate.reset_mock()
            trial_case.history_guard(original,record,history,lambda:100,None,source)
            self.assertEqual(len(visits),len(documents),'a later guard must reread every dependency')
            self.assertEqual(validate.call_count,3)

    def test_substituted_nested_prior_and_later_pointer_changes_refuse(self):
        for fault in ('name','prefix','current-prior','pointer'):
            original,record,history,documents,refs,visits=self.fixture()
            prior=documents[f'{111:040x}']
            if fault=='name': prior['candidate']['name']='new-head'
            if fault=='prefix': prior['history']=[]
            if fault=='current-prior': prior['candidate']['transition']['intent']=dict(phase='current',prior=history[11])
            if fault=='pointer': refs[trial_reference(prior)]='f'*40
            with self.subTest(fault=fault),patch.object(__import__('trial_mutation'),'authenticate',return_value=(dict(preview=dict(baseline={})),None)),\
                 patch.object(__import__('trial_mutation'),'validate',return_value={}),self.assertRaises(Refusal):
                trial_case.history_guard(original,record,history,lambda:100,None,object())
