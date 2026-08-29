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

# Minimizes a crashing ganak command by stripping options that don't affect
# the non-zero exit code (i.e., the crash still occurs).

import sys
import subprocess


KEEP_OPTS = {"--mode"}


def run_and_check_crash(cmd):
    print(f"    Running: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True,
                                text=True, timeout=20)
    except subprocess.TimeoutExpired:
        print("    -> timeout (treating as no crash)")
        return False
    crashed = result.returncode != 0
    print(f"    -> exit code {result.returncode} ({'crash' if crashed else 'no crash'})")
    return crashed


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
    if not run_and_check_crash(cmd_str):
        print("ERROR: original command does not crash (exit code 0).")
        sys.exit(1)
    print("Original command crashes. Starting minimization...\n")

    current = list(options)

    # First pass: remove unnecessary options
    for opt, val in options:
        if opt in KEEP_OPTS:
            continue

        trial = [(o, v) for o, v in current if o != opt]
        trial_cmd = build_command(executable, trial, input_file)

        label = f"{opt} {val}" if val is not None else opt
        print(f"Trying without {label} ...")

        if run_and_check_crash(trial_cmd):
            print(f"  -> still crashes, dropping {label}\n")
            current = trial
        else:
            print(f"  -> no longer crashes, keeping {label}\n")

    # Second pass: try to simplify remaining options
    # Try to set/add --td 0
    td_idx = None
    for i, (opt, val) in enumerate(current):
        if opt == "--td":
            td_idx = i
            break

    if td_idx is not None:
        # --td is present, try setting it to 0 if it isn't already
        if current[td_idx][1] != "0":
            print("Trying to set --td 0 ...")
            trial = current.copy()
            trial[td_idx] = ("--td", "0")
            trial_cmd = build_command(executable, trial, input_file)
            if run_and_check_crash(trial_cmd):
                print("  -> still crashes, setting --td 0\n")
                current = trial
            else:
                print("  -> no longer crashes, keeping original --td value\n")
    else:
        # --td is not present, try adding --td 0
        print("Trying to add --td 0 ...")
        trial = current.copy()
        trial.append(("--td", "0"))
        trial_cmd = build_command(executable, trial, input_file)
        if run_and_check_crash(trial_cmd):
            print("  -> still crashes, adding --td 0\n")
            current = trial
        else:
            print("  -> no longer crashes, not adding --td 0\n")

    # Try to set/add --arjun 0
    arjun_idx = None
    for i, (opt, val) in enumerate(current):
        if opt == "--arjun":
            arjun_idx = i
            break

    if arjun_idx is not None:
        # --arjun is present, try setting it to 0 if it isn't already
        if current[arjun_idx][1] != "0":
            print("Trying to set --arjun 0 ...")
            trial = current.copy()
            trial[arjun_idx] = ("--arjun", "0")
            trial_cmd = build_command(executable, trial, input_file)
            if run_and_check_crash(trial_cmd):
                print("  -> still crashes, setting --arjun 0\n")
                current = trial
            else:
                print("  -> no longer crashes, keeping original --arjun value\n")
    else:
        # --arjun is not present, try adding --arjun 0
        print("Trying to add --arjun 0 ...")
        trial = current.copy()
        trial.append(("--arjun", "0"))
        trial_cmd = build_command(executable, trial, input_file)
        if run_and_check_crash(trial_cmd):
            print("  -> still crashes, adding --arjun 0\n")
            current = trial
        else:
            print("  -> no longer crashes, not adding --arjun 0\n")

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
            if run_and_check_crash(trial_cmd):
                print("  -> still crashes, setting --threads 1 --debugthreads 1\n")
                current = trial
            else:
                print("  -> no longer crashes, keeping original thread settings\n")

    final_cmd = build_command(executable, current, input_file)
    print("Minimized command:")
    print(f"  {final_cmd}")
    return final_cmd


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: crash_minimize.py '<full ganak command>'")
        sys.exit(1)
    minimize(sys.argv[1])
