"""Operational holds for this unqualified build, not remote authorization proof."""
from trusted_ci_policy import Refusal

LOCAL_OPERATIONS = frozenset(('render', 'inspect-local', 'verify-local', 'export'))
HELD_OPERATIONS = frozenset(('bootstrap', 'provision', 'hosted-execute', 'qualify-live',
                             'publish', 'activate', 'protected-run', 'broker-merge'))


class Held(Refusal):
    """An operation is deliberately unavailable under the current release policy."""


def authorize(operation):
    if operation in HELD_OPERATIONS:
        raise Held(operation + ' blocked: build is unqualified; enforcement is inactive')
    if operation not in LOCAL_OPERATIONS:
        raise Refusal('unknown authority operation')


def status():
    return {'state': 'blocked', 'enforcement_active': False,
            'live_qualification_allowed': False, 'privileged_setup_allowed': False,
            'held_operations': sorted(HELD_OPERATIONS),
            'reason': 'trusted bootstrap context and hosted qualification unavailable'}
