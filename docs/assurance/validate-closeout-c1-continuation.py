#!/usr/bin/env python3
"""Approved C1 continuation: immutable N01-N08 reuse; only six N09-N11 workers. R1-R6."""
import importlib.util
import json
from pathlib import Path
import re
import shutil
import signal
import sys
import time
import traceback

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD_FILE = HERE / 'validate-closeout-c1.py'
OLD_HASH = 'd86802775f980e2d8daebe34693a5e3f77ee77c471496b7cb8262b831d6da0fb'
# Only definitions are imported. The old main/campaign and globals remain untouched.
import hashlib
if hashlib.sha256(OLD_FILE.read_bytes()).hexdigest() != OLD_HASH:
    raise RuntimeError('immutable original operator changed')
module_spec = importlib.util.spec_from_file_location('c1_original_helpers', OLD_FILE)
old = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(old)

AMENDMENT = HERE / 'amendment-closeout-c1-continuation.md'
PRE_REVIEW = HERE / 'review-operator-closeout-c1-continuation.md'
FREEZE = HERE / 'closeout-c1-continuation-freeze.json'
RESULTS = HERE / 'closeout-c1-continuation-results'
PRIOR_ROOT = HERE / 'closeout-c1-validation-results'
PRIOR_REPORT_HASH = 'a0d0cbf1cf2fc0368b939cef63b323ba9bbfda04e2de7a4299aace27a7fd2fc2'
PRIOR_FREEZE_HASH = '0bdf33257d4139da8793b8515d3f0a30ff89eec43048f0fa86a97145d72549ed'
PRIOR_REVIEW_HASH = '413c07d896e2f93ebf2f0af46d6fadda89574de2019a522ce73fd357d3a25023'
NEW_ROWS = tuple(old.ROWS[8:])
CONTROLS = ['empty-suite', 'unapplied-mutation', 'unrelated-error', 'restoration-failure']
N08_IDS = ['CALC-R1', 'CALC-R2', 'CALC-R3', 'CALC-R4', 'CALC-R5']


def read(path):
    return json.loads(path.read_text())


def judge(data, expected, item=None):
    if item is None or item['id'] != 'N08':
        return old.judge(data, expected, item)
    # Preserve every original failure-quality condition; amend only the extra N08 ID oracle.
    for field in ('loaded', 'started', 'finished'):
        old.require(data[field] == expected and len(expected) == 1, 'wrong N08 test execution')
    old.require(data['run'] == 1 and not any(data[k] for k in
                ('errors', 'skips', 'unexpected', 'expected_failures')), 'non-assertion N08 result')
    old.require(len(data['failures']) == 1, 'wrong N08 failure count')
    failure = data['failures'][0]
    old.require(failure['id'] == expected[0] and failure['type'] == 'AssertionError', 'wrong N08 failure')
    frames = [f for f in failure['frames'] if f['file'] == item['module'] + '.py'
              and f['function'] == item['method'] and f['line'] == item['line']]
    old.require(len(frames) == 1 and all(t in failure['message'] for t in item['terms']), 'wrong N08 assertion')
    old.require(frames[0]['locals'].get('listed_ids') == N08_IDS, 'wrong amended N08 selection')


def canonical(item):
    return item['path'] if item['path'].startswith('.ai/') else '.ai/scripts/' + item['path']


def check_pair(folder, item, candidate):
    for phase in ('baseline', 'mutant'):
        process = read(folder / (item['id'] + '-' + phase + '-process.json'))
        old.require(not process['timeout'] and process['exit'] == int(phase == 'mutant'), 'worker failure/timeout')
        data = read(folder / (item['id'] + '-' + phase + '-tests.json'))
        ids = [old.selector(item, True)] if phase == 'mutant' else candidate['roster'][item['id']]
        judge(data, ids, item if phase == 'mutant' else None)
    mutation = read(folder / (item['id'] + '-mutation.json'))
    original = old.safe(ROOT, canonical(item)).read_bytes()
    old.require(mutation['path'] == canonical(item) and mutation['before'] == old.digest(original)
                and mutation['after'] == old.digest(old.mutate(original, item))
                and mutation['old'] == item['old'] and mutation['new'] == item['new'], 'mutation identity drift')


def prior_audit():
    old.require(old.file_hash(PRIOR_ROOT / 'report.json') == PRIOR_REPORT_HASH, 'prior report changed')
    old.require((PRIOR_ROOT / 'report.sha256').read_text().strip() == PRIOR_REPORT_HASH, 'prior report seal changed')
    freeze_path = HERE / 'closeout-c1-operator-freeze.json'
    review_path = HERE / 'review-evidence-closeout-c1-stopped.md'
    old.require(old.file_hash(freeze_path) == PRIOR_FREEZE_HASH, 'prior freeze changed')
    old.require(old.file_hash(review_path) == PRIOR_REVIEW_HASH, 'partial evidence review changed')
    frozen = read(freeze_path)
    old.require(old.identity() == frozen, 'original candidate/runtime/operator drift')
    report = read(PRIOR_ROOT / 'report.json')
    old.require(report['identity'] == frozen and report['outcome'] == 'FAILED'
                and report['product_invocations'] == 16 and report['duration'] < 1200
                and report['error'] == 'ProofError: ProofError: wrong changed selection', 'unapproved prior outcome')
    old.require(report['controls'] == CONTROLS and len(report['artifacts']) == 40, 'prior controls/artifacts incomplete')
    old.check_files(PRIOR_ROOT, report['artifacts'])
    old.require(old.artifact_pins(PRIOR_ROOT) == report['artifacts'] and not (PRIOR_ROOT / '.work').exists(),
                'prior artifact set/cleanup drift')
    old.require([r['id'] for r in report['rows']] == [r['id'] for r in old.ROWS[:7]], 'prior completed map drift')
    reused = []
    for item in old.ROWS[:8]:
        check_pair(PRIOR_ROOT, item, frozen['candidate'])
        if item['id'] != 'N08':
            record = report['rows'][int(item['id'][1:]) - 1]
            old.require(record['restored'] and record['candidate_after'] == frozen['candidate'], 'prior restore drift')
        reused.append(dict(id=item['id'], baseline_count=item['count'], source='immutable stopped campaign',
                           restoration='qualified-control-flow' if item['id'] == 'N08' else 'explicit',
                           raw_prefix=item['id'], report_sha256=PRIOR_REPORT_HASH))
    return dict(outcome='FAILED', convergence='0 PASS / 6 FAIL / 0 MANUAL', product_invocations=16,
                duration=report['duration'], rows=reused, report_sha256=PRIOR_REPORT_HASH,
                freeze_sha256=PRIOR_FREEZE_HASH, evidence_review_sha256=PRIOR_REVIEW_HASH,
                qualification='N08 restoration: reviewed frozen finally control flow; no completed row flag invented.')


def identity():
    return dict(original=old.identity(), prior=prior_audit(),
                files={p.name: old.file_hash(p) for p in
                       (Path(__file__), HERE / 'test_closeout_c1_continuation.py', AMENDMENT, PRE_REVIEW)})


def guard(current):
    old.require(old.candidate() == current['original']['candidate'], 'invoking candidate drift')


def freeze():
    old.require(re.search(r'(?m)^## Verdict\s*\n+Approved', PRE_REVIEW.read_text()) is not None,
                'independent pre-run review not Approved')
    old.require(not RESULTS.exists(), 'continuation already attempted')
    old.write_new(FREEZE, identity())
    print('FROZEN continuation: prior failure preserved; no product workers launched')


def launch(argv, cwd, env, timeout):
    return old.run_process(argv, cwd, env, timeout)


def restore_copy(copied, target, original, pins, base):
    target.write_bytes(original)
    old.restored(old.file_hash(target), old.digest(original))
    old.check_files(copied, pins)
    shutil.rmtree(base)
    old.require(not base.exists(), 'copy disposal failed')


def validate_report(report, current):
    old.require(report['outcome'] == 'MECHANICAL_PASS' and report['identity'] == current, 'failed/stale continuation')
    old.require(report['prior'] == prior_audit(), 'prior evidence drift')
    old.require(report['controls'] == CONTROLS and report['new_workers'] == 6 and report['aggregate_workers'] == 22,
                'wrong controls/worker accounting')
    old.require(report['duration'] <= 300 and report['aggregate_active_duration'] < 1200, 'deadline exceeded')
    old.require(report['aggregate_baselines'] == 30 and report['aggregate_mutant_rejections'] == 11,
                'wrong aggregate test counts')
    old.require([r['id'] for r in report['rows']] == ['N09', 'N10', 'N11'], 'new row set incomplete')
    old.require(report['aggregate_rows'] == report['prior']['rows'] + report['rows'], 'aggregate map drift')
    old.require(not (RESULTS / '.work').exists(), 'work not disposed')
    candidate = current['original']['candidate']
    for item, record in zip(NEW_ROWS, report['rows']):
        check_pair(RESULTS, item, candidate)
        old.require(record['restored'] is True and record['candidate_after'] == candidate, 'restore/candidate drift')
        for phase in ('baseline', 'mutant'):
            restoration = read(RESULTS / (item['id'] + '-' + phase + '-restoration.json'))
            old.require(restoration['ok'] is True and restoration['sha256'] == candidate['pins'][canonical(item)],
                        'missing phase restoration proof')
    old.check_files(RESULTS, report['artifacts'])
    old.require(old.artifact_pins(RESULTS) == report['artifacts'], 'new artifact set drift')
    guard(current)


def publish(report):
    pending = RESULTS / 'report.pending'
    old.write_new(pending, report)
    pending.replace(RESULTS / 'report.json')
    (RESULTS / 'report.sha256').write_text(old.file_hash(RESULTS / 'report.json') + '\n')


def reuse(current):
    old.require((RESULTS / 'report.sha256').read_text().strip() == old.file_hash(RESULTS / 'report.json'),
                'continuation seal changed')
    report = read(RESULTS / 'report.json')
    validate_report(report, current)
    print('REUSE continuation: same complete aggregate evidence; no product workers launched')
    return report


def campaign(current, started=None):
    begun = time.monotonic() if started is None else started
    deadline = begun + 300
    RESULTS.mkdir()  # Atomic claim. Partial/failed evidence never triggers a new attempt.
    work = RESULTS / '.work'
    work.mkdir()
    report = dict(outcome='FAILED', identity=current, prior=prior_audit(), rows=[], controls=[], new_workers=0)
    try:
        report['controls'] = old.operator_controls()
        for item in NEW_ROWS:
            guard(current)
            record = dict(id=item['id'], baseline_count=item['count'], source='new continuation', restored=False)
            for phase in ('baseline', 'mutant'):
                old.require(report['new_workers'] < 6, 'worker cap reached')
                base = work / (item['id'] + '-' + phase)
                base.mkdir()
                copied = base / 'repo'
                copied.mkdir()
                pins = current['original']['candidate']['pins']
                for name in pins:
                    destination = old.safe(copied, name)
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(old.safe(ROOT, name).read_bytes())
                old.check_files(copied, pins)
                target = old.safe(copied, canonical(item))
                original = target.read_bytes()
                try:
                    if phase == 'mutant':
                        changed = old.mutate(original, item)
                        target.write_bytes(changed)
                        old.require(old.file_hash(target) == old.digest(changed), 'mutation not applied')
                        old.check_files(copied, {p: s for p, s in pins.items() if p != canonical(item)})
                        old.write_new(RESULTS / (item['id'] + '-mutation.json'),
                                      dict(path=canonical(item), before=old.digest(original), after=old.digest(changed),
                                           old=item['old'], new=item['new']))
                    remaining = deadline - time.monotonic() - 5
                    old.require(remaining > 0, 'segment deadline reached')
                    output = RESULTS / (item['id'] + '-' + phase + '-tests.json')
                    command = [sys.executable, '-I', '-B', str(Path(__file__).resolve()), '--worker',
                               str(copied), old.selector(item, phase == 'mutant'), str(output)]
                    report['new_workers'] += 1
                    process = launch(command, copied, old.isolated_env(base), min(180, remaining))
                    old.write_new(RESULTS / (item['id'] + '-' + phase + '-process.json'), process)
                    old.require(not process['timeout'] and process['exit'] == int(phase == 'mutant'), 'worker error/timeout')
                    expected = ([old.selector(item, True)] if phase == 'mutant'
                                else current['original']['candidate']['roster'][item['id']])
                    judge(read(output), expected, item if phase == 'mutant' else None)
                finally:
                    restoration = dict(ok=False)
                    try:
                        restore_copy(copied, target, original, pins, base)
                        restoration.update(ok=True, sha256=old.digest(original))
                    except BaseException as error:
                        restoration['error'] = type(error).__name__ + ': ' + str(error)
                        raise
                    finally:
                        old.write_new(RESULTS / (item['id'] + '-' + phase + '-restoration.json'), restoration)
            guard(current)
            record.update(restored=True, candidate_after=current['original']['candidate'])
            report['rows'].append(record)
            print(item['id'] + ': baseline PASS; intended assertion rejected; restoration recorded', flush=True)
        shutil.rmtree(work)
        report['outcome'] = 'MECHANICAL_PASS'
    except BaseException as error:
        report.update(error=type(error).__name__ + ': ' + str(error), traceback=traceback.format_exc())
        if work.exists():
            try:
                shutil.rmtree(work)
            except OSError as cleanup:
                report['cleanup_error'] = str(cleanup)
    report.update(aggregate_workers=report['new_workers'] + 16, aggregate_baselines=23 + sum(r['baseline_count'] for r in report['rows']),
                  aggregate_mutant_rejections=8 + len(report['rows']), aggregate_rows=report['prior']['rows'] + report['rows'],
                  duration=time.monotonic() - begun, artifacts=old.artifact_pins(RESULTS),
                  qualification='Original campaign remains FAILED. N08 restoration is qualified control-flow evidence. C1 review pending.',
                  approval_gap='Separate human approval gap excluded from active execution; not one uninterrupted campaign.')
    report['aggregate_active_duration'] = report['prior']['duration'] + report['duration']
    try:
        old.require(report['outcome'] == 'MECHANICAL_PASS', report.get('error', 'continuation failed'))
        validate_report(report, current)
        old.require(time.monotonic() < deadline, 'deadline crossed during final verification')
        report['duration'] = time.monotonic() - begun
        report['aggregate_active_duration'] = report['prior']['duration'] + report['duration']
        publish(report)
        old.require(time.monotonic() < deadline, 'deadline crossed during publication')
    except BaseException as error:
        report.update(outcome='FAILED', error=type(error).__name__ + ': ' + str(error),
                      duration=time.monotonic() - begun, traceback=traceback.format_exc())
        report['aggregate_active_duration'] = report['prior']['duration'] + report['duration']
        publish(report)
        raise old.ProofError(report['error']) from error
    print('MECHANICAL_PASS: exactly 6 new workers; aggregate 30 baseline methods / 11 mutant rejections / 22 workers. Independent review pending.')


def main():
    if sys.argv[1:2] == ['--worker']:
        old.require(len(sys.argv) == 5, 'invalid worker arguments')
        return old.worker(Path(sys.argv[2]), sys.argv[3], Path(sys.argv[4]))
    if sys.argv[1:] == ['--freeze']:
        freeze()
        return 0
    old.require(len(sys.argv) == 1, 'unknown arguments')
    def interrupted(signum, frame):
        raise old.ProofError('continuation interrupted by signal ' + str(signum))
    signal.signal(signal.SIGTERM, interrupted)
    begun = time.monotonic()
    current = identity()
    old.require(read(FREEZE) == current, 'continuation not frozen/current')
    if RESULTS.exists():
        reuse(current)
    else:
        campaign(current, begun)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (old.ProofError, OSError, ValueError, KeyError) as error:
        print('C1 CONTINUATION REFUSED: ' + str(error), file=sys.stderr)
        sys.exit(1)
