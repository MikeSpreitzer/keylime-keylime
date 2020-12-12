import re

from . import policies
from . import conversions
from . import tests

# NextGen2 is an eventlog-checking policy that aims to establish the following:
# - an allowed combination of kernel, kernel command line, and initrd was booted,
# - all the PK, KEK, db, and MoK keys are allowed ones, and
# - all the code that was loaded during boot is allowed.

# This policy expects to find the following entries in params.
# s_crtm - list of allowed digest for PCR 0 event type EV_S_CRTM_VERSION.
# post_code - list of allowed digest for PCR 0 event type EV_POST_CODE
# pk - list of allowed PK keys
# kek - list of allowed KEK keys
# db - list of allowed db keys
# device_drivers - list of allowed digests for firmware from devices
#   (appears in PCR 2 event type EV_EFI_BOOT_SERVICES_DRIVER)
# shim - list of allowed digests for shim (PCR 4 EV_EFI_BOOT_SERVICES_APPLICATION)
# grub - list of allowed digests for grub (PCR 4 EV_EFI_BOOT_SERVICES_APPLICATION)
# moklist - list of allowed digests of MoKList (PCR 14 EV_IPL)
# runs - list of allowed {
#   kernel: {name: string for event.Event in PCR 9 EV_IPL, digest: digest for PCR 4 EV_EFI_BOOT_SERVICES_APPLICATION},
#   kernel_cmdline: regex for event.Event,
#   initrd: string for event.Event (PCR 9 EV_IPL) }
# A digest is a map from hash-algorithm-name (sha1 or sha256) to hex hash value.
# A key is {owner: UUID, data: hex}.


class NextGen2(policies.Policy):
    def __init__(self):
        super(NextGen2, self).__init__()
        return

    def compile(self, params):
        for req in ('s_crtm', 'post_code', 'pk', 'kek', 'db', 'device_drivers',
                    'shim', 'grub', 'runs'):
            if req not in params:
                return f'params lacks {req}'

        dispatcher = tests.Dispatcher(('PCRIndex', 'EventType'))
        dispatcher.set((0, 'EV_NO_ACTION'), tests.AcceptAll())
        dispatcher.set((0, 'EV_S_CRTM_VERSION'),
                       tests.DigestTest(params['s_crtm']))
        dispatcher.set((0, 'EV_POST_CODE'),
                       tests.DigestTest(params['post_code']))
        vd = tests.VariableDispatch()
        vd.set('61dfe48b-ca93-d211-aa0d-00e098032b8c', 'SecureBoot',
               tests.FieldTest('Enabled', tests.StringEqual('Yes')))
        vd.set('61dfe48b-ca93-d211-aa0d-00e098032b8c', 'PK',
               tests.KeySubset('a5c059a1-94e4-4aa7-87b5-ab155c2bf072', params['pk']))
        vd.set('61dfe48b-ca93-d211-aa0d-00e098032b8c', 'KEK',
               tests.KeySubset('a5c059a1-94e4-4aa7-87b5-ab155c2bf072', params['kek']))
        vd.set('cbb219d7-3a3d-9645-a3bc-dad00e67656f', 'db',
               tests.KeySubset('a5c059a1-94e4-4aa7-87b5-ab155c2bf072', params['db']))
        vd.set('cbb219d7-3a3d-9645-a3bc-dad00e67656f', 'dbx', tests.AcceptAll())
        dispatcher.set((7, 'EV_EFI_VARIABLE_DRIVER_CONFIG'), vd)
        for pcr in range(8):
            dispatcher.set((pcr, 'EV_SEPARATOR'), tests.AcceptAll())
        dispatcher.set((2, 'EV_EFI_BOOT_SERVICES_DRIVER'),
                       tests.DigestTest(params['device_drivers']))
        dispatcher.set((1, 'EV_EFI_VARIABLE_BOOT'), tests.VariableTest(
            '61dfe48b-ca93-d211-aa0d-00e098032b8c',
            re.compile('BootOrder|Boot[0-9a-fA-F]+'),
            tests.AcceptAll()))
        dispatcher.set((7, 'EV_EFI_VARIABLE_AUTHORITY'), tests.AcceptAll())
        run = tests.DelayToFields(
            tests.Or(*[tests.FieldsTest(
                kernel_cmdline=tests.TupleTest(tests.RegExp(
                    'kernel_cmdline: ' + run['kernel_cmdline'])),
                bsa=tests.TupleTest(tests.DigestTest(
                    [run['kernel']['digest']])),
                ipl9=tests.TupleTest(
                    tests.StringEqual(run['kernel']['name']),
                    tests.StringEqual(run['initrd']))
            ) for run in params['runs']]),
            'kernel_cmdline', 'bsa', 'ipl9')
        shimgrubtest = tests.DigestTest(params['shim'] + params['grub'],
                                        run.get('bsa'))
        dispatcher.set((4, 'EV_EFI_BOOT_SERVICES_APPLICATION'),
                       shimgrubtest)
        dispatcher.set((14, 'EV_IPL'),
                       tests.DigestTest(params['moklist']))
        dispatcher.set((8, 'EV_IPL'), tests.FieldTest('Event', tests.FieldTest('String', tests.Or(
            tests.RegExp('grub_cmd: .*', re.DOTALL),
            tests.And(
                tests.RegExp('kernel_cmdline: .*'),
                run.get('kernel_cmdline'))
        ))))
        dispatcher.set((9, 'EV_IPL'), tests.FieldTest('Event', tests.FieldTest('String', tests.Or(
            tests.RegExp(r'\(tftp,.*\).*'),
            tests.RegExp(r'/boot/grub.*'),
            run.get('ipl9')))))
        event_test = tests.IterateTest(
            dispatcher, show_elt=True,
            initial_test=run.get_reset(), final_test=run)
        return tests.FieldTest('events', event_test, show_name=False)

    pass


policies.register('nextgen2', NextGen2())
