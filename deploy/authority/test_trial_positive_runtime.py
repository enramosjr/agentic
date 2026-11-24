"""Explicit required isolated eligibility lane; never hosted qualification."""
import argparse
from pathlib import Path
import sys
import time
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'.ai/scripts'))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'.ai/scripts/tests'))

from trusted_ci_fixtures import policy, snapshot
from trusted_ci_policy import CHECKS, Refusal, require
from trial_runtime import archive, pinned_kit, preflight, verify
from trial_specimen import compose, mutate


def eligibility(root, pin, image, runtime):
    preflight(image, runtime)
    baseline, worker = compose(pinned_kit(root, pin))
    p = policy(); p['image'] = image
    d = dict(policy=p,adapter='github-actions',generation=1,account='source-fixture',resources={})
    s = snapshot(p)
    for name, files in [('original',worker), ('bad-acceptance',mutate(worker,'bad-acceptance'))]:
        raw = archive(files)
        class Source:
            def fetch(self, path, **kwargs):
                require(path == '/repos/'+p['repository']+'/tarball/'+s['merge'], 'exact fixture merge archive required')
                return raw
        result = verify(Source(),d,s,17,lambda:None,lambda:int(time.time()),runtime)
        outcomes = result['report']['outcomes']
        expected = ([dict(id=check,status='success') for check in CHECKS] if name=='original' else
                    [dict(id=CHECKS[0],status='failure'), *[dict(id=check,status='not_run') for check in CHECKS[1:]]])
        require(outcomes == expected and result['cleanup_complete'] is True, 'actual critical eligibility or fault control failed')
        print(name+': '+str(outcomes), flush=True)
    return baseline,worker


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--eligibility', action='store_true')
    mode.add_argument('--required', action='store_true')
    mode.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--lost-merge-ack', action='store_true', help='select a fresh strict trial with an uncertain merge response')
    parser.add_argument('--image', required=True)
    parser.add_argument('--runtime', choices=('docker','podman'), default='docker')
    parser.add_argument('--source-pin', default='52cf54117323689104abd3c80b62ce0c3d9b93da')
    parser.add_argument('--source-root', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args(argv)
    if args.lost_merge_ack and not args.required: parser.error('--lost-merge-ack requires --required')
    try:
        if args.eligibility:
            eligibility(args.source_root,args.source_pin,args.image,args.runtime)
        else:
            preflight(args.image,args.runtime)
            sys.path.insert(0,str(Path(__file__).parent/'tests'))
            from positive_fixture import run
            run(args.source_root,args.source_pin,args.image,args.runtime,diagnostic=args.diagnostic,lost_merge_ack=args.lost_merge_ack)
            if args.required: print('strict native sixteen-case source fixture PASS; qualification and activation remain HELD',flush=True)
    except (Refusal,OSError,ValueError) as error:
        print('HELD: '+str(error),file=sys.stderr)
        traceback.print_exc()
        return 1
    return 0


if __name__ == '__main__': raise SystemExit(main())
