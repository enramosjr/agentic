"""Fresh-trial private controller snapshots; references are never authority."""
import copy
import os
import re
from pathlib import Path

from trusted_ci_policy import digest, object_fields, positive, require


FIELDS=('kind version namespace_digest journal_kind case_name case_phase source_generation snapshot_digest').split()
COMPONENTS=('candidate','certificate','transition_ownership','terminal')
COMPONENT_FIELDS=('kind version namespace_digest journal field created_generation value_digest component_digest').split()
CONTEXTS=('new-base','policy-transition')


def install(c):
    """Select the finite controller codec after native setup, never generic JSON."""
    if getattr(c,'_controller_storage_installed',False): return
    from trial_controller import CASE_CHAIN,case_journal
    keys={case_journal('trial-controller',dict(name=name)) for name in CASE_CHAIN}
    keys.update('trial-controller-'+name+'-prior' for name in ('new-head','new-base','policy-transition'))
    publications={key.replace('trial-controller','trial-case-publication',1):key for key in keys}
    factory=c.store
    def store(path):
        path=Path(path); journal=factory(path)
        if path.parent==c.root:
            if path.name in keys: return ControllerJournal(c,path.name,journal)
            if path.name in publications: return PublicationJournal(c,publications[path.name],journal)
            if path.name in ('trial-context-new-base','trial-context-policy-transition'):
                return ContextJournal(c,path.name.removeprefix('trial-context-'),journal)
            if path.name=='trial-broker-context' or re.fullmatch('trial-component-[0-9a-f]{64}',path.name):
                from trial_wire import WireJournal
                return WireJournal(journal,'native-broker-context' if path.name=='trial-broker-context' else 'native-controller-component',path)
        return journal
    c.store=store
    c._controller_storage_installed=True


class ControllerJournal:
    """Four immediate domain fields; expected CAS and ACK remain physical."""
    def __init__(self,c,key,journal):
        self.c,self.key,self.raw=c,key,journal
        self.root=getattr(journal,'root',c.root/key)

    def component(self,reference,field,generation,ns):
        object_fields(reference,COMPONENT_FIELDS,'private controller component reference')
        require(reference['kind']=='native-private-controller-component-reference' and
                type(reference['version']) is int and reference['version']==1 and
                reference['namespace_digest']==ns and reference['journal']==self.key and reference['field']==field and
                positive(reference['created_generation']) and reference['created_generation']<=generation and
                all(isinstance(reference[k],str) and re.fullmatch('[0-9a-f]{64}',reference[k])
                    for k in ('value_digest','component_digest')),'private controller component identity differs')
        retained=self.c.store(self.c.root/('trial-component-'+reference['component_digest'])).read()
        require(retained is not None and retained['generation']==1,'immutable controller component missing or changed')
        value=retained['value']
        object_fields(value,('kind version namespace_digest journal field created_generation value').split(),'private controller component')
        require(value['kind']=='native-private-controller-component' and type(value['version']) is int and value['version']==1 and
                all(value[k]==reference[k] for k in ('namespace_digest','journal','field','created_generation')) and
                digest(value)==reference['component_digest'] and digest(value['value'])==reference['value_digest'] and
                isinstance(value['value'],dict),'private controller component substituted')
        return copy.deepcopy(value['value'])

    def decode(self,document):
        require(isinstance(document,dict) and positive(document.get('generation')) and
                isinstance(document.get('value'),dict),'physical controller root required')
        result=copy.deepcopy(document); value=result['value']; ns=namespace(self.c)
        require(type(value.get('storage_version')) is int and value['storage_version']==2 and
                all(field in value for field in COMPONENTS),'version-2 component controller required')
        for field in COMPONENTS:
            reference=value[field]
            value[field]=None if reference is None else self.component(reference,field,document['generation'],ns)
        if value['transition_ownership'] is None: value.pop('transition_ownership')
        require(namespace(self.c)==ns,'controller namespace changed during component reads')
        return result
    def read(self):
        document=self.raw.read()
        if document is None: return None
        result=self.decode(document)
        require(self.raw.read()==document,'controller changed during component reads')
        return result

    def physical(self,expected):
        document=self.raw.read()
        require(document is not None and self.decode(document)==expected,'physical controller root differs')
        require(self.raw.read()==document,'physical controller changed during readback')
        return document

    def write(self,expected,value):
        physical=self.raw.read()
        old=None if physical is None else self.decode(physical)
        require(old==expected,'private controller changed; do not repeat an exchange')
        generation=1 if physical is None else physical['generation']+1
        ns=namespace(self.c); normalized=copy.deepcopy(value)
        for field in COMPONENTS:
            item=value.get(field)
            if item is None:
                normalized[field]=None
            elif old is not None and old['value'].get(field)==item:
                # Only this authenticated expected root supplies reusable refs.
                normalized[field]=copy.deepcopy(physical['value'][field])
            else:
                require(isinstance(item,dict),'controller component object required')
                payload=dict(kind='native-private-controller-component',version=1,namespace_digest=ns,
                    journal=self.key,field=field,created_generation=generation,value=copy.deepcopy(item))
                reference=dict(kind='native-private-controller-component-reference',version=1,namespace_digest=ns,
                    journal=self.key,field=field,created_generation=generation,value_digest=digest(item),component_digest=digest(payload))
                component=self.c.store(self.c.root/('trial-component-'+reference['component_digest']))
                require(component.read() is None,'uncommitted controller component cannot acknowledge a new write')
                retained=component.write(None,payload)
                require(retained['generation']==1 and retained['value']==payload and component.read()==retained,
                        'controller component acknowledgement changed')
                normalized[field]=reference
        require(namespace(self.c)==ns and self.raw.read()==physical,'controller ownership changed before root CAS')
        written=self.raw.write(physical,normalized)
        result=self.decode(written)
        require(self.raw.read()==written,'controller changed after root persistence acknowledgement')
        return result


class PublicationJournal:
    """Private Case echo reuses two committed controller refs; public Case is full."""
    def __init__(self,c,controller,journal):
        self.c,self.controller,self.raw=c,controller,journal

    def project(self,document,encode=False):
        result=copy.deepcopy(document); initial=result['value'].get('initial')
        require(isinstance(initial,dict) and initial.get('kind')=='trial-case-handoff' and
                all(field in initial for field in ('candidate','certificate')),'exact private Case echo required')
        ns=namespace(self.c); controller=self.c.store(self.c.root/self.controller)
        source=controller.raw.read()
        require(source is not None and source['value'].get('kind')=='native-trial-controller' and
                type(source['value'].get('storage_version')) is int and source['value']['storage_version']==2,
                'owned Case echo controller required')
        for field in ('candidate','certificate'):
            reference=source['value'][field]
            if initial[field] is None:
                require(reference is None,'Case echo null differs from owned controller')
                continue
            value=controller.component(reference,field,source['generation'],ns)
            if encode:
                require(value==initial[field],'Case echo differs from owned controller component')
                initial[field]=copy.deepcopy(reference)
            else:
                require(initial[field]==reference,'Case echo component reference changed')
                initial[field]=value
        require(controller.raw.read()==source and namespace(self.c)==ns,'Case echo controller changed during component reads')
        return result,controller,source,ns

    def read(self):
        physical=self.raw.read()
        if physical is None: return None
        result=self.project(physical)[0]
        require(self.raw.read()==physical,'Case echo root changed during component reads')
        return result

    def write(self,expected,value):
        physical=self.raw.read()
        require((None if physical is None else self.project(physical)[0])==expected,
                'private Case echo changed; do not repeat an exchange')
        projected,controller,source,ns=self.project(dict(generation=1 if physical is None else physical['generation']+1,value=value),encode=True)
        acknowledged(self.c,self.controller,controller,controller.read())
        require(self.raw.read()==physical and controller.raw.read()==source and namespace(self.c)==ns,
                'Case echo ownership changed before root CAS')
        written=self.raw.write(physical,projected['value'])
        result=self.project(written)[0]
        require(self.raw.read()==written,'Case echo changed after persistence acknowledgement')
        return result


class ContextJournal(PublicationJournal):
    """Two context journals reuse immutable historical owner inputs, not authority."""
    FIELDS=('record','workflow','candidates','provisioning')

    def __init__(self,c,name,journal):
        super().__init__(c,'trial-controller-'+name+'-prior',journal)
        self.name=name

    def project(self,document,encode=False):
        result=copy.deepcopy(document); value=result['value']; ns=namespace(self.c)
        require(value.get('name')==self.name,'native context echo name differs')
        controller=self.c.store(self.c.root/self.controller); source=controller.raw.read()
        require(source is not None and source['value'].get('kind')=='native-trial-controller' and
                type(source['value'].get('storage_version')) is int and source['value']['storage_version']==2 and
                source['value'].get('phase')=='terminal' and source['value'].get('name')==self.name,
                'exact closed historical context owner required')
        candidate=controller.component(source['value']['candidate'],'candidate',source['generation'],ns)
        from trial_transition import historical
        require(candidate.get('name')==self.name and historical(candidate),'context echo requires the historical owner')
        pin=dict(kind='native-private-context-source',version=1,namespace_digest=ns,journal=self.controller,
                 generation=source['generation'],digest=digest(source))
        if encode:
            require('_context_source' not in value and all(value.get(field)==source['value'][field] for field in self.FIELDS),
                    'native context echo differs from historical owner')
            for field in self.FIELDS: value.pop(field)
            value['_context_source']=pin
        else:
            require(value.pop('_context_source',None)==pin and all(field not in value for field in self.FIELDS),
                    'native context source pin differs')
            value.update({field:copy.deepcopy(source['value'][field]) for field in self.FIELDS})
        require(controller.raw.read()==source and namespace(self.c)==ns,'context owner changed during source reads')
        return result,controller,source,ns

    def physical(self,expected):
        physical=self.raw.read()
        require(physical is not None and self.project(physical)[0]==expected and self.raw.read()==physical,
                'physical context root changed during readback')
        return physical

    def write(self,expected,value):
        physical=self.raw.read()
        require((None if physical is None else self.project(physical)[0])==expected,
                'private context changed; do not repeat an exchange')
        projected,controller,source,ns=self.project(dict(generation=1 if physical is None else physical['generation']+1,value=value),encode=True)
        # Cleanup still uses its original authentication and can remove privilege
        # in a fresh process; this closed source is not an active-controller ACK.
        require(self.raw.read()==physical and controller.raw.read()==source and namespace(self.c)==ns,
                'context ownership changed before root CAS')
        written=self.raw.write(physical,projected['value']); result=self.project(written)[0]
        require(self.raw.read()==written,'context changed after persistence acknowledgement')
        return result


def _ack(c,key,journal,document):
    physical=journal.physical(document) if isinstance(journal,ControllerJournal) else document
    return (os.getpid(),namespace(c),str(getattr(journal,'root',c.root/key)),
            physical['generation'],digest(physical))


def write_controller(c,key,journal,expected,value):
    """ACK bookkeeping is process-local, never a substitute for fresh guards."""
    acknowledgements=getattr(c,'_controller_acknowledgements',None)
    if acknowledgements is None:
        acknowledgements={}; c._controller_acknowledgements=acknowledgements
    failed=getattr(c,'_controller_unacknowledged',None)
    if failed is None:
        failed=set(); c._controller_unacknowledged=failed
    require(key not in failed,'controller write acknowledgement unavailable; preserve hold')
    acknowledgements.pop(key,None); failed.add(key)
    document=journal.write(expected,value)
    require(journal.read()==document,'controller changed before persistence acknowledgement retention')
    acknowledgements[key]=_ack(c,key,journal,document)
    failed.remove(key)
    return document


def acknowledged(c,key,journal,document):
    require(document is not None and getattr(c,'_controller_acknowledgements',{}).get(key)==_ack(c,key,journal,document) and
            journal.read()==document,'active controller acknowledgement unavailable; preserve hold and start a fresh trial')


def namespace(c):
    value=c.document['value']
    require(value.get('storage_version')==2 and type(value.get('storage_version')) is int and
            isinstance(value.get('storage_id'),str) and re.fullmatch('[0-9a-f]{32}',value['storage_id']),
            'fresh version-2 trial storage required; retained trials remain held')
    require(c.store(c.root/'trial').read()==c.document,'trial snapshot namespace ownership changed')
    return digest(dict(kind='native-private-snapshot-namespace-v1',owner=c.session.owner,
                       scope=c.session.scope,trial=value['storage_id'],preview=value['preview']))


def _identity(key,document):
    from trial_controller import CASE_CHAIN, case_journal
    require(isinstance(document,dict) and positive(document.get('generation')) and
            isinstance(document.get('value'),dict),'complete controller snapshot required')
    value=document['value']
    if key in tuple('trial-context-'+name for name in CONTEXTS):
        from trial_transition import _context_completion
        from trusted_ci_policy import sha
        completion=value.get('completion')
        require(value.get('name')==key.removeprefix('trial-context-') and value.get('phase')=='complete' and
                isinstance(completion,dict) and completion.get('kind')=='native-trial-context-complete' and
                sha(completion.get('revision')),'exact completed context snapshot required')
        _context_completion(value)
        return value
    require(value.get('storage_version')==2 and type(value.get('storage_version')) is int and
            value.get('kind')=='native-trial-controller' and value.get('name') in CASE_CHAIN and
            value.get('phase')=='terminal' and isinstance(value.get('candidate'),dict) and
            value['candidate'].get('name')==value['name'] and
            key==case_journal('trial-controller',value['candidate']),'exact terminal controller snapshot required')
    require(isinstance(value.get('history'),list) and len(value['history'])==CASE_CHAIN.index(value['name']),
            'terminal controller history length differs')
    if value['history']:
        _reference(value.get('previous'))
        require(value['previous']['journal_kind']=='trial-controller','context snapshots cannot be controller predecessors')
    return value


def _reference(reference):
    from trial_controller import CASE_CHAIN
    object_fields(reference,FIELDS,'private controller snapshot reference')
    require(reference['kind']=='native-private-snapshot-reference' and type(reference['version']) is int and
            reference['version']==1 and
            ((reference['journal_kind']=='trial-controller' and reference['case_name'] in CASE_CHAIN and
              reference['case_phase'] in ('current','prior')) or
             (reference['journal_kind']=='trial-context' and reference['case_name'] in CONTEXTS and reference['case_phase']=='complete')) and
            positive(reference['source_generation']) and all(isinstance(reference[k],str) and
            re.fullmatch('[0-9a-f]{64}',reference[k]) for k in ('namespace_digest','snapshot_digest')),
            'invalid private controller snapshot reference')
    require(reference['case_phase']!='prior' or reference['case_name'] in ('new-head','new-base','policy-transition'),
            'unexpected historical controller reference')


def _key(reference):
    from trial_controller import case_journal
    if reference['journal_kind']=='trial-context': return 'trial-context-'+reference['case_name']
    candidate=dict(name=reference['case_name'])
    if reference['case_phase']=='prior': candidate['transition']=dict(intent=dict(phase='prior'))
    return case_journal('trial-controller',candidate)


def _snapshot(c,key,document):
    value=_identity(key,document)
    from trial_transition import historical
    journal=c.store(c.root/key)
    context=isinstance(journal,ContextJournal)
    require(context==(key in tuple('trial-context-'+name for name in CONTEXTS)),
            'actual bounded snapshot source required')
    physical=journal.physical(document) if isinstance(journal,(ControllerJournal,ContextJournal)) else document
    source=dict(kind='native-private-context-snapshot' if context else 'native-private-controller-snapshot',version=1,namespace_digest=namespace(c),
                source_journal=key,source_generation=document['generation'],document=copy.deepcopy(physical))
    reference=dict(kind='native-private-snapshot-reference',version=1,namespace_digest=source['namespace_digest'],
        journal_kind='trial-context' if context else 'trial-controller',case_name=value['name'],
        case_phase='complete' if context else 'prior' if historical(value['candidate']) else 'current',
        source_generation=document['generation'],snapshot_digest=digest(source))
    return source,reference


def pin(c,key,document):
    """Acknowledge dependencies before the caller's existing root CAS; no retry."""
    source,reference=_snapshot(c,key,document)
    require(c.store(c.root/key).read()==document,'live controller changed before archive')
    journal=c.store(c.root/('trial-snapshot-'+reference['snapshot_digest']))
    require(journal.read() is None,'existing uncommitted controller archive cannot acknowledge a new pin')
    retained=journal.write(None,source)  # Unknown acknowledgement propagates; never read back to adopt it.
    require(retained['generation']==1 and retained['value']==source,'immutable controller archive changed')
    require(journal.read()==retained and c.store(c.root/key).read()==document,
            'controller archive or live source changed during pin')
    return reference


def resolve(c,reference):
    """Fresh protected reads on every call; no cache and no prefix expansion."""
    _reference(reference)
    require(reference['namespace_digest']==namespace(c),'private snapshot namespace differs')
    key=_key(reference)
    archived=c.store(c.root/('trial-snapshot-'+reference['snapshot_digest'])).read()
    require(archived is not None and archived['generation']==1,'immutable controller archive missing or changed')
    source=archived['value']
    object_fields(source,('kind version namespace_digest source_journal source_generation document').split(),'private controller archive')
    kind='native-private-context-snapshot' if reference['journal_kind']=='trial-context' else 'native-private-controller-snapshot'
    require(source['kind']==kind and type(source['version']) is int and source['version']==1 and
            source['namespace_digest']==reference['namespace_digest'] and source['source_journal']==key and
            source['source_generation']==reference['source_generation'] and digest(source)==reference['snapshot_digest'],
            'private controller archive substituted')
    physical=source['document']; journal=c.store(c.root/key)
    require((reference['journal_kind']=='trial-context')==isinstance(journal,ContextJournal),
            'snapshot source journal kind differs')
    live=journal.raw.read() if isinstance(journal,(ControllerJournal,ContextJournal)) else journal.read()
    require(physical['generation']==reference['source_generation'] and live==physical,
            'live archived controller changed')
    document=journal.decode(physical) if isinstance(journal,ControllerJournal) else journal.project(physical)[0] if isinstance(journal,ContextJournal) else physical
    _identity(key,document)
    require((journal.raw.read() if isinstance(journal,(ControllerJournal,ContextJournal)) else journal.read())==physical,
            'live archived controller changed during component reads')
    return document


def predecessors(c,value):
    from trial_controller import CASE_CHAIN
    require(value.get('storage_version')==2 and type(value.get('storage_version')) is int and
            isinstance(value.get('history'),list) and len(value['history'])<len(CASE_CHAIN),
            'version-2 bounded controller history required')
    current=value; seen=set()
    for index in reversed(range(len(value['history']))):
        reference=current.get('previous'); _reference(reference)
        identity=(reference['case_name'],reference['case_phase'])
        require(reference['journal_kind']=='trial-controller' and identity==(CASE_CHAIN[index],'current') and
                identity not in seen,'unexpected private controller predecessor')
        seen.add(identity)
        previous=resolve(c,reference)
        require(previous['value']['history']==value['history'][:index],'private controller history prefix changed')
        yield previous
        current=previous['value']
    require('previous' not in current,'unexpected private controller ancestor')


def ownership(c,documents,create=False):
    """Pin controllers and the two complete contexts; other ownership stays inline."""
    result=copy.deepcopy(documents)
    for key,document in documents.items():
        if key.startswith('trial-controller') or key in tuple('trial-context-'+name for name in CONTEXTS):
            if create: result[key]=pin(c,key,document)
            else:
                _,reference=_snapshot(c,key,document)
                require(resolve(c,reference)==document,'owned controller archive changed')
                result[key]=reference
    return result
