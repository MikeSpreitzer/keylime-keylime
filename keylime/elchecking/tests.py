import abc
import re
import typing

# This module defines the abstraction of a Test (of JSON data)
# and several specific test classes.
# A Test can be used multiple times, even concurrently.

# VisualStudio Code objects to the subscripting but Python accepts it
Data = typing.Union[int, str, bool, typing.Tuple['Data', ...],
                    typing.Mapping[str, 'Data'], None]
"""Data structure corresponding to JSON"""

Globals = typing.Mapping[str, Data]
"""Globals is a dict of variables for communication among tests.  There is a distinct dict for each top-level test."""

PCR_Contents = typing.Mapping[str, typing.Mapping[str, int]]
"""PCR_Contents maps digest name to map from PCR index to PCR value

Here digest name is something like 'sha256'.
The PCR index is a number expressed in decimal."""


class Test(metaclass=abc.ABCMeta):
    """Test is something that can examine a value and either approve it or explain the reason why not"""

    @abc.abstractmethod
    def why_not(self, gobals: Globals, subject: Data) -> str:
        """Test the given value, return empty string for pass, explanation for fail.

        The explanation is (except in deliberate exceptions) English that
        makes a sentence when placed after a noun phrase.
        The test can read and write in the given globals dict.
        """
        raise NotImplementedError

    pass


def type_test(t) -> typing.Callable[[typing.Any], bool]:
    """Returns a lambda that tests against the given type"""
    def test(v: typing.Any) -> bool:
        if isinstance(v, t):
            return True
        raise Exception(f'{v} is a {type(v)} rather than a {t}')
    return test


class AcceptAll(Test, object):
    """Every value passes this test"""

    def __init__(self):
        super(AcceptAll, self).__init__()
        return

    def why_not(self, globals: Globals, subject: Data) -> str:
        return ''
    pass


class RejectAll(Test, object):
    """No value passes this test"""

    def __init__(self, why: str):
        super(RejectAll, self).__init__()
        if not why:
            raise Exception(f'the truth value of {why!a} is false')
        self.why = why
        return

    def why_not(self, globals: Globals, subject: Data) -> str:
        return self.why
    pass


class And(Test, object):
    """Conjunction of given tests

    The tests are run in series, stopping as soon as one fails."""

    def __init__(self, *tests: Test):
        super(And, self).__init__()
        list(map(type_test(Test), tests))
        self.tests = tests
        return

    def why_not(self, globals: Globals, subject: Data) -> str:
        for test in self.tests:
            reason = test.why_not(globals, subject)
            if reason:
                return reason
        return ''
    pass


class Or(Test, object):
    """Disjunction of given tests

    The tests are run in series, stopping as soon as one succeeds."""

    def __init__(self, *tests: Test):
        super(Or, self).__init__()
        list(map(type_test(Test), tests))
        self.tests = tests
        return

    def why_not(self, globals: Globals, subject: Data) -> str:
        if not self.tests:
            return 'does not pass empty disjunction'
        reasons = []
        for test in self.tests:
            reason = test.why_not(globals, subject)
            if not reason:
                return ''
            reasons.append(reason)
        return '[' + ', '.join(reasons) + ']'

    pass


class Dispatcher(Test, object):
    """Apply a specific test for each key tuple"""

    def __init__(self, key_names: typing.Tuple[str, ...]):
        super(Dispatcher, self).__init__()
        if len(key_names) < 1:
            raise Exception(f'Dispatcher given empty list of key names')
        list(map(type_test(str), key_names))
        self.key_names = key_names
        self.tests = dict()
        return

    def set(self, key_vals: typing.Tuple[str, ...], test: Test):
        """Set the test for the given value tuple"""
        if len(key_vals) != len(self.key_names):
            raise Exception(
                f'{key_vals=!a} does not match length of {self.key_names}')
        if key_vals in self.tests:
            raise Exception(f'multiple tests for {key_vals=!a}')
        self.tests[key_vals] = test
        return

    def why_not(self, globals: Globals, subject: Data) -> str:
        if not isinstance(subject, dict):
            return f'is not a dict'
        if self.key_names[0] not in subject:
            return f'has no {self.key_names[0]}'
        key_vals = (subject[self.key_names[0]],)
        for kn in self.key_names[1:]:
            if kn not in subject:
                return f'has no {kn}'
            key_vals += (subject[kn],)
        if key_vals not in self.tests:
            return f'has unexpected {self.key_names} combination {key_vals}'
        test = self.tests[key_vals]
        return test.why_not(globals, subject)
    pass


class FieldTest(Test, object):
    """Applies given test to field having given name"""

    def __init__(self, field_name: str, field_test: Test, show_name: bool = True):
        super(FieldTest, self).__init__()
        self.field_name = field_name
        if not isinstance(field_test, Test):
            print(f'{field_test=!a} is not a Test')
            assert(False)
        self.field_test = field_test
        self.show_name = show_name
        return

    def why_not(self, globals: Globals, subject: Data) -> str:
        if not isinstance(subject, dict):
            return f'is not a dict'
        if self.field_name not in subject:
            return f'has no {self.field_name} field'
        reason = self.field_test.why_not(globals, subject[self.field_name])
        if reason and self.show_name:
            return self.field_name + ' ' + reason
        return reason
    pass


class FieldsTest(And):
    """Tests a collection of fields"""

    def __init__(self, **fields: Test):
        tests = [FieldTest(field_name, field_test)
                 for field_name, field_test in fields.items()]
        super(FieldsTest, self).__init__(*tests)
        return
    pass


class IterateTest(Test, object):
    """Applies a test to every member of a list, plus optionally one to all at the end"""

    def __init__(self, elt_test: Test, show_elt: bool = False,):
        super(IterateTest, self).__init__()
        self.elt_test = elt_test
        self.show_elt = show_elt
        return

    def why_not(self, globals: Globals, subject: Data) -> str:
        if not isinstance(subject, list):
            return f'is not a list'
        for idx, elt in enumerate(subject):
            reason = self.elt_test.why_not(globals, elt)
            if not reason:
                continue
            if self.show_elt:
                return f'{elt!a} ' + reason
            return f'[{idx}] ' + reason
        return ''
    pass


class TupleTest(Test, object):
    """Applies a sequence of tests to a sequence of values

    The tests are run in series, stopping as soon as one fails"""

    def __init__(self, *tests: Test):
        super(TupleTest, self).__init__()
        list(map(type_test(Test), tests))
        self.tests = tests
        return

    def why_not(self, globals: Globals, subject: Data) -> str:
        if not isinstance(subject, list):
            return f'is not a list'
        if len(subject) != len(self.tests):
            return f' has length {len(subject)} instead of {len(self.tests)}'
        for idx, test in enumerate(self.tests):
            reason = test.why_not(globals, subject[idx])
            if reason:
                return f'[{idx}] ' + reason
        return ''
    pass


class DelayedField(Test, object):
    """Remembers a field value for later testing"""

    def __init__(self, delayer: 'DelayToFields', field_name: str):
        super(DelayedField, self).__init__()
        self.delayer = delayer
        self.field_name = field_name
        return

    def why_not(self, globals: Globals, subject: Data) -> str:
        """Add the value to the list stashed for later testing"""
        val_list = globals[self.field_name]
        if not isinstance(val_list, list):
            return f'malformed test: global {self.field_name} is not a list'
        val_list.append(subject)
        return ''
    pass


class DelayInitializer(Test, object):
    """A Test that initializes the globals used buy a DelayToFields and reports acceptance"""

    def __init__(self, delayer: 'DelayToFields'):
        super(DelayInitializer, self).__init__()
        self.delayer = delayer
        return

    def why_not(self, globals: Globals, subject):
        self.delayer.initialize_globals(globals)
        return ''
    pass


class DelayToFields(Test, object):
    """A test to apply after stashing fields to test.

    For each field, accumulates a list of values
    in a correspondingly-named global.
    As a test, ignores the given subject and instead applies the
    configured fields_test to the record of accumulated value lists.
    """

    def __init__(self, fields_test: Test, *field_names: str):
        super(DelayToFields, self).__init__()
        self.field_names = field_names
        self.fields_test = fields_test
        return

    def initialize_globals(self, globals: Globals):
        """Initialize for a new pass over data"""
        for field_name in self.field_names:
            globals[field_name] = []
        return

    def get_initializer(self):
        """Get a test that accepts the subject and initializes the relevant globals"""
        return DelayInitializer(self)

    def get(self, field_name: str) -> Test:
        """Return a test that adds the value to the list stashed for later evaulation"""
        if field_name not in self.field_names:
            raise Exception(f'{field_name} not in {self.field_names}')
        return DelayedField(self, field_name)

    def why_not(self, globals: Globals, subject: Data) -> str:
        """Test the stashed field values"""
        delayed = dict()
        for field_name in self.field_names:
            delayed[field_name] = globals.get(field_name, None)
        return self.fields_test.why_not(globals, delayed)
    pass


class IntEqual(Test, object):
    """Compares with a given int"""

    def __init__(self, expected: int):
        super(IntEqual, self).__init__()
        type_test(int)(expected)
        self.expected = expected
        return

    def why_not(self, globals: Globals, subject: Data) -> str:
        if not isinstance(subject, int):
            return f'is not a int'
        if subject == self.expected:
            return ''
        return f'is not {self.expected}'
    pass


class StringEqual(Test, object):
    """Compares with a given string"""

    def __init__(self, expected: str):
        super(StringEqual, self).__init__()
        type_test(str)(expected)
        self.expected = expected
        return

    def why_not(self, globals: Globals, subject: Data) -> str:
        if not isinstance(subject, str):
            return f'is not a str'
        if subject == self.expected:
            return ''
        return f'is not {self.expected!a}'
    pass


class RegExp(Test, object):
    """Does a full match against a regular expression"""

    def __init__(self, pattern: str, flags=0):
        super(RegExp, self).__init__()
        self.regexp = re.compile(pattern, flags)
        return

    def why_not(self, globals: Globals, subject: Data) -> str:
        if not isinstance(subject, str):
            return f'is not a str'
        if self.regexp.fullmatch(subject):
            return ''
        return f'does not match {self.regexp.pattern}'
    pass


Digest = typing.Mapping[str, str]  # hash algorithm -> hash value in hex


class DigestTest(Test, object):
    """Tests whether subject (a) has a digest that is in a list of good ones or (b) passes an optional final test"""

    def __init__(self, good_digests_list: typing.Tuple[Digest, ...], or_else: Test = None):
        """good_digests_list is a list of good {alg:hash}"""
        super(DigestTest, self).__init__()
        self.good_digests = dict()
        'map from alg to set of good digests'
        for good_digests in good_digests_list:
            for alg, hash in good_digests.items():
                if alg in self.good_digests:
                    self.good_digests[alg].add(hash)
                else:
                    self.good_digests[alg] = set((hash,))
        self.or_else = or_else
        return

    def why_not(self, globals: Globals, subject: Data) -> str:
        if not isinstance(subject, dict):
            return f'is not a dict'
        if 'Digests' not in subject:
            return f'has no Digests'
        digest_list = subject['Digests']
        if type(digest_list) != list:
            return f'Digests is not a list'
        for idx, subject_digest in enumerate(digest_list):
            if type(subject_digest) != dict:
                return f'Digests[{idx}] is {subject_digest!a}, not a dict'
            if 'AlgorithmId' not in subject_digest:
                return f'digest {idx} has no AlgorithmId'
            alg = subject_digest['AlgorithmId']
            if type(alg) != str:
                return f'Digests[{idx}].AlgorithmId is {alg}, not a str'
            if 'Digest' not in subject_digest:
                return f'digest {idx} has no Digest'
            hash = subject_digest['Digest']
            if type(hash) != str:
                return f'Digests[{idx}].Digest is {hash}, not a str'
            if alg not in self.good_digests:
                continue
            if hash in self.good_digests[alg]:
                return ''
        if not self.or_else:
            return f'has no digest approved by {self.good_digests}'
        reason = self.or_else.why_not(globals, subject)
        if not reason:
            return ''
        return reason + f' and has no digest approved by {self.good_digests}'
    pass


# VisualStudio Code objects to the subscripting but Python accepts it
StrOrRE = typing.Union[str, re.Pattern]


class VariableTest(Test, object):
    """Test whether a given variable has value passing given test"""

    def __init__(self, variable_name: str, unicode_name: StrOrRE, data_test: Test):
        """variable_name and unicode_name are as in the parsed event; data_test applies to VariableData"""
        super(VariableTest, self).__init__()
        self.variable_name = variable_name
        if not(isinstance(unicode_name, str) or isinstance(unicode_name, re.Pattern)):
            raise Exception(
                f'{unicode_name=!a} is neither a str nor an re.Pattern')
        self.unicode_name = unicode_name
        self.data_test = data_test
        return

    def why_not(self, globals: Globals, subject: Data) -> str:
        if not isinstance(subject, dict):
            return 'is not a dict'
        if 'Event' not in subject:
            return 'has no Event field'
        evt = subject['Event']
        if not isinstance(evt, dict):
            return 'Event is not a dict'
        if 'VariableName' not in evt:
            return 'Event has no VariableName field'
        variable_name = evt['VariableName']
        if variable_name != self.variable_name:
            return f'Event.VariableName is {variable_name} rather than {self.variable_name}'
        if 'UnicodeName' not in evt:
            return 'Event has no UnicodeName field'
        unicode_name = evt['UnicodeName']
        if 'VariableData' not in evt:
            return 'Event has no VariableData field'
        if not isinstance(unicode_name, str):
            return 'Event.UnicodeName is not a str'
        variable_data = evt['VariableData']
        if type(self.unicode_name) == str:
            if unicode_name != self.unicode_name:
                return f'Event.UnicodeName is {unicode_name} rather than {self.unicode_name}'
        elif not self.unicode_name.fullmatch(unicode_name):
            return f'Event.UnicodeName, {unicode_name}, does not match {self.unicode_name.pattern}'
        return self.data_test.why_not(globals, variable_data)
    pass


class VariableDispatch(FieldTest):
    """Do a specific test for each variable"""

    def __init__(self):
        self.vd = Dispatcher(('VariableName', 'UnicodeName'))
        super(VariableDispatch, self).__init__('Event', self.vd)
        return

    def set(self, variable_name: str, unicode_name: str, data_test: Test):
        """Define the test for a specific variable"""
        self.vd.set((variable_name, unicode_name),
                    FieldTest('VariableData', data_test))
        return
    pass


class SignatureTest(And):
    """Compares to a particular signature"""

    def __init__(self, owner: str, data: str):
        """owner is SignatureOwner, data is SignatureData"""
        super(SignatureTest, self).__init__(
            FieldTest('SignatureOwner', StringEqual(owner)),
            FieldTest('SignatureData', StringEqual(data))
        )
        return
    pass


class SignatureSetMember(Or):
    """Tests for membership in the given list of signatures"""

    def __init__(self, sigs):
        tests = [SignatureTest(sig['owner'], sig['data']) for sig in sigs]
        super(SignatureSetMember, self).__init__(*tests)
        return
    pass


class KeySubset(IterateTest):
    def __init__(self, sig_type: str, keys):
        super(KeySubset, self).__init__(And(
            FieldTest('SignatureType', StringEqual(sig_type)),
            FieldTest('Keys', IterateTest(SignatureSetMember(keys)))))
        return
    pass


class DeficientQuote(Exception):
    """Identifies a problem with the actual PCR_Contents"""

    def __init__(self, reason):
        super(DeficientQuote, self).__init__()
        self.reason = reason
        return

    def get_reason(self) -> str:
        return self.reason

    pass


class PCRs_Test(FieldTest, object):
    """PCR_Test checks whether expected contents equal given (quoted) contents"""

    def __init__(self, care: typing.Mapping[str, typing.Iterable[int]], got_pcrs: PCR_Contents):
        """initialize with contents gotten from agent and identification of which matter

        care maps hash name to list of PCR index.
        got_pcrs maps hash name to map from PCR index (as decimal string)
        to hash value (as int)."""
        type_test(dict)(care)
        if not isinstance(got_pcrs, dict):
            raise DeficientQuote('got_pcrs is not a dict')
        digest_tests = []
        for hash_name, pcr_indices in care.items():
            type_test(str)(hash_name)
            type_test(list)(pcr_indices)
            if hash_name not in got_pcrs:
                raise DeficientQuote(f'no {hash_name} hashes')
            got_by_index = got_pcrs[hash_name]
            index_tests = []
            for index in pcr_indices:
                type_test(int)(index)
                index_s = str(index)
                if index_s not in got_by_index:
                    raise DeficientQuote(f'PCR {index} got no {hash_name}')
                got_val = got_by_index[index_s]
                if not isinstance(got_val, int):
                    raise DeficientQuote(
                        f'PCR {index} digest {hash_name} is not an int')
                index_tests.append(FieldTest(index_s, IntEqual(got_val)))
            digest_tests.append(FieldTest(hash_name, And(*index_tests)))
        pcrs_test = And(*digest_tests)
        super(PCRs_Test, self).__init__('pcrs', pcrs_test)
        return
