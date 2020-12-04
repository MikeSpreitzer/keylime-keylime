import argparse
import json
import os
import sys
from . import policies

# This main module is just for command-line based testing.
# It implements a command to do one test.
# Invoke it with `python3 -m $packagename`, for some value of
# `$packagename` that works with your `$PYTHONPATH`.

parser = argparse.ArgumentParser()
parser.add_argument('policy_name', choices=policies.get_policies())
parser.add_argument('params_file', type=argparse.FileType('rt'))
parser.add_argument(
    'eventlog_file', type=argparse.FileType('rb'), default=sys.stdin)
args = parser.parse_args()
params_str = args.params_file.read()
params = json.loads(params_str)
test = policies.compile(args.policy_name, params)
elbin = args.eventlog_file.read()
why_fails = policies.convert_and_test(elbin, test)
if why_fails:
    print(why_fails, file=sys.stderr)
    sys.exit(10)
print('AOK')
