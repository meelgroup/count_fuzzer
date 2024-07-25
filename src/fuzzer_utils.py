#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Short description.

Author:     Anna L.D. Latour
Authors:    [Anna L.D. Latour, And another one, etc]
Contact:    a.l.d.latour@tudelft.nl
Date:       2024-07-06
Maintainer: Anna L.D. Latour
Version:    0.0.1
Credits:    [One developer, And another one, etc]
Copyright:  (C) 2024, Anna L.D. Latour
License:    GPLv3
    This program is free software; you can redistribute it and/or
    modify it under the terms of the GNU General Public License
    as published by the Free Software Foundation; version 3
    of the License.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program; if not, write to the Free Software
    Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
    02110-1301, USA.
    
Description: Long description.

"""

from collections import namedtuple
from decimal import Decimal
from functools import partial
from gmpy2 import mpz, log10, mpfr
import json
import os
import re
import resource
import subprocess

import report_manager as rm

Counter = namedtuple("Counter", "name path config exact",
                     defaults=[None, None, None, True])
Generator = namedtuple("Generator", "name path config",
                       defaults=[None, None, None])
Preprocessor = namedtuple("Preprocessor", "name path config",
                          defaults=[None, None, None])
DeltaDebugger = namedtuple("DeltaDebugger", "name path config",
                           defaults=[None, None, None])

Count = namedtuple("Count", "solver preproc count", defaults=[None, None, -1])

# The following regular expressions are all based on the information in
# https://mccompetition.org/assets/files/mccomp_format_24.pdf
# TODO: add support for alternative precisions
# TODO: add support for all value formats
sat_pat = re.compile(r'\s*s\s+(?P<satisfiability>(UN)?((SATISFIABLE)|(KNOWN)))\s*', re.DOTALL)
type_pat = re.compile(r'\s*c\s+s\s+type\s+(?P<problem_type>((w)|(p)|(pw))?mc)\s*', re.DOTALL)
est_pat = re.compile(r'\s*c\s+s\s+(?P<est_type>(neg)?log10-estimate)\s+(?P<est_val>[\d.e\-inf]+)\s*', re.DOTALL)
count_pat = re.compile(r'\s*c\s+s\s+(?P<counter_type>((exact)|(approximate)))\s+(?P<precision>((arb)|(single)|(double)|(quadruple)))\s+(?P<notation>((log10)|(float)|(prec-sci)|(int)|(frac)))\s+(?P<value>((inf)|(\d+\.*\d*)))\s*', re.DOTALL)
# TODO: add functionality for pac guarantees

# REGEX for parsing verifier output
trace_pat = re.compile(r'reading from \"(?P<trace_file>.*\.trace)\"...done', re.DOTALL)
verified_count_pat = re.compile(r'root model count: (?P<verified_count>\d+)\s*', re.DOTALL)

def fstr(template, **kwargs):
    return eval(f"f'{template}'", kwargs)


def set_limits(t):
    """

    :param t:
    :return:
    """
    # Set maximum CPU time to 1 second in child process, after fork() but before exec()
    rm.log_message(f"Setting resource limit in child (pid {os.getpid()})")
    resource.setrlimit(resource.RLIMIT_CPU, (t, t))


def run(command: str,
        dir: str,
        verbosity=1,
        timeout=10):
    if verbosity >= 2:
        rm.log_message(f'--> Executing: {" ".join(command)} in dir {dir}')
    if verbosity >= 3:
        rm.log_message(f'CPU limit of parent (pid {os.getpid()}): {resource.getrlimit(resource.RLIMIT_CPU)}')

    subprocess.call(['echo', '$STAREXEC_MAX_MEM'])
    this_dir = os.path.dirname(os.path.realpath(__file__))
    os.chdir(dir)
    p = subprocess.Popen(command, stderr=subprocess.STDOUT,
                         stdout=subprocess.PIPE, universal_newlines=True,
                         preexec_fn=partial(set_limits, timeout))
    os.chdir(this_dir)

    console_output, err = p.communicate()
    if verbosity >= 3:
        rm.log_message(
            f"CPU limit of parent (pid {os.getpid()}) after child finished executing: {resource.getrlimit(resource.RLIMIT_CPU)}")
    return console_output, err


def log10cnt(cnt: str):
    """

    Source: adapted from Johannes' parse_counts_util.py.

    :param cnt:
    :return:
    """
    try:
        if 'inf' in cnt:
            log10_value = str(mpfr('nan'))
        elif 'e' in cnt:
            cnt = Decimal(cnt)
            log10_value = str(log10(mpz(cnt)))
        else:
            cnt = Decimal(cnt)
            log10_value = str(log10(mpz(cnt)))
    except ValueError as _:
        print(f"ValueError: {cnt}")
        log10_value = str(mpfr('nan'))
    return log10_value


def get_random_seed(seed):
    if seed is None:
        b = os.urandom(8)
        seed = int.from_bytes(b)
    rm.log_message(f"Using seed: {seed}")
    return seed


def get_type_number(projected=False, weighted=False) -> str:
    ty = "0"
    if projected and not weighted: ty = "1"
    if not projected and weighted: ty = "2"
    if projected and weighted: ty = "3"
    return ty


def get_extension(projected=False, weighted=False) -> str:
    if not projected and not weighted:
        return "cnf"
    if projected and not weighted:
        return "pcnf"
    if weighted and not projected:
        return "wcnf"
    if weighted and projected:
        return "pwcnf"


def parse_counters(counter_config_file: str):
    """Read counter configurations from a given json file.

    Parameters:
        counter_config_file (str): Path to json file with counter configuration
    """
    counter_dict = json.load(open(counter_config_file))
    counters = [Counter(name, counter_dict[name]["path"], counter_dict[name]["config"], bool(counter_dict[name]["exact"]))
                for name in counter_dict]
    assert len(counters) > 1, "Aborting. Please specify at least two counters."
    return counters


def parse_generators(generator_config_file: str):
    """Read instance generators from a given json file..

    Parameters:
        generator_config_file (str): Path to json file with generator configuration
    """
    gen_dict = json.load(open(generator_config_file))
    generators = [Generator(name, gen_dict[name]["path"], gen_dict[name]["config"]) for name in gen_dict]
    assert generators, "Aborting. Please specify at least one instance generator."
    return generators


def parse_preprocessors(preprocessor_config_file: str):
    """Append preprocessors from a given json file with the preprocessor configurations.

    Parameters:
        preprocessor_config_file (str): Path to json file with preprocessor configuration
    """
    preprocessors = []
    if preprocessor_config_file is not None:
        prep_dict = json.load(open(preprocessor_config_file))
        preprocessors = [Preprocessor(name, prep_dict[name]["path"], prep_dict[name]["config"]) for name in prep_dict]
    return preprocessors


def parse_output(
        counter_output: str,
        counter: Counter,
        path_to_instance: str,
        timed_out=False,
        verbosity=1) -> (bool, dict):

    result = {
        'counter': counter.name,
        'instance': path_to_instance,
        'satisfiability': None,
        'problem_type': None,
        'est_type': None,
        'est_val': None,
        'counter_type': None,
        'count_precision': None,
        'count_notation': None,
        'count_value': None,
        'error': False,
        'timed_out': timed_out
    }

    if verbosity >= 3:
        rm.log_message("OUTPUT")

    for l in counter_output.split("\n"):
        l = l.strip()

        # Print each line of the counter's output, if verbosity level is high enough
        if verbosity >= 3:
            rm.log_message(l)

        # Skip all optional information:
        if l.startswith('c o'):
            continue

        # Catch some basic errors:
        if "Assertion " in l and "failed" in l:
            rm.log_message(f"Counter {counter.name} reports assertion fail: {l}")  # TODO: come up with better error message
            result['error']: True
            return False, result
        if "ERROR Memory out!" in l:
            if verbosity >= 2:
                rm.log_message(f"Counter {counter.name} ran out of memory on {path_to_instance}.")
            result['error']: True
            return False, result
        if "ERROR" in l:  # TODO: check if this is a reliable way to detect errors
            if verbosity >= 2:
                rm.log_message(f"ERROR found in counter {counter.name} on instance {path_to_instance}: {l}")
            result['error']: True
            return False, result

        # Process lines to retrieve relevant data for reporting and sanity checks
        m = re.match(sat_pat, l)
        if m is not None:
            result['satisfiability'] = m.group("satisfiability")
            continue
        m = re.match(type_pat, l)
        if m is not None:
            result['problem_type'] = m.group("problem_type")
            continue
        m = re.match(est_pat, l)
        if m is not None:
            result['est_type'] = m.group("est_type")
            result['est_val'] = m.group("est_val")  # TODO: check what should happen if neglog10
            continue
        m = re.match(count_pat, l)
        if m is not None:
            result['counter_type'] = m.group("counter_type")
            result['count_precision'] = m.group("precision")
            result['count_notation'] = m.group("notation")
            result['count_value'] = m.group("value")  # TODO: recompute for uniform reporting

    return True, result


def check_counts(counts: dict) -> bool:
    # TODO: Add functionality for approximate counters
    # TODO: Add functionality for weighted & projected counters

    # If all counts agree, return True
    if len(set(counts.values())) == 1:
        return True
    return False


def parse_verifier_output(output_file: str, timed_out=bool) -> dict():
    result = {'verified': False,
              'satisfiability': None,
              'timed_out': timed_out,
              'error': None,
              'no_root_claim': False,
              'verified_count': None}
    with open(output_file, 'r') as out_file:
        for l in out_file.readlines():
            l = l.strip()

            m = re.match(trace_pat, l)
            if m is not None:
                result['trace_file'] = m.group("trace_file")
                continue
            m = re.match(verified_count_pat, l)
            if m is not None:
                result['verified_count'] = m.group("verified_count")
                result['satisfiability'] = 'SATISFIABLE'
                continue

            if 'proofs verified' in l:
                result['verified'] = True
                continue
            if 'IntegrityError(NoRootClaim)' in l:        # I think this means that the instance is UNSAT
                result['no_root_claim'] = True
                result['satisfiability'] = 'UNSATISFIABLE'
                continue
            if 'error' in l.lower():
                result['error']: l
                return False, result

    return True, result