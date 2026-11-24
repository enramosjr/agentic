"""Specific measured broker refusals; generic errors are never qualification."""
import copy

from trusted_ci_policy import Refusal, digest


class BrokerRefusal(Refusal):
    def __init__(self, code, message, observation):
        super().__init__(message)
        self.code, self.observation = code, copy.deepcopy(observation)


def same(current, original, message):
    keys = ('configuration_revision', 'deployment_digest', 'deployment', 'fence')
    if any(current[k] != original[k] for k in keys):
        raise BrokerRefusal('configuration_changed', message,
            dict(before=digest({k: original[k] for k in keys}),
                 after=digest({k: current[k] for k in keys})))
