#!/usr/bin/env python3
"""
Weight minimizer for CNF files that crash a binary.

This script tries to remove weight lines ("c p weight ...") from a CNF file
while ensuring the binary still crashes with the modified input.
"""

import sys
import os
import subprocess
import tempfile
import shutil
from pathlib import Path


def parse_command(cmd_string):
    """Parse command string to extract binary path and arguments."""
    parts = cmd_string.strip().split()

    # Find the CNF file path in the command
    cnf_file = None
    binary_and_args = []

    for part in parts:
        if part.endswith('.cnf') and os.path.exists(part):
            cnf_file = part
        else:
            binary_and_args.append(part)

    if not cnf_file:
        print("Error: Could not find CNF file in command")
        sys.exit(1)

    return binary_and_args, cnf_file


def read_cnf_file(filepath):
    """Read CNF file and separate weight lines from other lines."""
    with open(filepath, 'r') as f:
        lines = f.readlines()

    non_weight_lines = []
    weight_lines = []

    for line in lines:
        if line.startswith('c p weight '):
            weight_lines.append(line)
        else:
            non_weight_lines.append(line)

    return non_weight_lines, weight_lines


def write_cnf_file(filepath, non_weight_lines, weight_lines):
    """Write CNF file with given weight lines."""
    with open(filepath, 'w') as f:
        f.writelines(non_weight_lines)
        f.writelines(weight_lines)


def test_crash(binary_and_args, cnf_file, timeout=10):
    """Test if the binary crashes with the given CNF file."""
    cmd = binary_and_args + [cnf_file]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout
        )
        # Binary crashes if it has non-zero exit code
        return result.returncode != 0
    except subprocess.TimeoutExpired:
        # Timeout means it didn't crash quickly
        return False
    except Exception as e:
        print(f"Error running command: {e}")
        return False


def minimize_weights(binary_and_args, original_cnf):
    """Minimize weights in CNF file while preserving crash."""

    # Read the original file
    non_weight_lines, weight_lines = read_cnf_file(original_cnf)

    print(f"Original CNF has {len(weight_lines)} weight lines")

    # First verify the original crashes
    if not test_crash(binary_and_args, original_cnf):
        print("Error: Original CNF does not crash the binary!")
        sys.exit(1)

    print("Confirmed: Original CNF crashes the binary")

    # Create a temporary working file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.cnf', delete=False) as tmp:
        tmp_cnf = tmp.name

    try:
        current_weights = weight_lines.copy()
        removed_count = 0

        # Try to remove each weight line one by one
        i = 0
        while i < len(current_weights):
            # Create a version without this weight line
            test_weights = current_weights[:i] + current_weights[i+1:]

            # Write test file
            write_cnf_file(tmp_cnf, non_weight_lines, test_weights)

            # Test if it still crashes
            print(f"Testing removal of weight {i+1}/{len(current_weights)}: ", end='', flush=True)

            if test_crash(binary_and_args, tmp_cnf):
                # Still crashes, keep this weight removed
                print(f"✓ Removed (now {len(test_weights)} weights)")
                current_weights = test_weights
                removed_count += 1
                # Don't increment i since we removed an element
            else:
                # No longer crashes, keep this weight
                print("✗ Needed")
                i += 1

        # Write the final minimized version
        output_file = original_cnf.replace('.cnf', '_min_weights.cnf')
        write_cnf_file(output_file, non_weight_lines, current_weights)

        print(f"\nMinimization complete!")
        print(f"  Original weights: {len(weight_lines)}")
        print(f"  Removed weights: {removed_count}")
        print(f"  Remaining weights: {len(current_weights)}")
        print(f"  Output file: {output_file}")

        # Verify the minimized file still crashes
        if test_crash(binary_and_args, output_file):
            print(f"\n✓ Verified: Minimized file still crashes the binary")
        else:
            print(f"\n✗ WARNING: Minimized file does not crash the binary!")

    finally:
        # Clean up temporary file
        if os.path.exists(tmp_cnf):
            os.remove(tmp_cnf)


def main():
    if len(sys.argv) != 2:
        print("Usage: ./minim_weights.py \"<command with cnf file>\"")
        print("Example: ./minim_weights.py \"../ganak/build/ganak --mode 1 --polar 1 file.cnf\"")
        sys.exit(1)

    cmd_string = sys.argv[1]
    binary_and_args, cnf_file = parse_command(cmd_string)

    print(f"Binary: {' '.join(binary_and_args)}")
    print(f"CNF file: {cnf_file}")
    print()

    minimize_weights(binary_and_args, cnf_file)


if __name__ == '__main__':
    main()
