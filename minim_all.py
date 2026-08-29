#!/usr/bin/env python3
"""
Automated minimization pipeline for fuzzer test cases.

This script orchestrates all minimization tools to reduce a test case:
1. Detects whether the command crashes or produces a count
2. For crashes: Minimizes options, then weights, then CNF clauses
3. For counts: Minimizes options (preserving count), then weights, then clauses
4. Verifies each step preserves the crash or count

Note: This tool is NOT for timeouts - only for crashes and successful counts.

Usage:
    ./minim_all.py "<full command with CNF file>"
    ./minim_all.py "../ganak/build/ganak --mode 1 --polar 1 file.cnf"
"""

import sys
import os
import subprocess
import shutil


def run_command(cmd, timeout=20):
    """
    Run a command and return (returncode, stdout, stderr, timed_out).
    """
    try:
        result = subprocess.run(
            cmd if isinstance(cmd, list) else cmd,
            shell=not isinstance(cmd, list),
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr, False
    except subprocess.TimeoutExpired:
        return -1, "", "", True


def extract_count(output):
    """
    Extract count from solver output.
    Returns None if no count found.
    """
    for line in output.splitlines():
        line = line.strip()

        # Integer count
        if line.startswith("s mc") or line.startswith("s pmc"):
            return float(line.split()[2])

        # Interval (quadruple float)
        if "c s exact quadruple float interval [" in line:
            parts = line.split()
            return (float(parts[7]) + float(parts[8])) / 2.0

        # Quadruple float
        if "c s exact quadruple float" in line:
            return float(line.split()[5])

        # Fraction
        if "c s exact arb frac" in line:
            parts = line.split()
            if parts[5] == "[":
                return (float(parts[6]) + float(parts[7])) / 2.0
            frac = parts[5].split("/")
            num = float(frac[0])
            return num if len(frac) < 2 else num / float(frac[1])

        # Float or int
        if "c s exact arb float" in line or "c s exact arb int" in line:
            return float(line.split()[5])

        # Double precision
        if "c s exact double prec-sci" in line or \
           "s exact double prec-sci" in line:
            return float(line.split()[5])

        # Approximate
        if "c s approx arb int" in line:
            return float(line.split()[5])

    return None


def parse_command(cmd_string):
    """
    Parse command string to extract components.
    Returns (full_command, cnf_file_path)
    """
    parts = cmd_string.strip().split()

    cnf_file = None
    for part in parts:
        if part.endswith('.cnf') and os.path.exists(part):
            cnf_file = part
            break

    if not cnf_file:
        print("ERROR: Could not find CNF file in command")
        sys.exit(1)

    return cmd_string, cnf_file


def check_result_type(cmd):
    """
    Determine if command crashes, times out, or produces a count.
    Returns: ("crash", exitcode, output) or ("count", count_value, output)
             or ("timeout", None, output) or ("unknown", None, output)
    """
    print(f"Checking result for: {cmd}")
    returncode, stdout, stderr, timed_out = run_command(cmd)

    if timed_out:
        return "timeout", None, stdout + stderr

    if returncode != 0:
        return "crash", returncode, stdout + stderr

    # Success - check if we got a count
    count = extract_count(stdout + stderr)
    if count is not None:
        return "count", count, stdout + stderr

    return "unknown", None, stdout + stderr


def has_weights(cnf_file):
    """Check if CNF file contains weight lines."""
    try:
        with open(cnf_file, 'r') as f:
            for line in f:
                if line.startswith('c p weight '):
                    return True
    except Exception as e:
        print(f"Warning: Could not read CNF file: {e}")
    return False


def backup_file(filepath):
    """Create a backup of the file."""
    backup = filepath + ".backup"
    shutil.copy2(filepath, backup)
    print(f"Created backup: {backup}")
    return backup


def run_minimizer_script(script_name, cmd):
    """
    Run one of the minimizer scripts and stream its output in real-time.
    Returns (success, minimized_command)
    """
    script_path = os.path.join(os.path.dirname(__file__), script_name)

    if not os.path.exists(script_path):
        print(f"ERROR: Minimizer script not found: {script_path}")
        return False, cmd

    print(f"\n{'='*80}")
    print(f"Running {script_name}...")
    print(f"{'='*80}")
    sys.stdout.flush()

    # Run the minimizer with streaming output
    process = None
    try:
        # Use -u flag to force unbuffered output from Python subprocess
        process = subprocess.Popen(
            [sys.executable, "-u", script_path, cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,  # Line buffered
        )

        # Stream output line by line
        output_lines = []
        if process.stdout:
            for line in iter(process.stdout.readline, ''):
                if line:
                    print(line, end='', flush=True)  # Print immediately with flush
                    output_lines.append(line)

        # Wait for process to complete
        returncode = process.wait(timeout=600)  # 10 minute timeout

        if returncode != 0:
            print(f"\nWARNING: {script_name} exited with code {returncode}")
            return False, cmd

        # Extract minimized command from output
        for i, line in enumerate(output_lines):
            if "Minimized command:" in line:
                # Next line should be the command
                if i + 1 < len(output_lines):
                    minimized = output_lines[i + 1].strip()
                    return True, minimized

        # If we didn't find minimized command, assume no change
        return True, cmd

    except subprocess.TimeoutExpired:
        print(f"\nERROR: {script_name} timed out after 10 minutes")
        if process:
            process.kill()
        return False, cmd
    except Exception as e:
        print(f"\nERROR running {script_name}: {e}")
        return False, cmd


def verify_result_preserved(original_type, original_value, cmd):
    """
    Verify that the crash or count is still present after minimization.
    """
    print("\nVerifying result preserved...")
    print(f"Running: {cmd}")

    result_type, value, output = check_result_type(cmd)

    if original_type == "crash":
        if result_type == "crash":
            print(f"✓ Crash preserved (exit code: {value})")
            return True
        else:
            print(f"✗ WARNING: No longer crashes! Got: {result_type}")
            return False

    elif original_type == "count":
        if result_type == "count":
            if value == original_value:
                print(f"✓ Count preserved: {value}")
                return True
            else:
                print(f"✗ WARNING: Count changed from {original_value} "
                      f"to {value}")
                return False
        else:
            print(f"✗ WARNING: No longer produces count! Got: {result_type}")
            return False

    return False


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        print("\nUsage: ./minim_all.py \"<command with cnf file>\"")
        print("Example: ./minim_all.py \"../ganak/build/ganak --mode 1 "
              "file.cnf\"")
        sys.exit(1)

    original_cmd = sys.argv[1]
    cmd, cnf_file = parse_command(original_cmd)

    print(f"{'='*80}")
    print("AUTOMATED MINIMIZATION PIPELINE")
    print(f"{'='*80}")
    print(f"Original command: {cmd}")
    print(f"CNF file: {cnf_file}")
    print()

    # Step 0: Backup the original CNF file
    backup = backup_file(cnf_file)

    # Step 1: Determine result type
    print(f"\n{'='*80}")
    print("STEP 1: Detecting result type")
    print(f"{'='*80}")

    result_type, value, original_output = check_result_type(cmd)
    print(f"Result type: {result_type}")

    if result_type == "crash":
        print(f"Exit code: {value}")
    elif result_type == "count":
        print(f"Count: {value}")
    elif result_type == "timeout":
        print("Command timed out after 20 seconds")
        print("ERROR: This tool does not handle timeouts.")
        print("Timeouts are not minimized - we leave them as-is.")
        sys.exit(1)
    else:
        print("ERROR: Unknown result type, cannot proceed")
        sys.exit(1)

    current_cmd = cmd

    # Step 2: Minimize command-line options
    print(f"\n{'='*80}")
    print("STEP 2: Minimizing command-line options")
    print(f"{'='*80}")
    minimizer = "minim_opts.py"

    success, minimized_cmd = run_minimizer_script(minimizer, current_cmd)

    if success and minimized_cmd != current_cmd:
        if verify_result_preserved(result_type, value, minimized_cmd):
            current_cmd = minimized_cmd
            print("✓ Options minimized successfully")
        else:
            print("✗ Options minimization failed verification, reverting")
    else:
        print("Options unchanged or minimization failed")

    # Step 3: Minimize weights (if present)
    if has_weights(cnf_file):
        print(f"\n{'='*80}")
        print("STEP 3: Minimizing weight lines")
        print(f"{'='*80}")

        # minim_weights.py creates a new file, so we need to handle that
        success, _ = run_minimizer_script("minim_weights.py", current_cmd)

        if success:
            # Check if minimized file was created
            min_weights_file = cnf_file.replace('.cnf', '_min_weights.cnf')
            if os.path.exists(min_weights_file):
                # Update command to use new file
                new_cmd = current_cmd.replace(cnf_file, min_weights_file)
                if verify_result_preserved(result_type, value, new_cmd):
                    current_cmd = new_cmd
                    cnf_file = min_weights_file
                    print("✓ Weights minimized successfully")
                    print(f"  New CNF file: {cnf_file}")
                else:
                    print("✗ Weight minimization failed verification")
                    os.remove(min_weights_file)
            else:
                print("No weight-minimized file created")
        else:
            print("Weight minimization failed or not applicable")
    else:
        print(f"\n{'='*80}")
        print("STEP 3: Skipping weight minimization (no weights found)")
        print(f"{'='*80}")

    # Step 4: Minimize CNF clauses
    print(f"\n{'='*80}")
    print("STEP 4: Minimizing CNF clauses")
    print(f"{'='*80}")

    success, _ = run_minimizer_script("minim_cnf.py", current_cmd)

    if success:
        # Check if minimized file was created
        min_clauses_file = cnf_file.replace('.cnf', '_min_clauses.cnf')
        if os.path.exists(min_clauses_file):
            # Update command to use new file
            new_cmd = current_cmd.replace(cnf_file, min_clauses_file)
            if verify_result_preserved(result_type, value, new_cmd):
                current_cmd = new_cmd
                cnf_file = min_clauses_file
                print("✓ Clauses minimized successfully")
                print(f"  New CNF file: {cnf_file}")
            else:
                print("✗ Clause minimization failed verification")
                os.remove(min_clauses_file)
        else:
            print("No clause-minimized file created")
    else:
        print("Clause minimization failed")

    # Final summary
    print(f"\n{'='*80}")
    print("MINIMIZATION COMPLETE")
    print(f"{'='*80}")
    print(f"Original command: {original_cmd}")
    print(f"Minimized command: {current_cmd}")
    print()
    print(f"Original CNF file: {backup}")
    print(f"Final minimized CNF file: {cnf_file}")
    print()

    # Final verification
    print("Final verification:")
    if verify_result_preserved(result_type, value, current_cmd):
        if result_type == "crash":
            print("\n✓ SUCCESS: Minimized test case still crashes")
        else:
            print(f"\n✓ SUCCESS: Minimized test case produces same count "
                  f"({value})")
    else:
        print("\n✗ FAILURE: Minimized test case does not preserve the "
              "original result")
        print("  This should not happen. Please report this bug.")
        sys.exit(1)


if __name__ == '__main__':
    main()
