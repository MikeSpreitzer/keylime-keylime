#!/bin/bash
#Usage: $0
#.. with github.ibm.com/k8s4g/intel-tpm2-tss appearing at ../../.. .

# This will exercise eventlog checking, applying the nextgen2 policy
# and the intended state in `test-params.json` to
# `gen2/pok1-qz1-sr1-rk048-s03/secure-boot/201123-eventlog.bin`.

cd $(dirname $0)
export PYTHONPATH=.:${PYTHONPATH}
python3 -m keylime.elchecking nextgen2 test-params.json ../../../github.ibm.com/k8s4g/intel-tpm2-tss/data/gen2/pok1-qz1-sr1-rk048-s03/secure-boot/201123-eventlog.bin
