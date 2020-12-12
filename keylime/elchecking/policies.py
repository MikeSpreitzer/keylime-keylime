import abc
import typing

from . import conversions
from . import tests

# This module defines Policy, which maps intended state expressed in some
# convenient form into the corresponding Test to apply to an eventlog.
# This module also implements a registry of policies.

IntendedState = typing.Mapping[str, tests.Data]


class Policy(metaclass=abc.ABCMeta):
    """Policy can compile parameters into a Test"""

    def __init__(self):
        super(Policy, self).__init__()
        return

    @abc.abstractclassmethod
    def compile(self, params: IntendedState) -> tests.Test:
        """Compile the given params into a Test"""
        raise NotImplementedError

    pass


_registry = dict()


def register(name: str, policy: Policy):
    """Remember the given policy under the given name"""
    _registry[name] = policy
    return


def get_policies() -> typing.Tuple[str, ...]:
    """Return the list of policy names"""
    return [key for key in _registry]


def compile(policy_name: str, params: IntendedState) -> tests.Test:
    """Compiled the given parameter value set into a Test"""
    if policy_name not in _registry:
        return f'there is no policy named {policy_name!a}'
    policy = _registry[policy_name]
    return policy.compile(params)


def convert_and_use_test_result(eventlog: bytes, test: tests.Test, consume: typing.Callable[[str], None]):
    """Parse and enrich, then test, then use the test result.

    The given binary eventlog is parsed then enriched.
    The resulting data structure is given to `test`.
    The result of the test is given to `consume`.
    The use of CPS here lets deletion of temp files happen only
    if and when consumption of test result completes successfully.
    """
    if type(eventlog) != bytes:
        return f'eventlog is a {type(eventlog)} rather than bytes'
    conversions.bin_to_json(eventlog,
                            lambda logdata: consume(test.why_not(logdata)))
    return
