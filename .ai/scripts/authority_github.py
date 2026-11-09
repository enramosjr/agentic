"""V2 authority read transport and marker-free exact-candidate discovery."""
from __future__ import annotations

from urllib.parse import unquote, urlsplit
import re

from authority_protocol import validate_deployment
from trusted_ci_policy import digest, positive, require, validate_snapshot


class Readers:
    """Route authority and source reads without lending either token wider scope."""

    def __init__(self, source, authority, deployment):
        validate_deployment(deployment)
        self.source, self.authority = source, authority
        self.source_root = '/repos/' + deployment['policy']['repository']
        self.authority_root = '/repos/' + deployment['policy']['authority_repository']

    def _api(self, path):
        require(isinstance(path, str) and not any(ord(c) < 32 for c in path), 'invalid read path')
        parsed = urlsplit(path)
        decoded = unquote(parsed.path)
        require(not parsed.scheme and not parsed.netloc and '\\' not in decoded and
                not any(p in ('.', '..') for p in decoded.split('/')), 'read path escapes scope')
        for root, api in ((self.source_root, self.source), (self.authority_root, self.authority)):
            if parsed.path == root or parsed.path.startswith(root + '/'):
                return api
        require(False, 'read outside approved repositories refused')

    def get(self, path):
        # Effective CODEOWNERS and App-bot readback need public login identities,
        # not another repository or a caller-selected URL. Preserve GET-only and
        # an exact single login path; all mutation APIs remain absent.
        if isinstance(path, str) and re.fullmatch(r'/users/[A-Za-z0-9_-]+(?:%5[Bb]bot%5[Dd])?', path):
            return self.source.get(path)
        return self._api(path).get(path)

    def pages(self, path, collection=None):
        return self._api(path).pages(path, collection)

    def fetch(self, path, method='GET', data=None, binary=False, limit=1024 * 1024):
        require(method == 'GET' and data is None, 'read transport cannot mutate GitHub')
        return self._api(path).fetch(path, binary=binary, limit=limit)


def current_snapshot(api, deployment, pr_number, run_id, attempt):
    validate_deployment(deployment)
    p = deployment['policy']
    require(positive(pr_number) and positive(run_id) and positive(attempt), 'numeric execution identities required')
    root = '/repos/' + p['repository']
    require(api.get(root)['id'] == p['repository_id'], 'repository identity changed')
    require(api.get('/repos/' + p['authority_repository'])['id'] == p['authority_repository_id'],
            'authority identity changed')
    pr = api.get(root + '/pulls/' + str(pr_number))
    require(pr['state'] == 'open' and not pr['draft'] and pr['base']['ref'] == p['target'],
            'PR must be open, ready and on the approved target')
    head, base = pr['head']['sha'], pr['base']['sha']
    require(api.get(root + '/branches/' + p['target'])['commit']['sha'] == base, 'base changed')
    merge = api.get(root + '/git/ref/pull/' + str(pr_number) + '/merge')['object']['sha']
    parents = api.get(root + '/git/commits/' + merge)['parents']
    require([x['sha'] for x in parents] == [base, head], 'synthetic merge parents mismatch')
    # V2's approved registry is independent of the candidate. Neither the base
    # nor proposed merge needs a marker that would create a setup/check cycle.
    result = dict(repository_id=p['repository_id'], pr=pr_number, head=head, base=base,
                  merge=merge, epoch=p['epoch'], policy_digest=digest(p),
                  verifier_sha=p['verifier_sha'], image=p['image'],
                  authority_repository_id=p['authority_repository_id'], workflow_sha=p['workflow_sha'],
                  run_id=run_id, run_attempt=attempt)
    return validate_snapshot(result, p)
