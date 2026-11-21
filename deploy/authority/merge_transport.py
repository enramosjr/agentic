"""One isolated HTTPS merge request under a parent-enforced total deadline."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib import request

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai/scripts'))
from trusted_ci_github import NoRedirect
from trusted_ci_policy import Refusal, loads, object_fields, positive, require, sha


def isolated(document, seconds):
    require(isinstance(seconds, (int, float)) and 0 < seconds <= 30, 'invalid merge transport deadline')
    payload = json.dumps(document, allow_nan=False).encode()
    require(len(payload) <= 64 * 1024, 'merge request exceeds limit')
    # Token stays in stdin. Python isolation and an environment allowlist exclude
    # ambient GitHub/cloud credentials, proxies and Python startup injection.
    environment = {k: v for k, v in os.environ.items() if k.upper() in
                   ('SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP', 'LANG', 'LC_ALL')}
    started = time.monotonic()
    with subprocess.Popen([sys.executable, '-I', str(Path(__file__).resolve())],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            cwd=str(Path(__file__).resolve().parent), env=environment) as child:
        try:
            output, _ = child.communicate(payload, timeout=max(.001, seconds - (time.monotonic() - started)))
        except subprocess.TimeoutExpired:
            child.kill()
            child.communicate()
            raise Refusal('merge request total deadline exceeded; outcome unknown') from None
        require(child.returncode == 0 and len(output) <= 64 * 1024, 'merge request outcome unknown')
    return loads(output)


def request_once(document, opener=None):
    import re
    object_fields(document, ('token', 'repository', 'pr', 'head', 'timeout'), 'merge request')
    token, repository = document['token'], document['repository']
    require(isinstance(token, str) and 0 < len(token) <= 16000 and not any(ord(c) < 32 for c in token) and
            isinstance(repository, str) and re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository) and
            all(p not in ('.', '..') for p in repository.split('/')) and positive(document['pr']) and
            sha(document['head']) and type(document['timeout']) is int and 0 < document['timeout'] <= 30,
            'invalid scoped merge request')
    body = json.dumps({'sha': document['head'], 'merge_method': 'merge'}).encode()
    req = request.Request('https://api.github.com/repos/' + repository + '/pulls/' + str(document['pr']) + '/merge',
        body, {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json',
               'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
               'User-Agent': 'AGENTIC-authority-broker'}, method='PUT')
    with (opener or request.build_opener(NoRedirect())).open(req, timeout=document['timeout']) as response:
        require(response.status == 200, 'merge submission did not return success')
        raw = response.read(64 * 1024 + 1)
        require(len(raw) <= 64 * 1024, 'merge response exceeds limit')
        return loads(raw)


def main():
    try:
        raw = sys.stdin.buffer.read(64 * 1024 + 1)
        require(len(raw) <= 64 * 1024, 'merge request exceeds limit')
        result = request_once(loads(raw))
        sys.stdout.write(json.dumps(result, allow_nan=False))
        return 0
    except Exception:
        # Never relay HTTP bodies, URLs containing data, credentials or tracebacks.
        return 1


if __name__ == '__main__':
    sys.exit(main())
