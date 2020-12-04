import abc

from . import conversions
from . import tests

# This module defines Policy, which maps intended state expressed in some
# convenient form into the corresponding Test to apply to an eventlog.
# This module also implements a registry of policies.


class Policy(metaclass=abc.ABCMeta):
    """Policy can compile parameters into a Test"""

    def __init__(self):
        super(Policy, self).__init__()
        return

    @abc.abstractclassmethod
    def compile(self, params: dict) -> tests.Test:
        """Compile the given params into a Test"""
        raise NotImplementedError

    pass


_registry = dict()


def register(name, policy: Policy):
    """Remember the given policy under the given name"""
    _registry[name] = policy
    return


def get_policies():
    """Return the list of policy names"""
    return [key for key in _registry]


def compile(policy_name: str, params: dict) -> tests.Test:
    """Compiled the given parameter value set into a Test"""
    if policy_name not in _registry:
        return f'there is no policy named {policy_name!a}'
    policy = _registry[policy_name]
    return policy.compile(params)


def convert_and_test(eventlog: bytes, test: tests.Test):
    """Convert the given binary eventlog to its enriched Data form and apply given test"""
    if type(eventlog) != bytes:
        return f'eventlog is a {type(eventlog)} rather than bytes'
    logobj = conversions.bin_to_json(eventlog)
    return test.why_not(logobj)
