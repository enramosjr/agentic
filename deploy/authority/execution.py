"""Provider execution and cleanup orchestration. Public live entry points are held."""
from __future__ import annotations

import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '.ai/scripts'))
from authority_jobs import check_result, validate_lease
from trusted_ci_policy import digest, require


def execute(provider, lease, now=None, sleep=time.sleep, cancelled=lambda: False):
    """A result is eligible only after verified execution AND owned-host cleanup.

    Providers implement authenticated launch/readback/report/cleanup. Local tests
    supply fixtures; their output cannot become hosted qualification evidence.
    """
    now = now or (lambda: int(time.time()))
    validate_lease(lease, now())
    require(not cancelled(), 'job cancelled before launch')
    handle = provider.launch(lease)
    report = None
    try:
        for _ in range(301):
            require(not cancelled(), 'job cancelled')
            validate_lease(lease, now())
            provider.observe(handle, lease)
            value = provider.report(lease)
            if value is not None:
                report = check_result(value, lease, now())
                break
            sleep(2)
        require(report is not None, 'job report deadline exceeded')
    finally:
        provider.cleanup(handle, lease)
    require(not cancelled(), 'job cancelled during cleanup')
    validate_lease(lease, now())
    return {'schema_version': 2, 'lease_digest': digest(lease), 'report': report,
            'cleanup_complete': True, 'enforcement_active': False}
