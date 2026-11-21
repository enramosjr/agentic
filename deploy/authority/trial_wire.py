"""Selected held-trial values: bounded, lossless wire encoding, never authority."""
import base64
import binascii
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import zlib

from authority_private import MAX_STATE
from trusted_ci_policy import Refusal,digest,loads,object_fields,positive,require

KIND='native-private-wire-value'
MAX_LOGICAL=16*1024*1024
PURPOSES=('native-broker-context','native-controller-component','original-context-recovery','positive-broker','positive-finalize')
FIELDS=('kind version codec purpose root_digest generation logical_bytes logical_digest compressed_digest data').split()


def canonical(value):
    try: return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode('ascii')
    except (TypeError,ValueError,RecursionError): raise Refusal('invalid private wire JSON') from None


def wire_size(generation,value):
    return len((json.dumps(dict(schema_version=1,generation=generation,value=value),sort_keys=True,allow_nan=False)+'\n').encode())


class WireJournal:
    def __init__(self,journal,purpose,root=None):
        require(purpose in PURPOSES,'unsupported private wire purpose')
        selected=getattr(journal,'root',root)
        require(selected is not None,'verified protected root required for wire encoding')
        self.raw,self.purpose,self.root=journal,purpose,Path(selected)
        self._root_identity=self.identity()

    def identity(self):
        # Store owns path/ancestor verification. Normalize its verified path;
        # never resolve links or take identity from the encoded payload.
        root=getattr(self.raw,'root',self.root)
        require(root is not None,'protected wire root identity unavailable')
        path=os.path.normcase(os.path.abspath(os.path.normpath(os.fspath(root))))
        return digest(dict(kind='native-private-wire-root-v1',path=path))

    def decode(self,document):
        require(self.identity()==self._root_identity,'protected wire root was relocated')
        require(isinstance(document,dict) and positive(document.get('generation')) and
                isinstance(document.get('value'),dict),'private wire document required')
        value=document['value']
        if value.get('kind')!=KIND: return copy.deepcopy(document)
        object_fields(value,FIELDS,'private wire envelope')
        require(type(value['version']) is int and value['version']==1 and value['codec']=='zlib' and
                value['purpose']==self.purpose and value['root_digest']==self._root_identity and
                positive(value['generation']) and value['generation']==document['generation'] and
                positive(value['logical_bytes']) and value['logical_bytes']<=MAX_LOGICAL and
                all(isinstance(value[k],str) and re.fullmatch('[0-9a-f]{64}',value[k]) for k in ('logical_digest','compressed_digest')) and
                isinstance(value['data'],str) and len(value['data'])<=MAX_STATE,'private wire binding or bounds differ')
        try: packed=base64.b64decode(value['data'],validate=True)
        except (binascii.Error,ValueError,UnicodeError): raise Refusal('invalid private wire encoding') from None
        require(hashlib.sha256(packed).hexdigest()==value['compressed_digest'],'private compressed bytes changed')
        decoder=zlib.decompressobj()
        try: logical=decoder.decompress(packed,value['logical_bytes']+1)
        except zlib.error: raise Refusal('invalid private compressed stream') from None
        # No flush: every output allocation is constrained by the retained bound.
        require(len(logical)==value['logical_bytes'] and decoder.eof and not decoder.unused_data and
                not decoder.unconsumed_tail,'private wire inflation bound or stream differs')
        require(hashlib.sha256(logical).hexdigest()==value['logical_digest'],'private logical bytes changed')
        decoded=loads(logical)
        require(isinstance(decoded,dict) and decoded.get('kind')!=KIND and canonical(decoded)==logical,
                'private logical JSON is not canonical or collides with wire encoding')
        return dict(document,value=decoded)

    def read(self):
        require(self.identity()==self._root_identity,'protected wire root was relocated')
        physical=self.raw.read()
        if physical is None: return None
        result=self.decode(physical)
        require(self.raw.read()==physical,'private wire root changed during decoding')
        return result

    def write(self,expected,value):
        require(self.identity()==self._root_identity,'protected wire root was relocated')
        require(isinstance(value,dict) and value.get('kind')!=KIND,'reserved private wire discriminator')
        physical=self.raw.read()
        require((None if physical is None else self.decode(physical))==expected,
                'private wire root changed; do not repeat an exchange')
        logical=canonical(value)
        require(len(logical)<=MAX_LOGICAL,'private logical value exceeds wire bound')
        generation=1 if physical is None else physical['generation']+1
        frozen=loads(logical)
        if wire_size(generation,frozen)<=MAX_STATE:
            encoded=frozen
        else:
            packed=zlib.compress(logical)
            encoded=dict(kind=KIND,version=1,codec='zlib',purpose=self.purpose,root_digest=self.identity(),generation=generation,
                logical_bytes=len(logical),logical_digest=hashlib.sha256(logical).hexdigest(),
                compressed_digest=hashlib.sha256(packed).hexdigest(),data=base64.b64encode(packed).decode('ascii'))
            require(wire_size(generation,encoded)<=MAX_STATE,'private encoded value exceeds wire limit; no fallback')
        written=self.raw.write(physical,encoded)  # Unknown persistence ACK propagates, without readback adoption.
        result=self.decode(written)
        require(self.raw.read()==written,'private wire root changed after persistence acknowledgement')
        return result
