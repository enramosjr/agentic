"""Bounded private wire encoding; no trial or external effects."""
import backend_test_support
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch
import zlib

from authority_private import MAX_STATE
from test_authority_trial_storage import Journal
from trusted_ci_policy import Refusal
import trial_wire


class WireContracts(unittest.TestCase):
    def fixture(self):
        raw=Journal(); raw.root=Path('/private/wire')
        return raw,trial_wire.WireJournal(raw,'native-broker-context')

    def encoded(self):
        raw,wire=self.fixture(); value=dict(phase='acquired',data='abc\u2603'*50000)
        document=wire.write(None,value)
        return raw,wire,value,document

    def test_plain_large_and_small_transitions_preserve_values_and_physical_cas(self):
        raw,wire=self.fixture(); value=dict(phase='initial',items=[1,True,None,'\u2603'])
        first=wire.write(None,value); self.assertEqual(raw.read()['value'],value)
        physical=raw.read(); large=dict(phase='acquired',data='x'*200000)
        with patch.object(raw,'write',wraps=raw.write) as write:
            second=wire.write(first,large)
        self.assertEqual(write.call_args.args[0],physical)
        self.assertEqual(raw.read()['value']['kind'],trial_wire.KIND)
        self.assertEqual(second['value'],large); self.assertEqual(wire.read(),second)
        self.assertLessEqual(len(json.dumps(raw.read()).encode()),MAX_STATE)
        third=wire.write(second,value); self.assertEqual(raw.read()['value'],value)
        self.assertEqual(third['value'],value)

    def test_exact_physical_threshold_and_bounded_inflation_call(self):
        raw,wire=self.fixture()
        count=MAX_STATE-trial_wire.wire_size(1,dict(data=''))
        first=wire.write(None,dict(data='x'*count))
        self.assertNotEqual(raw.read()['value'].get('kind'),trial_wire.KIND)
        self.assertEqual(trial_wire.wire_size(1,raw.read()['value']),MAX_STATE)
        wire.write(first,dict(data='x'*(count+1)))
        physical=raw.read(); value=copy.deepcopy(physical['value'])
        value.update(generation=physical['generation']+1,logical_bytes=2)
        raw.write(physical,value)
        real=zlib.decompressobj; limits=[]
        class Decoder:
            def __init__(self): self.decoder=real()
            def decompress(self,data,max_length=0):
                limits.append(max_length)
                return self.decoder.decompress(data,max_length)
            def flush(self,*args): raise AssertionError('unbounded flush')
            def __getattr__(self,name): return getattr(self.decoder,name)
        with patch.object(trial_wire.zlib,'decompressobj',Decoder),self.assertRaises(Refusal): wire.read()
        self.assertEqual(limits,[3])

    def test_malformed_headers_and_purpose_or_root_substitution_refuse(self):
        for key,replacement in (('version',2),('version',True),('codec','gzip'),('purpose','positive-finalize'),
                ('root_digest','0'*64),('logical_digest','0'*64),('compressed_digest','0'*64),
                ('generation',999),('logical_bytes',trial_wire.MAX_LOGICAL+1),('data','invalid!')):
            raw,wire,_,_=self.encoded(); physical=raw.read(); value=copy.deepcopy(physical['value'])
            value['generation']=physical['generation']+1; value[key]=replacement
            raw.write(physical,value)
            with self.subTest(key=key,replacement=replacement),self.assertRaises(Refusal): wire.read()
        raw,wire,_,_=self.encoded()
        with self.assertRaises(Refusal): trial_wire.WireJournal(raw,'positive-finalize').read()
        raw.root=raw.root/'different'
        with self.assertRaises(Refusal): wire.read()

    def test_trailing_multistream_bad_json_and_inflation_overrun_refuse_without_flush(self):
        for fault in ('trailing','multistream','json','bomb'):
            raw,wire,_,_=self.encoded(); physical=raw.read(); value=copy.deepcopy(physical['value'])
            packed=base64.b64decode(value['data'])
            if fault=='trailing': packed+=b'trailing'
            if fault=='multistream': packed+=zlib.compress(b'{}')
            if fault=='json':
                logical=b'{"bad":NaN}'; packed=zlib.compress(logical)
                value.update(logical_bytes=len(logical),logical_digest=hashlib.sha256(logical).hexdigest())
            if fault=='bomb':
                packed=zlib.compress(b'x'*100000); value.update(logical_bytes=2,logical_digest=hashlib.sha256(b'{}').hexdigest())
            value.update(data=base64.b64encode(packed).decode(),compressed_digest=hashlib.sha256(packed).hexdigest(),generation=physical['generation']+1)
            raw.write(physical,value)
            with self.subTest(fault=fault),self.assertRaises(Refusal): wire.read()

    def test_reserved_kind_incompressible_and_nonfinite_values_refuse_before_write(self):
        raw,wire=self.fixture(); first=wire.write(None,dict(ok=True))
        noise=base64.b64encode(random.Random(1).randbytes(160000)).decode()
        for value in (dict(kind=trial_wire.KIND),dict(data=noise),dict(data=float('nan'))):
            with self.assertRaises(Refusal): wire.write(first,value)
            self.assertEqual(wire.read(),first)

    def test_unknown_ack_propagates_once_and_cas_conflict_never_rebases(self):
        raw,wire,value,first=self.encoded(); write=raw.write; calls=[]
        def unknown(expected,state):
            calls.append(True); write(expected,state); raise OSError('unknown ACK')
        with patch.object(raw,'write',side_effect=unknown),self.assertRaises(OSError): wire.write(first,dict(value,phase='next'))
        self.assertEqual(len(calls),1)
        before=wire.read(); physical=raw.read()
        def racing(expected,state):
            write(expected,dict(winner=True)); return write(expected,state)
        with patch.object(raw,'write',side_effect=racing),self.assertRaises(Refusal): wire.write(before,dict(value,phase='loser'))
        self.assertEqual(raw.read()['value'],dict(winner=True))

    def test_oversized_declaration_refuses_before_inflation_and_midread_root_change_refuses(self):
        raw,wire,_,_=self.encoded(); physical=raw.read(); value=copy.deepcopy(physical['value'])
        value.update(generation=physical['generation']+1,logical_bytes=trial_wire.MAX_LOGICAL+1)
        raw.write(physical,value)
        with patch.object(trial_wire.zlib,'decompressobj',side_effect=AssertionError('inflation started')),self.assertRaises(Refusal): wire.read()
        raw,wire,_,_=self.encoded(); physical=raw.read(); load=trial_wire.loads; changed=[]
        def moving(data):
            decoded=load(data)
            if not changed:
                raw.write(physical,dict(changed=True)); changed.append(True)
            return decoded
        with patch.object(trial_wire,'loads',side_effect=moving),self.assertRaises(Refusal): wire.read()
        self.assertTrue(changed)

    def test_native_dispatch_is_restricted_to_approved_wire_sites(self):
        from types import SimpleNamespace
        import trial_storage
        journals={}
        def factory(path): return journals.setdefault(str(path),Journal())
        c=SimpleNamespace(root=Path('/private/dispatch'),store=factory)
        trial_storage.install(c)
        self.assertIsInstance(c.store(c.root/'trial-broker-context'),trial_wire.WireJournal)
        self.assertIsInstance(c.store(c.root/('trial-component-'+'a'*64)),trial_wire.WireJournal)
        for name in ('trial','trial-snapshot-'+'a'*64,'trial-component-invalid','unrelated'):
            self.assertNotIsInstance(c.store(c.root/name),trial_wire.WireJournal)


@unittest.skipUnless(os.name=='posix','actual Linux protected Store')
class ProtectedWireContracts(WireContracts):
    def fixture(self):
        from authority_private import Store
        folder=tempfile.TemporaryDirectory(prefix='native-wire-'); self.addCleanup(folder.cleanup)
        raw=Store(Path(folder.name)/'record')
        return raw,trial_wire.WireJournal(raw,'native-broker-context')
