#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2026  Mate Soos
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; version 2
# of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.

# Minimizes a ganak command by stripping options that don't affect the count.

import sys
import subprocess


KEEP_OPTS = {"--mode", "--verb"}
TOLERANCE = 0.001  # 0.1%


def run_and_get_count(cmd):
    print(f"    Running: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True,
                                text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return None

    output = result.stdout + result.stderr
    for line in output.splitlines():
        line = line.strip()
        num = extract_count(line)
        if num is not None:
            return num
    return None


def extract_count(line):
    if line.startswith("s mc") or line.startswith("s pmc"):
        return float(line.split()[2])
    if "c s exact quadruple float interval [" in line:
        parts = line.split()
        return (float(parts[7]) + float(parts[8])) / 2.0
    if "c s exact quadruple float" in line:
        return float(line.split()[5])
    if "c s exact arb frac" in line:
        parts = line.split()
        if parts[5] == "[":
            return (float(parts[6]) + float(parts[7])) / 2.0
        frac = parts[5].split("/")
        return float(frac[0]) if len(frac) < 2 else float(frac[0]) / float(frac[1])
    if "c s exact arb float" in line or "c s exact arb int" in line:
        return float(line.split()[5])
    if "c s exact double prec-sci" in line or "s exact double prec-sci" in line:
        return float(line.split()[5])
    if "c s approx arb int" in line:
        return float(line.split()[5])
    return None


def counts_close(a, b):
    if a is None or b is None:
        return False
    if b == 0.0:
        return abs(a) < 1e-10
    return abs(a - b) / abs(b) <= TOLERANCE


def parse_command(cmd_str):
    """Returns (executable, [(opt, val_or_None), ...], input_file)."""
    tokens = cmd_str.split()
    executable = tokens[0]
    input_file = tokens[-1]

    options = []
    i = 1
    while i < len(tokens) - 1:
        tok = tokens[i]
        if tok.startswith("--"):
            nxt = tokens[i + 1] if i + 1 < len(tokens) - 1 else None
            if nxt is not None and not nxt.startswith("--"):
                options.append((tok, nxt))
                i += 2
            else:
                options.append((tok, None))
                i += 1
        else:
            i += 1

    return executable, options, input_file


def build_command(executable, options, input_file):
    parts = [executable]
    for opt, val in options:
        parts.append(opt)
        if val is not None:
            parts.append(val)
    parts.append(input_file)
    return " ".join(parts)


def minimize(cmd_str):
    executable, options, input_file = parse_command(cmd_str)

    print(f"Original command:\n  {cmd_str}\n")
    original_count = run_and_get_count(cmd_str)
    if original_count is None:
        print("ERROR: could not extract count from original command.")
        sys.exit(1)
    print(f"Original count: {original_count}\n")

    current = list(options)

    # First pass: remove unnecessary options
    for opt, val in options:
        if opt in KEEP_OPTS:
            continue

        trial = [(o, v) for o, v in current if o != opt]
        trial_cmd = build_command(executable, trial, input_file)

        label = f"{opt} {val}" if val is not None else opt
        print(f"Trying without {label} ...")
        count = run_and_get_count(trial_cmd)

        if counts_close(count, original_count):
            print(f"  -> same count ({count}), dropping {label}\n")
            current = trial
        else:
            print(f"  -> different count ({count}), keeping {label}\n")

    # Second pass: try to simplify remaining options
    # Try to set --td 0 if it's present
    td_idx = None
    for i, (opt, val) in enumerate(current):
        if opt == "--td":
            td_idx = i
            break

    if td_idx is not None and current[td_idx][1] != "0":
        print("Trying to set --td 0 ...")
        trial = current.copy()
        trial[td_idx] = ("--td", "0")
        trial_cmd = build_command(executable, trial, input_file)
        count = run_and_get_count(trial_cmd)
        if counts_close(count, original_count):
            print(f"  -> same count ({count}), setting --td 0\n")
            current = trial
        else:
            print(f"  -> different count ({count}), keeping original --td value\n")

    # Try to set --arjun 0 if it's present
    arjun_idx = None
    for i, (opt, val) in enumerate(current):
        if opt == "--arjun":
            arjun_idx = i
            break

    if arjun_idx is not None and current[arjun_idx][1] != "0":
        print("Trying to set --arjun 0 ...")
        trial = current.copy()
        trial[arjun_idx] = ("--arjun", "0")
        trial_cmd = build_command(executable, trial, input_file)
        count = run_and_get_count(trial_cmd)
        if counts_close(count, original_count):
            print(f"  -> same count ({count}), setting --arjun 0\n")
            current = trial
        else:
            print(f"  -> different count ({count}), keeping original --arjun value\n")

    # Try to set --threads 1 --debugthreads 1 if threads is present
    threads_idx = None
    debugthreads_idx = None
    for i, (opt, val) in enumerate(current):
        if opt == "--threads":
            threads_idx = i
        if opt == "--debugthreads":
            debugthreads_idx = i

    if threads_idx is not None:
        need_change = current[threads_idx][1] != "1"
        if debugthreads_idx is not None:
            need_change = need_change or current[debugthreads_idx][1] != "1"
        else:
            # debugthreads not present, need to add it
            need_change = True

        if need_change:
            print("Trying to set --threads 1 --debugthreads 1 ...")
            trial = current.copy()
            trial[threads_idx] = ("--threads", "1")
            if debugthreads_idx is not None:
                trial[debugthreads_idx] = ("--debugthreads", "1")
            else:
                # Insert --debugthreads 1 right after --threads
                trial.insert(threads_idx + 1, ("--debugthreads", "1"))

            trial_cmd = build_command(executable, trial, input_file)
            count = run_and_get_count(trial_cmd)
            if counts_close(count, original_count):
                print(f"  -> same count ({count}), setting --threads 1 --debugthreads 1\n")
                current = trial
            else:
                print(f"  -> different count ({count}), keeping original thread settings\n")

    final_cmd = build_command(executable, current, input_file)
    print("Minimized command:")
    print(f"  {final_cmd}")
    return final_cmd


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: minimize.py '<full ganak command>'")
        sys.exit(1)
    minimize(sys.argv[1])
