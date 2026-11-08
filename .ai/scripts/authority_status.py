"""Local diagnostics are never proof of hosted enforcement."""
import time

import authority_release
from authority_protocol import validate_deployment


def inspect_local(deployment=None):
    result = authority_release.status()
    result.update(kind='local-authority-status', remote_verified=False)
    if deployment is not None:
        d = validate_deployment(deployment)
        result.update(adapter=d['adapter'], repository=d['policy']['repository'],
                      generation=d['generation'], reported_state=d['state'],
                      expired=d['expires'] <= int(time.time()), local_structure_valid=True)
        if d['state'] == 'revoked':
            result['state'] = 'revoked'
    return result
