import abc
import typing

from . import conversions
from . import tests

# This module defines Policy, which maps intended state expressed in some
# convenient form into the corresponding test to apply to quote content.
# The content of a quote is a binary event log and a set of PCR contents.
# This module also implements a registry of policies.

IntendedState = typing.Mapping[str, tests.Data]

TestResultConsumer = typing.Callable[[str], typing.Any]
"""TestResultConsumer is a continuation that is given a test result

A test result is either a string reason why the test failed
or the empty string (which indicates success)."""

QuoteContentTester = typing.Callable[[
    bytes, tests.PCR_Contents, TestResultConsumer], typing.Any]
"""QuoteContentTester evaluates an event log and PCR contents

The tester returns whatever the consumer returns.
We use CPS here so that the tester can leak temp files for debugging
if the consumer raises an Exception.
"""


class Policy(metaclass=abc.ABCMeta):
    """Policy can compile parameters into a test"""

    def __init__(self):
        super(Policy, self).__init__()
        return

    @abc.abstractclassmethod
    def compile(self, params: IntendedState) -> QuoteContentTester:
        """Compile the given params into a quote content tester"""
        raise NotImplementedError

    pass


def _mkreg() -> typing.Mapping[str, Policy]:
    return dict()


_registry = _mkreg()


def register(name: str, policy: Policy):
    """Remember the given policy under the given name"""
    _registry[name] = policy
    return


def get_policy_names() -> typing.Tuple[str, ...]:
    """Return the list of policy names"""
    return list(_registry.keys())


def compile(policy_name: str, params: IntendedState) -> QuoteContentTester:
    """Compiles the given intended state into a quote content tester"""
    if policy_name not in _registry:
        return f'there is no policy named {policy_name!a}'
    policy = _registry[policy_name]
    return policy.compile(params)
