#!/usr/bin/env python3

import json
import os
import random
import shutil
import subprocess
import sys
import tempfile

# Given a binary eventlog as a Python bytes, parse and enrich.
# Return the Python data structure that results from reading the enriched.
# The current implementation deliberately uses files and leaks them when
# something goes wrong, to aid debugging.
# At some future level of development we should probably use files much less,
# and remove them even in the case of failure, or not use files at all.
def bin_to_json(bin):
    random.seed()
    while True:
        temp_name = os.path.join(os.getcwd(), '.klcvt', str(random.randint(1000000,9999999)))
        try:
            os.makedirs(temp_name)
        except FileExistsError:
            continue
        print(f'Working in {temp_name}', file=sys.stderr)
        break
    temp_bin_name = os.path.join(temp_name, 'bin')
    temp_parsed_name = os.path.join(temp_name, 'parsed.yaml')
    temp_enriched_name = os.path.join(temp_name, 'enriched.json')
    with open(temp_bin_name, 'wb') as temp_bin:
        temp_bin.write(bin)
    with open(temp_parsed_name, 'wt') as temp_parsed:
        p1 = subprocess.Popen(
            ['docker', 'run', '--rm', '-v', f'{temp_bin_name}:/binlog', '9.41.33.175/intel-tpm2-tss:ecc94a9e324bab0f5f95dfba8149b48c392c1036', 'tpm2_eventlog', '/binlog'],
            stdin=subprocess.DEVNULL,
            stdout=temp_parsed,
            stderr=subprocess.PIPE)
        try:
            stdouterr1 = p1.communicate(timeout=100)
        except subprocess.TimeoutExpired:
            raise Exception('parse took too long')
        if p1.returncode != 0:
            raise Exception(f'parse returned code {p1.returncode}, {temp_name=}, stderr={stdouterr1[1]!a}')
    with open(temp_parsed_name, 'rt') as temp_parsed:
        with open(temp_enriched_name, 'wt') as temp_enriched:
            p2 = subprocess.Popen(
                ['docker', 'run', '--rm', '-i', '9.41.33.175/intel-tpm2-tss:98b5fc51aa1abefedc5de32c772099a959f42212', '/enrich.py', '-o', 'json'],
                stdin=temp_parsed,
                stdout=temp_enriched,
                stderr=subprocess.PIPE)
            try:
                stdouterr2 = p2.communicate(timeout=100)
            except subprocess.TimeoutExpired:
                raise Exception('enrich took too long')
            if p2.returncode != 0:
                raise Exception(f'enrich returned code {p2.returncode}, {temp_name=}, stderr={stdouterr2[1]!a}')
    with open(temp_enriched_name, 'rt') as temp_enriched:
        as_json = temp_enriched.read()
    as_py = json.loads(as_json)
    shutil.rmtree(temp_name)
    return as_py
    
if __name__ == '__main__':
    import sys
    bin_name = sys.argv[1]
    with open(bin_name, 'rb') as bin_file:
        bin = bin_file.read()
        as_json = bin_to_json(bin)
    print(json.dumps(as_json, sort_keys=True, indent=4))
