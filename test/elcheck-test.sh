#!/bin/bash
#Usage: $0

# This will exercise eventlog checking, applying the nextgen2 policy
# and the intended state in `../test-data/elcheck-test-params.json` to
# `../test-data/pok1-qz1-sr1-rk048-s03-secure-boot-201123-eventlog.bin`
# and `../test-data/elcheck-test-pcrs.json` .

# This script also tests the nextgen2-ignore-pcrs policy by using the
# same intended state and eventlog but bogus PCR contents.

# This script also tests the accept-all policy by providing a bogus
# eventlog as well as bogus PCR contents.


cd $(dirname $0)
cd ..
export PYTHONPATH=.:${PYTHONPATH}
python3 -m keylime.elchecking nextgen2 test-data/elcheck-test-params.json test-data/elcheck-test-pcrs.json test-data/pok1-qz1-sr1-rk048-s03-secure-boot-201123-eventlog.bin
python3 -m keylime.elchecking nextgen2-ignore-pcrs test-data/elcheck-test-params.json test-data/elcheck-test-params.json test-data/pok1-qz1-sr1-rk048-s03-secure-boot-201123-eventlog.bin
python3 -m keylime.elchecking accept-all test-data/elcheck-test-params.json test-data/elcheck-test-params.json test-data/elcheck-test-params.json
