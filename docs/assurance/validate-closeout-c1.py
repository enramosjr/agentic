#!/usr/bin/env python3
"""Bounded current-candidate C1 proof. R1-R6. No product code is edited."""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import traceback
import unittest

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RESULTS = HERE / 'closeout-c1-validation-results'
SPEC = 'specification-closeout-c1-validation.md'
PLAN = 'plan-closeout-c1-validation.md'
MANIFEST = 'closeout-c1-candidate.sha256'
REVIEW = 'review-operator-closeout-c1.md'
FREEZE = HERE / 'closeout-c1-operator-freeze.json'
HEAD = '02dd97586873f24a604224aa5ad186a60c4104e7'
BRANCH = 'claude/assurance-increment-7'
MANIFEST_HASH = '32affe791ca9c75523ec5780a46f7cfe30e8179f2d77e66eaff63d147003ca29'
SPEC_HASH = '4eccb9ae35f35a551d2aa051982843ad587751aa6e0ecd86090eb982544acdaa'


class ProofError(Exception):
    """A proof condition was not met; never earns mutation credit."""


def require(condition, message):
    if not condition:
        raise ProofError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_hash(path):
    require(path.is_file() and not path.is_symlink(), 'missing or linked file: ' + str(path))
    return digest(path.read_bytes())


def safe(root, name):
    path = root / name
    require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'unsafe relative path')
    require(path.resolve().is_relative_to(root.resolve()), 'path escaped root')
    for parent in (path, *path.parents):
        if parent == root.parent:
            break
        require(not parent.is_symlink(), 'linked path: ' + str(parent))
    return path


def parse_pins(text):
    pins = {}
    for line in text.splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  (\S+)', line)
        require(match is not None, 'invalid pin line')
        sha, name = match.groups()
        require(name not in pins and not Path(name).is_absolute() and '..' not in Path(name).parts,
                'duplicate or unsafe pin')
        pins[name] = sha
    require(bool(pins), 'empty pins')
    return pins


def check_files(root, pins):
    for name, sha in pins.items():
        require(file_hash(safe(root, name)) == sha, 'hash mismatch: ' + name)


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write('\n')


def publish_report(report):
    """Only the final summary is replaceable; raw process artifacts stay append-only."""
    pending = RESULTS / 'report.pending'
    write_new(pending, report)
    pending.replace(RESULTS / 'report.json')
    (RESULTS / 'report.sha256').write_text(file_hash(RESULTS / 'report.json') + '\n')


def row(number, cls, count, method, line, path, scope, old, new, terms):
    return dict(id=f'N{number:02}', module='test_lifecycle_conformance' if number == 11 else 'test_assurance',
                **{'class': cls}, count=count, method=method, line=line, path=path, scope=scope,
                old=old, new=new, terms=terms)


ROWS = [
    row(1, 'ObligationSyntaxTests', 1, 'test_valid_and_malformed_obligations', 119, 'assurance.py', '_parse',
        'if kind in found:', "if kind in found and kind != 'Verify':", ['INVALID', 'CALC-R3']),
    row(2, 'CompatibilityTests', 3, 'test_obligation_free_and_prose_capabilities_stay_green', 133,
        'assurance.py', 'evaluate', "return result(obligation, 'UNDECLARED', 'no Verify: line')",
        "return result(obligation, 'UNVERIFIED', 'no Verify: line')", ['1 != 0']),
    row(3, 'AssureRunTests', 4, 'test_run_records_req_entry_with_declared_inputs', 150,
        'lifecycle.py', 'assure_run', 'f"req:{obligation.id}"', 'f"req:BROKEN-{obligation.id}"',
        ['req:CALC-R1', 'not found', 'req:BROKEN-CALC-R1']),
    row(4, 'StatusTests', 7, 'test_fresh_evidence_is_verified', 187, 'assurance.py', 'evaluate',
        "'VERIFIED', f'passed on {scope}; covers only this command on these inputs'",
        "'UNVERIFIED', f'passed on {scope}; covers only this command on these inputs'", ['UNVERIFIED', 'VERIFIED']),
    row(5, 'RuntimeTests', 1, 'test_changed_executable_is_stale', 240, 'ledger.py', '_entry_verdict',
        "if entry.get('runtime_sha256') and runtime_digest(entry['argv']) != entry['runtime_sha256']:",
        "if False and entry.get('runtime_sha256') and runtime_digest(entry['argv']) != entry['runtime_sha256']:",
        ['VERIFIED', 'STALE']),
    row(6, 'IntegrityTests', 2, 'test_invalid_and_output_bearing_records_contribute_nothing', 258,
        'assurance.py', 'evidence.add', 'if problems:', 'if False and problems:', ['VERIFIED', 'UNVERIFIED']),
    row(7, 'UnscopedTests', 3, 'test_any_commit_makes_it_stale', 285, 'ledger.py', '_entry_verdict',
        'return False, f"{name} declared no --inputs and the working tree changed since it ran (declare --inputs to reuse across edits)"',
        'return True, f"{name} declared no --inputs and the working tree changed since it ran (declare --inputs to reuse across edits)"',
        ['VERIFIED', 'STALE']),
    row(8, 'ChangedTests', 2, 'test_matched_unmatched_and_unscoped', 312, 'assurance.py', 'selected',
        'chosen = not negative', 'chosen = True', ['CALC-R4']),
    row(9, 'ReportFormatTests', 2, 'test_text_and_json_fields_without_output', 336, 'assurance.py', '',
        'SCHEMA_VERSION = 1', 'SCHEMA_VERSION = 2', ['2 != 1']),
    row(10, 'ExitCodeTests', 4, 'test_strict_counts_undeclared', 391, 'assurance.py', 'exit_code',
        "failing = FAILING + (('UNDECLARED',) if strict else ())", 'failing = FAILING', ['0 != 1']),
    row(11, 'Assurance', 1, 'test_assurance_documented', 267, '.ai/lifecycle.md', '',
        '| Assurance |', '| Assurance-broken |', ['Recording table row', 'Regex didn\'t match']),
]


def selector(item, mutant=False):
    name = item['module'] + '.' + item['class']
    return name + '.' + item['method'] if mutant else name


def check_rows(rows):
    require([r['id'] for r in rows] == [f'N{i:02}' for i in range(1, 12)], 'incomplete/duplicate row map')
    require(len({selector(r) for r in rows}) == 11 and sum(r['count'] for r in rows) == 30, 'invalid class map')


def roster(root):
    check_rows(ROWS)
    result = {}
    for item in ROWS:
        source = safe(root, '.ai/scripts/tests/' + item['module'] + '.py').read_text()
        tree = ast.parse(source)
        classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == item['class']]
        require(len(classes) == 1, 'missing/duplicate class: ' + item['class'])
        names = sorted(node.name for node in classes[0].body
                       if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'))
        require(len(names) == item['count'] and item['method'] in names, 'method roster mismatch')
        result[item['id']] = [selector(item) + '.' + name for name in names]
    return result


def mutate(original, item):
    text = original.decode('utf-8')
    lines = text.splitlines(keepends=True)
    start, end = 0, len(lines)
    if item['scope']:
        nodes = ast.parse(text).body
        for name in item['scope'].split('.'):
            matches = [n for n in nodes if isinstance(n, ast.FunctionDef) and n.name == name]
            require(len(matches) == 1, 'mutation function not unique')
            node = matches[0]
            start, end = node.lineno - 1, node.end_lineno
            nodes = node.body
    region = ''.join(lines[start:end])
    require(region.count(item['old']) == 1 and item['old'] != item['new'], 'unapplied/ambiguous mutation')
    changed = ''.join(lines[:start]) + region.replace(item['old'], item['new'], 1) + ''.join(lines[end:])
    result = changed.encode('utf-8')
    require(digest(result) != digest(original), 'unapplied mutation')
    if item['path'].endswith('.py'):
        ast.parse(changed)
    return result


class Capture(unittest.TestResult):
    def __init__(self):
        super().__init__()
        self.started, self.finished, self.proofs = [], [], []

    def startTest(self, test):
        self.started.append(test.id())
        super().startTest(test)

    def stopTest(self, test):
        self.finished.append(test.id())
        super().stopTest(test)

    def addFailure(self, test, error):
        frames = []
        trace = error[2]
        while trace:
            frame = trace.tb_frame
            values = {}
            if 'rid' in frame.f_locals:
                values['rid'] = str(frame.f_locals['rid'])
            if isinstance(frame.f_locals.get('listed'), dict):
                values['listed_ids'] = sorted(frame.f_locals['listed'])
            frames.append(dict(file=Path(frame.f_code.co_filename).name, function=frame.f_code.co_name,
                               line=trace.tb_lineno, locals=values))
            trace = trace.tb_next
        self.proofs.append(dict(id=test.id(), type=error[0].__name__, message=str(error[1]), frames=frames,
                                traceback=''.join(traceback.format_exception(*error))))
        super().addFailure(test, error)

    def data(self, loaded):
        return dict(loaded=loaded, started=self.started, finished=self.finished, run=self.testsRun,
                    failures=self.proofs, errors=[dict(id=t.id(), traceback=s) for t, s in self.errors],
                    skips=[t.id() for t, _ in self.skipped], unexpected=[t.id() for t in self.unexpectedSuccesses],
                    expected_failures=[t.id() for t, _ in self.expectedFailures])


def leaves(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from leaves(test)
        else:
            yield test


def worker(root, name, output):
    sys.path[:0] = [str(root / '.ai/scripts/tests'), str(root / '.ai/scripts')]
    suite = unittest.TestLoader().loadTestsFromName(name)
    loaded = [test.id() for test in leaves(suite)]
    result = Capture()
    suite.run(result)
    write_new(output, result.data(loaded))
    return 0 if result.wasSuccessful() else 1


def judge(data, expected, item=None):
    for key in ('loaded', 'started', 'finished'):
        require(sorted(data[key]) == sorted(expected) and len(set(data[key])) == len(expected),
                key + ': wrong test IDs')
    require(data['run'] == len(expected) and bool(expected), 'empty/wrong test execution count')
    require(not any(data[k] for k in ('errors', 'skips', 'unexpected', 'expected_failures')), 'non-assertion result')
    if item is None:
        require(not data['failures'], 'baseline assertion failure')
        return
    require(len(expected) == 1 and len(data['failures']) == 1, 'wrong mutant failure count')
    proof = data['failures'][0]
    require(proof['id'] == expected[0] and proof['type'] == 'AssertionError', 'wrong mutant failure')
    frames = [f for f in proof['frames'] if f['file'] == item['module'] + '.py'
              and f['function'] == item['method'] and f['line'] == item['line']]
    require(len(frames) == 1 and all(term in proof['message'] for term in item['terms']), 'wrong assertion/meaning')
    if item['id'] == 'N01':
        require(frames[0]['locals'].get('rid') == 'CALC-R3', 'wrong malformed case')
    if item['id'] == 'N08':
        require(frames[0]['locals'].get('listed_ids') == ['CALC-R1', 'CALC-R3', 'CALC-R4', 'CALC-R5'],
                'wrong changed selection')


def restored(actual, expected):
    require(actual == expected, 'restoration/readback failed')


def operator_controls():
    caught = []
    result = Capture()
    unittest.TestSuite().run(result)
    empty = result.data([])
    class Unrelated(unittest.TestCase):
        def runTest(self):
            raise RuntimeError('unrelated loader/error proof')
    error_result = Capture()
    test = Unrelated()
    unittest.TestSuite([test]).run(error_result)
    controls = [
        ('empty-suite', lambda: judge(empty, [])),
        ('unapplied-mutation', lambda: mutate(b'x = 1\n', dict(scope='', old='1', new='1', path='x.py'))),
        ('unrelated-error', lambda: judge(error_result.data([test.id()]), [test.id()], ROWS[0])),
        ('restoration-failure', lambda: restored('changed', 'original')),
    ]
    for name, check in controls:
        try:
            check()
        except ProofError:
            caught.append(name)
        else:
            raise ProofError('invalid proof accepted: ' + name)
    return caught


def run_process(argv, cwd, env, timeout):
    begun = time.monotonic()
    process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, errors='replace', start_new_session=True)
    expired = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        expired = True
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate(timeout=5)
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)
    return dict(argv=argv, cwd=str(cwd), exit=process.returncode, timeout=expired,
                duration=time.monotonic() - begun, stdout=stdout, stderr=stderr)


def git(*args):
    return subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True, text=True,
                          check=True, timeout=20).stdout.strip()


def candidate():
    require(file_hash(HERE / MANIFEST) == MANIFEST_HASH, 'approval manifest changed')
    require(file_hash(HERE / SPEC) == SPEC_HASH, 'approved spec changed')
    pins = parse_pins((HERE / MANIFEST).read_text())
    require(len(pins) == 42, 'wrong candidate pin inventory')
    check_files(ROOT, pins)
    expected = {name for name in pins if Path(name).parent == Path('.ai/scripts')}
    require({str(p.relative_to(ROOT)) for p in (ROOT / '.ai/scripts').glob('*.py')} == expected,
            'root script inventory drift')
    require(git('rev-parse', 'HEAD') == HEAD and git('branch', '--show-current') == BRANCH, 'HEAD/branch drift')
    return dict(pins=pins, head=HEAD, branch=BRANCH, status=git('status', '--porcelain=v1'), roster=roster(ROOT))


def runtime():
    result = {}
    for name, executable in (('python', sys.executable), ('git', shutil.which('git'))):
        require(bool(executable), 'runtime unavailable: ' + name)
        path = Path(executable).resolve()
        version = subprocess.run([str(path), '--version'], capture_output=True, text=True, timeout=10, check=True)
        result[name] = dict(path=str(path), sha256=file_hash(path), version=(version.stdout + version.stderr).strip())
    return result


def identity():
    return dict(candidate=candidate(), runtime=runtime(),
                operator={name: file_hash(HERE / name) for name in
                          (Path(__file__).name, 'test_closeout_c1_operator.py', PLAN, SPEC, MANIFEST, REVIEW)})


def freeze():
    review = (HERE / REVIEW).read_text()
    require(re.search(r'(?m)^## Verdict\s*\n+Approved', review) is not None, 'pre-run review not Approved')
    require(not RESULTS.exists(), 'campaign already attempted')
    data = identity()
    for item in ROWS:
        name = item['path'] if item['path'].startswith('.ai/') else '.ai/scripts/' + item['path']
        mutate(safe(ROOT, name).read_bytes(), item)
    write_new(FREEZE, data)
    print('FROZEN: current candidate/operator/review; no product tests executed')


def artifact_pins(root):
    return {str(path.relative_to(root)): file_hash(path) for path in sorted(root.rglob('*'))
            if path.is_file() and path.name not in ('report.json', 'report.sha256') and '.work' not in path.parts}


def validate_report(root, report, current):
    require(report['outcome'] == 'MECHANICAL_PASS' and report['identity'] == current, 'failed/stale evidence')
    require(report['controls'] == ['empty-suite', 'unapplied-mutation', 'unrelated-error', 'restoration-failure'],
            'operator controls incomplete')
    require([r['id'] for r in report['rows']] == [r['id'] for r in ROWS], 'incomplete evidence map')
    require(report['product_invocations'] == 22 and report['duration'] <= 1200, 'campaign bounds not met')
    require(not (root / '.work').exists(), 'disposable data not removed')
    for item, recorded in zip(ROWS, report['rows']):
        require(recorded['restored'] is True and recorded['candidate_after'] == current['candidate'], 'restoration drift')
        expected = current['candidate']['roster'][item['id']]
        for phase, ids, mutation in (('baseline', expected, None), ('mutant', [selector(item, True)], item)):
            data = json.loads((root / (item['id'] + '-' + phase + '-tests.json')).read_text())
            process = json.loads((root / (item['id'] + '-' + phase + '-process.json')).read_text())
            require(not process['timeout'] and process['exit'] == (1 if mutation else 0), 'bad process result')
            judge(data, ids, mutation)
        name = recorded['path']
        original = safe(ROOT, name).read_bytes()
        require(recorded['before'] == digest(original) and recorded['after'] == digest(mutate(original, item)),
                'wrong mutation bytes')
    check_files(root, report['artifacts'])
    require(artifact_pins(root) == report['artifacts'], 'artifact set drift')


def reuse(root, current):
    try:
        raw = (root / 'report.json').read_bytes()
        require((root / 'report.sha256').read_text().strip() == digest(raw), 'report seal mismatch')
        report = json.loads(raw)
        validate_report(root, report, current)
    except (KeyError, ValueError, OSError) as error:
        raise ProofError('incomplete or corrupt campaign: ' + str(error)) from error
    print('REUSE: same complete campaign; no product tests executed')
    return report


def isolated_env(base):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_') and k not in
           ('_AGENTIC_REVIEW_PRODUCER', '_AGENTIC_LIFECYCLE_RUN_ROOTS', 'OKF_AUTONOMOUS',
            'LIFECYCLE_GUARD', 'OKF_SHELL_GUARD', 'PYTHONPATH', 'PYTHONHOME')}
    for key, name in (('HOME', 'home'), ('XDG_CACHE_HOME', 'cache'), ('TMPDIR', 'tmp'), ('TMP', 'tmp'), ('TEMP', 'tmp')):
        path = base / name
        path.mkdir(exist_ok=True)
        env[key] = str(path)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    return env


def campaign(current):
    RESULTS.mkdir()  # Atomic claim; an attempted campaign is never restarted automatically.
    started = time.monotonic()
    deadline = started + 1200
    report = dict(outcome='FAILED', identity=current, rows=[], controls=[], product_invocations=0)
    work = RESULTS / '.work'
    work.mkdir()
    try:
        report['controls'] = operator_controls()
        for item in ROWS:
            require(candidate() == current['candidate'], 'invoking drift before row')
            record = dict(id=item['id'], restored=False)
            for phase in ('baseline', 'mutant'):
                base = work / (item['id'] + '-' + phase)
                base.mkdir()
                copied = base / 'repo'
                copied.mkdir()
                pins = current['candidate']['pins']
                for name in pins:
                    destination = safe(copied, name)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(safe(ROOT, name).read_bytes())
                check_files(copied, pins)
                name = item['path'] if item['path'].startswith('.ai/') else '.ai/scripts/' + item['path']
                target = safe(copied, name)
                original = target.read_bytes()
                try:
                    if phase == 'mutant':
                        changed = mutate(original, item)
                        target.write_bytes(changed)
                        require(file_hash(target) == digest(changed), 'mutation not applied')
                        check_files(copied, {p: s for p, s in pins.items() if p != name})
                        record.update(path=name, before=digest(original), after=digest(changed),
                                      old=item['old'], new=item['new'])
                        write_new(RESULTS / (item['id'] + '-mutation.json'), record)
                    remaining = deadline - time.monotonic() - 5
                    require(remaining > 0, 'global deadline reached')
                    output = RESULTS / (item['id'] + '-' + phase + '-tests.json')
                    command = [sys.executable, '-I', '-B', str(Path(__file__).resolve()), '--worker',
                               str(copied), selector(item, phase == 'mutant'), str(output)]
                    report['product_invocations'] += 1
                    process = run_process(command, copied, isolated_env(base), min(180, remaining))
                    write_new(RESULTS / (item['id'] + '-' + phase + '-process.json'), process)
                    require(not process['timeout'] and process['exit'] == (1 if phase == 'mutant' else 0),
                            'worker error/timeout: ' + item['id'] + ' ' + phase)
                    data = json.loads(output.read_text())
                    judge(data, [selector(item, True)] if phase == 'mutant' else current['candidate']['roster'][item['id']],
                          item if phase == 'mutant' else None)
                finally:
                    target.write_bytes(original)
                    restored(file_hash(target), digest(original))
                    check_files(copied, pins)
                    shutil.rmtree(base)
                    require(not base.exists(), 'copy disposal failed')
            record.update(restored=True, candidate_after=candidate())
            require(record['candidate_after'] == current['candidate'], 'invoking drift after row')
            report['rows'].append(record)
            print(item['id'] + ': baseline PASS; intended assertion rejected; restored', flush=True)
        shutil.rmtree(work)
        require(candidate() == current['candidate'] and time.monotonic() < deadline, 'final drift/deadline')
        report['outcome'] = 'MECHANICAL_PASS'
    except BaseException as error:
        report['error'] = type(error).__name__ + ': ' + str(error)
        report['traceback'] = traceback.format_exc()
        if work.exists():
            try:
                shutil.rmtree(work)
            except OSError as cleanup:
                report['cleanup_error'] = str(cleanup)
    report['duration'] = time.monotonic() - started
    report['artifacts'] = artifact_pins(RESULTS)
    report['qualification'] = 'Current candidate only. C1 remains open pending independent evidence review.'
    write_new(RESULTS / 'report.json', report)
    (RESULTS / 'report.sha256').write_text(file_hash(RESULTS / 'report.json') + '\n')
    try:
        require(report['outcome'] == 'MECHANICAL_PASS', report.get('error', 'campaign failed'))
        validate_report(RESULTS, report, current)
        require(time.monotonic() < deadline, 'overall deadline crossed during final verification')
        report['duration'] = time.monotonic() - started
        report['duration_basis'] = 'through final evidence verification; publication also deadline-checked'
        publish_report(report)
        require(time.monotonic() < deadline, 'overall deadline crossed during final publication')
    except BaseException as error:
        report.update(outcome='FAILED', error=type(error).__name__ + ': ' + str(error),
                      duration=time.monotonic() - started, traceback=traceback.format_exc())
        publish_report(report)
        raise ProofError(report['error']) from error
    print('MECHANICAL_PASS: 30 baseline tests, 11 intended mutant rejections, 4 invalid-proof controls; independent review pending')


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--worker':
        require(len(sys.argv) == 5, 'invalid worker arguments')
        return worker(Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]))
    require(len(sys.argv) <= 2, 'unexpected arguments')
    if sys.argv[1:] == ['--freeze']:
        freeze()
        return 0
    require(len(sys.argv) == 1, 'unknown argument')
    def interrupted(signum, frame):
        raise ProofError('campaign interrupted by signal ' + str(signum))
    signal.signal(signal.SIGTERM, interrupted)
    current = identity()
    require(json.loads(FREEZE.read_text()) == current, 'operator/candidate not frozen after review')
    if RESULTS.exists():
        reuse(RESULTS, current)
    else:
        campaign(current)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ProofError, OSError, ValueError, KeyError) as exc:
        print('C1 PROOF REFUSED: ' + str(exc), file=sys.stderr)
        sys.exit(1)
