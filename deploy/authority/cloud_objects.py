"""Authority-side upload and expiring object capabilities. Never runs in coding."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai/scripts'))
from authority_jobs import artifact_host, new_lease
from authority_protocol import validate_deployment
from trusted_ci_policy import require


def prepare(provider, deployment, snapshot, job_id, nonce, now, bundle, candidate):
    """Only trusted inputs may call this; candidate data supplies no configuration."""
    d = validate_deployment(deployment)
    require(provider.adapter == d['adapter'], 'object provider differs from deployment')
    require(all(isinstance(v, bytes) and 0 < len(v) <= 64 * 1024 * 1024 for v in (bundle, candidate)),
            'bounded nonempty job inputs required')
    host = artifact_host(d)
    prefix = 'https://' + host + '/jobs/' + nonce + '/'
    objects = {key: {'url': prefix + key + '.tgz', 'sha256': hashlib.sha256(raw).hexdigest()}
               for key, raw in (('bundle', bundle), ('candidate', candidate))}
    objects['report'] = {'url': prefix + 'report.json'}
    lease = new_lease(d, snapshot, job_id, nonce, now, objects)
    provider.scope(d)
    provider.upload(d, nonce, 'bundle.tgz', bundle)
    provider.upload(d, nonce, 'candidate.tgz', candidate)
    urls = provider.capabilities(d, nonce, lease['expires'], now)
    for key in objects:
        objects[key]['url'] = urls[key]
    return new_lease(d, snapshot, job_id, nonce, now, objects)


class AWS:
    adapter = 'aws'

    def __init__(self, sts, uploader, session_client):
        self.sts, self.uploader, self.session_client = sts, uploader, session_client

    @classmethod
    def authenticated(cls, d):
        # Optional backend dependency; never imported by the installed client.
        import boto3
        from botocore.config import Config
        r = d['resources']
        config = Config(connect_timeout=10, read_timeout=30, retries={'max_attempts': 2},
                        signature_version='s3v4', s3={'addressing_style': 'virtual'})
        session = boto3.Session(region_name=r['region'])
        sts = session.client('sts', endpoint_url='https://sts.' + r['region'] + '.amazonaws.com')
        require(sts.get_caller_identity()['Account'] == d['account'], 'AWS object identity differs from deployment')
        endpoint = 'https://s3.' + r['region'] + '.amazonaws.com'
        def scoped(credentials, region):
            return boto3.client('s3', region_name=region, endpoint_url=endpoint, config=config,
                aws_access_key_id=credentials['AccessKeyId'], aws_secret_access_key=credentials['SecretAccessKey'],
                aws_session_token=credentials['SessionToken'])
        return cls(sts, session.client('s3', endpoint_url=endpoint, config=config), scoped)

    def scope(self, d):
        r = d['resources']
        require(r['bucket'] == 'agentic-' + d['account'] + '-' + r.get('deployment', '') and
                re.fullmatch('arn:aws:iam::' + d['account'] + r':role/[A-Za-z0-9+=,.@_-]+',
                             r.get('job_io_role', '')), 'AWS object inventory differs from deployment')

    def upload(self, d, nonce, filename, raw):
        self.uploader.put_object(Bucket=d['resources']['bucket'], Key='jobs/' + nonce + '/' + filename,
                                 Body=raw, ServerSideEncryption='AES256')

    def capabilities(self, d, nonce, expires, now):
        bucket, region = d['resources']['bucket'], d['resources']['region']
        prefix = 'jobs/' + nonce + '/'
        arn = 'arn:aws:s3:::' + bucket + '/' + prefix
        policy = {'Version': '2012-10-17', 'Statement': [
            {'Effect': 'Allow', 'Action': 's3:GetObject', 'Resource': [arn + 'bundle.tgz', arn + 'candidate.tgz']},
            {'Effect': 'Allow', 'Action': 's3:PutObject', 'Resource': arn + 'report.json'}]}
        credentials = self.sts.assume_role(RoleArn=d['resources']['job_io_role'],
            RoleSessionName='job-' + nonce, DurationSeconds=900, Policy=json.dumps(policy))['Credentials']
        client = self.session_client(credentials, region)
        return {key: client.generate_presigned_url('put_object' if key == 'report' else 'get_object',
            Params={'Bucket': bucket, 'Key': prefix + filename}, ExpiresIn=expires - now,
            HttpMethod='PUT' if key == 'report' else 'GET')
            for key, filename in (('bundle', 'bundle.tgz'), ('candidate', 'candidate.tgz'), ('report', 'report.json'))}


class Azure:
    adapter = 'azure'

    def __init__(self, api):
        self.api = api

    def scope(self, d):
        r, c = d['resources'], self.api.config
        require(d['account'] == c['account'] and r.get('resource_group') == c['deployment'] and
                r['storage_account'] == 'ag' + hashlib.sha256((c['account'] + c['deployment']).encode()).hexdigest()[:20],
                'Azure object inventory differs from deployment')
        self.api.identity()

    def arguments(self, d, nonce, filename):
        return ['--auth-mode', 'login', '--account-name', d['resources']['storage_account'],
                '--blob-endpoint', 'https://' + artifact_host(d), '--container-name', 'jobs',
                '--name', nonce + '/' + filename]

    def upload(self, d, nonce, filename, raw):
        with tempfile.TemporaryDirectory(prefix='agentic-input-') as folder:
            path = Path(folder) / filename
            path.write_bytes(raw)
            self.api.call(['storage', 'blob', 'upload', *self.arguments(d, nonce, filename),
                           '--file', str(path), '--overwrite', 'false', '--no-progress'])

    def capabilities(self, d, nonce, expires, now):
        expiry = datetime.fromtimestamp(expires, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        result = {}
        for key, filename in (('bundle', 'bundle.tgz'), ('candidate', 'candidate.tgz'), ('report', 'report.json')):
            token = self.api.call(['storage', 'blob', 'generate-sas', *self.arguments(d, nonce, filename),
                '--as-user', '--permissions', 'cw' if key == 'report' else 'r', '--expiry', expiry, '--https-only'])
            require(isinstance(token, str) and 0 < len(token) <= 4096 and
                    not any(c in token for c in '\r\n?#'), 'invalid Azure delegated capability')
            result[key] = 'https://' + artifact_host(d) + '/jobs/' + nonce + '/' + filename + '?' + token
        return result
