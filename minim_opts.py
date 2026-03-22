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

"""
Minimizes a ganak command by stripping options while preserving either:
- A crash (non-zero exit code), or
- A specific count value (within 0.1% tolerance)

Automatically detects which mode to use based on the initial command result.
"""

import sys
import subprocess


KEEP_OPTS = {"--mode", "--verb"}
COUNT_TOLERANCE = 0.001  # 0.1%


def run_command(cmd, timeout=120):
    """Run command and return (returncode, output, timed_out)."""
    print(f"    Running: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True,
                                text=True, timeout=timeout)
        return result.returncode, result.stdout + result.stderr, False
    except subprocess.TimeoutExpired:
        print("    -> timeout")
        return -1, "", True


def extract_count(output):
    """Extract count from solver output, returns None if not found."""
    for line in output.splitlines():
        line = line.strip()
        
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
    """Check if two counts are within tolerance."""
    if a is None or b is None:
        return False
    if b == 0.0:
        return abs(a) < 1e-10
    return abs(a - b) / abs(b) <= COUNT_TOLERANCE


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
    """Build command string from components."""
    parts = [executable]
    for opt, val in options:
        parts.append(opt)
        if val is not None:
            parts.append(val)
    parts.append(input_file)
    return " ".join(parts)


def minimize(cmd_str):
    """Minimize command options while preserving crash or count."""
    executable, options, input_file = parse_command(cmd_str)

    print(f"Original command:\n  {cmd_str}\n")
    
    # Detect mode: crash or count
    returncode, output, timed_out = run_command(cmd_str)
    
    if timed_out:
        print("ERROR: Original command timed out.")
        sys.exit(1)
    
    # Determine if we're minimizing for crash or count
    if returncode != 0:
        mode = "crash"
        print(f"Mode: CRASH (exit code {returncode})")
        print("Will minimize while preserving the crash.\n")
        
        def property_preserved(cmd):
            ret, _, timeout = run_command(cmd)
            if timeout:
                print("    -> timeout (treating as no crash)")
                return False
            crashed = ret != 0
            print(f"    -> exit code {ret} ({'crash' if crashed else 'no crash'})")
            return crashed
    else:
        # Try to extract count
        original_count = extract_count(output)
        if original_count is None:
            print("ERROR: Command succeeded but could not extract count.")
            sys.exit(1)
        
        mode = "count"
        print(f"Mode: COUNT (value: {original_count})")
        print("Will minimize while preserving the count.\n")
        
        def property_preserved(cmd):
            ret, out, timeout = run_command(cmd)
            if timeout:
                return False
            count = extract_count(out)
            same = counts_close(count, original_count)
            print(f"    -> count: {count} ({'same' if same else 'different'})")
            return same

    # First pass: remove unnecessary options
    current = list(options)
    
    for opt, val in options:
        if opt in KEEP_OPTS:
            continue

        trial = [(o, v) for o, v in current if o != opt]
        trial_cmd = build_command(executable, trial, input_file)

        label = f"{opt} {val}" if val is not None else opt
        print(f"Trying without {label} ...")

        if property_preserved(trial_cmd):
            print(f"  -> property preserved, dropping {label}\n")
            current = trial
        else:
            print(f"  -> property lost, keeping {label}\n")

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
            if property_preserved(trial_cmd):
                print("  -> property preserved, setting --td 0\n")
                current = trial
            else:
                print("  -> property lost, keeping original --td value\n")
    else:
        # --td is not present, try adding --td 0
        print("Trying to add --td 0 ...")
        trial = current.copy()
        trial.append(("--td", "0"))
        trial_cmd = build_command(executable, trial, input_file)
        if property_preserved(trial_cmd):
            print("  -> property preserved, adding --td 0\n")
            current = trial
        else:
            print("  -> property lost, not adding --td 0\n")

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
            if property_preserved(trial_cmd):
                print("  -> property preserved, setting --arjun 0\n")
                current = trial
            else:
                print("  -> property lost, keeping original --arjun value\n")
    else:
        # --arjun is not present, try adding --arjun 0
        print("Trying to add --arjun 0 ...")
        trial = current.copy()
        trial.append(("--arjun", "0"))
        trial_cmd = build_command(executable, trial, input_file)
        if property_preserved(trial_cmd):
            print("  -> property preserved, adding --arjun 0\n")
            current = trial
        else:
            print("  -> property lost, not adding --arjun 0\n")

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
            if property_preserved(trial_cmd):
                print("  -> property preserved, setting --threads 1 --debugthreads 1\n")
                current = trial
            else:
                print("  -> property lost, keeping original thread settings\n")

    final_cmd = build_command(executable, current, input_file)
    print("Minimized command:")
    print(f"  {final_cmd}")
    return final_cmd


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: minim_opts.py '<full ganak command>'")
        print("\nAutomatically detects whether to minimize for crash or count.")
        sys.exit(1)
    minimize(sys.argv[1])
