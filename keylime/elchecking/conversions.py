#!/usr/bin/env python3

import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import typing


def bin_to_json(bin: bytes, consume: typing.Any) -> None:
    """Parse, enrich, and use an eventlog.

    Given a binary eventlog as a Python bytes, parse and enrich then use.
    `consume` is given the Python data structure that results from reading
    then enriching.
    The current implementation deliberately uses files and leaks them when
    something goes wrong, to aid debugging.
    At some future level of development we should probably use files much less,
    and remove them even in the case of failure, or not use files at all.
    """
    random.seed()
    while True:
        temp_name = os.path.join(os.getcwd(), '.klcvt', str(
            random.randint(1000000, 9999999)))
        try:
            os.makedirs(temp_name)
        except FileExistsError:
            continue
        print(f'Working in {temp_name}', file=sys.stderr)
        break
    parser_commit = 'dc0bf809d09ec263754d6625f5653e235856cb45'
    temp_bin_name = os.path.join(temp_name, 'bin')
    temp_parsed_name = os.path.join(temp_name, 'parsed.yaml')
    temp_enriched_name = os.path.join(temp_name, 'enriched.json')
    with open(temp_bin_name, 'wb') as temp_bin:
        temp_bin.write(bin)
    with open(temp_parsed_name, 'wt') as temp_parsed:
        p1 = subprocess.Popen(
            ['docker', 'run', '--rm', '-v', f'{temp_bin_name}:/binlog',
                f'9.41.33.175/intel-tpm2-tss:{parser_commit}', 'tpm2_eventlog', '/binlog'],
            stdin=subprocess.DEVNULL,
            stdout=temp_parsed,
            stderr=subprocess.PIPE)
        try:
            stdouterr1 = p1.communicate(timeout=100)
        except subprocess.TimeoutExpired:
            raise Exception('parse took too long')
        if p1.returncode != 0:
            raise Exception(
                f'parse returned code {p1.returncode}, {temp_name=}, stderr={stdouterr1[1]!a}')
    with open(temp_parsed_name, 'rt') as temp_parsed:
        with open(temp_enriched_name, 'wt') as temp_enriched:
            p2 = subprocess.Popen(
                ['docker', 'run', '--rm', '-i',
                    f'9.41.33.175/intel-tpm2-tss:{parser_commit}', '/enrich.py', '-o', 'json'],
                stdin=temp_parsed,
                stdout=temp_enriched,
                stderr=subprocess.PIPE)
            try:
                stdouterr2 = p2.communicate(timeout=100)
            except subprocess.TimeoutExpired:
                raise Exception('enrich took too long')
            if p2.returncode != 0:
                raise Exception(
                    f'enrich returned code {p2.returncode}, {temp_name=}, stderr={stdouterr2[1]!a}')
    with open(temp_enriched_name, 'rt') as temp_enriched:
        as_json = temp_enriched.read()
    as_py = json.loads(as_json)
    consume(as_py)
    shutil.rmtree(temp_name)
    return


if __name__ == '__main__':
    import sys
    bin_name = sys.argv[1]
    with open(bin_name, 'rb') as bin_file:
        bin = bin_file.read()
        bin_to_json(bin,
                    lambda data: print(json.dumps(data, sort_keys=True, indent=4)))
