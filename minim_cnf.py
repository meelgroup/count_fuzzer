#!/usr/bin/env python3
"""
CNF clause minimizer for files that crash a binary.

This script tries to remove clauses from a CNF file using binary search
while ensuring the binary still crashes with the modified input.
"""

import sys
import os
import subprocess
import tempfile


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
    """Read CNF file and separate into header, clauses, and special lines."""
    with open(filepath, 'r') as f:
        lines = f.readlines()

    header_line = None
    num_vars = None
    clauses = []
    special_lines = []  # Comments, weights, show directives, etc.

    for line in lines:
        stripped = line.strip()

        if line.startswith('p cnf '):
            # This is the problem line
            header_line = line
            # Extract the original variable count
            parts = line.strip().split()
            if len(parts) >= 3:
                num_vars = int(parts[2])
        elif line.startswith('c '):
            # Comment lines (including weights, show, etc.)
            special_lines.append(line)
        elif stripped and not stripped.startswith('c') and stripped != '0':
            # This is a clause (ends with 0)
            clauses.append(line)

    if not header_line:
        print("Error: Could not find 'p cnf' header line")
        sys.exit(1)

    if num_vars is None:
        print("Error: Could not parse variable count from header")
        sys.exit(1)

    return num_vars, clauses, special_lines


def write_cnf_file(filepath, num_vars, clauses, special_lines):
    """Write CNF file with given clauses and special lines, preserving original variable count."""
    with open(filepath, 'w') as f:
        num_clauses = len(clauses)

        # Write header - preserve original variable count, only update clause count
        f.write(f'p cnf {num_vars} {num_clauses}\n')

        # Write non-weight/show comment lines first
        for line in special_lines:
            if not line.startswith('c p weight') and not line.startswith('c p show'):
                f.write(line)

        # Write clauses
        for clause in clauses:
            f.write(clause)

        # Write special directives (show, weights) at the end
        for line in special_lines:
            if line.startswith('c p show') or line.startswith('c p weight'):
                f.write(line)


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


def delta_debug_minimize(binary_and_args, tmp_cnf, num_vars, special_lines, clauses, original_cnf):
    """
    Delta debugging algorithm to minimize clauses.
    Returns the minimal set of clauses that still causes a crash.
    """
    n = len(clauses)
    if n == 0:
        return []

    # Test if crash occurs with empty set
    write_cnf_file(tmp_cnf, num_vars, [], special_lines)
    if test_crash(binary_and_args, tmp_cnf):
        print(f"  Crash occurs with no clauses!")
        return []

    # Test if we can find a minimal subset using binary search
    def test_subset(subset):
        write_cnf_file(tmp_cnf, num_vars, subset, special_lines)
        return test_crash(binary_and_args, tmp_cnf)

    # Start with granularity of 2 and increase
    granularity = 2

    while granularity <= n:
        chunk_size = n // granularity
        if chunk_size == 0:
            chunk_size = 1

        print(f"  Testing with granularity {granularity} (chunk size ~{chunk_size})")

        # Try removing each chunk
        some_removed = False
        new_clauses = clauses[:]
        i = 0

        while i < len(new_clauses):
            # Calculate chunk for current position
            current_chunk_size = min(chunk_size, len(new_clauses) - i)

            # Try without this chunk
            test_set = new_clauses[:i] + new_clauses[i+current_chunk_size:]

            if test_subset(test_set):
                # Still crashes without this chunk - remove it
                print(f"    Removed chunk of {current_chunk_size} clauses at position {i}")
                new_clauses = test_set
                some_removed = True
                
                # Save intermediate file with clause count
                base_name = original_cnf.replace('.cnf', '')
                intermediate_file = f"{base_name}-{len(new_clauses)}.cnf"
                write_cnf_file(intermediate_file, num_vars, new_clauses, special_lines)
                print(f"      Saved: {intermediate_file}")
                
                # Don't increment i, test the same position again
            else:
                # Need this chunk, move to next
                i += current_chunk_size

        if not some_removed:
            # No chunks could be removed at this granularity
            # Try finer granularity
            granularity *= 2
        else:
            # Made progress, update clauses and try same granularity again
            clauses = new_clauses
            n = len(clauses)
            print(f"  Reduced to {n} clauses")

    return clauses


def minimize_clauses(binary_and_args, original_cnf):
    """Minimize clauses in CNF file while preserving crash."""

    # Read the original file
    num_vars, clauses, special_lines = read_cnf_file(original_cnf)

    print(f"Original CNF has {num_vars} variables and {len(clauses)} clauses")

    # First verify the original crashes
    if not test_crash(binary_and_args, original_cnf):
        print("Error: Original CNF does not crash the binary!")
        sys.exit(1)

    print("Confirmed: Original CNF crashes the binary")
    print()

    # Create a temporary working file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.cnf', delete=False) as tmp:
        tmp_cnf = tmp.name

    try:
        current_clauses = clauses.copy()
        total_removed = 0
        round_num = 1

        # Keep doing passes until we can't remove anything more
        while True:
            print(f"Round {round_num}: Starting with {len(current_clauses)} clauses")

            # Try delta debugging minimization
            kept_clauses = delta_debug_minimize(
                binary_and_args, tmp_cnf, num_vars, special_lines, current_clauses, original_cnf
            )

            if len(kept_clauses) == len(current_clauses):
                print(f"Round {round_num}: No clauses removed, minimization complete")
                break

            # Update current clauses to only kept ones
            removed_this_round = len(current_clauses) - len(kept_clauses)
            total_removed += removed_this_round
            current_clauses = kept_clauses

            # Save intermediate result with clause count in filename
            base_name = original_cnf.replace('.cnf', '')
            intermediate_file = f"{base_name}-{len(current_clauses)}.cnf"
            write_cnf_file(intermediate_file, num_vars, current_clauses, special_lines)
            print(f"Round {round_num}: Removed {removed_this_round} clauses, {len(current_clauses)} remaining")
            print(f"  Saved: {intermediate_file}")
            print()

            round_num += 1

        # Write the final minimized version
        output_file = original_cnf.replace('.cnf', '_min_clauses.cnf')
        write_cnf_file(output_file, num_vars, current_clauses, special_lines)

        print("\nMinimization complete!")
        print(f"  Original clauses: {len(clauses)}")
        print(f"  Removed clauses: {total_removed}")
        print(f"  Remaining clauses: {len(current_clauses)}")
        print(f"  Reduction: {100 * total_removed / len(clauses):.1f}%")
        print(f"  Output file: {output_file}")

        # Verify the minimized file still crashes
        if test_crash(binary_and_args, output_file):
            print("\n✓ Verified: Minimized file still crashes the binary")
        else:
            print("\n✗ WARNING: Minimized file does not crash the binary!")

    finally:
        # Clean up temporary file
        if os.path.exists(tmp_cnf):
            os.remove(tmp_cnf)


def main():
    if len(sys.argv) != 2:
        print("Usage: ./minimize_cnf.py \"<command with cnf file>\"")
        print("Example: ./minimize_cnf.py \"../ganak/build/ganak --mode 1 --polar 1 file.cnf\"")
        sys.exit(1)

    cmd_string = sys.argv[1]
    binary_and_args, cnf_file = parse_command(cmd_string)

    print(f"Binary: {' '.join(binary_and_args)}")
    print(f"CNF file: {cnf_file}")
    print()

    minimize_clauses(binary_and_args, cnf_file)


if __name__ == '__main__':
    main()
