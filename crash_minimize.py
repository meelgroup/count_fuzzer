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
                                text=True, timeout=120)
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

    final_cmd = build_command(executable, current, input_file)
    print("Minimized command:")
    print(f"  {final_cmd}")
    return final_cmd


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: crash_minimize.py '<full ganak command>'")
        sys.exit(1)
    minimize(sys.argv[1])
