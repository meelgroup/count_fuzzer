#!/usr/bin/env python3
"""
Simple unit propagation for CNF formulas in DIMACS format.

This tool takes a CNF file and performs unit propagation until fixpoint:
1. Finds all unit clauses (clauses with single literal)
2. Propagates each unit literal through the formula:
   - Removes clauses containing the literal (satisfied)
   - Removes the negated literal from all clauses (falsified)
3. Repeats until no more unit clauses exist
4. Outputs simplified CNF to stdout
5. Prints progress information to stderr

Usage:
    ./propagate.py [--verb] input.cnf > output.cnf
    cat input.cnf | ./propagate.py [--verb] > output.cnf

Options:
    --verb    Verbose mode: print detailed propagation progress
"""

import sys

# Global verbose flag
VERBOSE = False


def parse_dimacs(lines):
    """
    Parse DIMACS CNF format.
    Returns (header_lines, num_vars, num_clauses, clauses)
    where clauses is a list of lists of integers.
    Returns None for clauses if empty clause found (UNSAT).
    """
    header_lines = []
    num_vars = 0
    num_clauses = 0
    clauses = []

    for line in lines:
        line = line.strip()

        # Skip empty lines
        if not line:
            continue

        # Comment or header lines
        if line.startswith('c'):
            header_lines.append(line)
            continue

        # Problem line
        if line.startswith('p cnf') or line.startswith('p wcnf') or line.startswith('p wcnf'):
            parts = line.split()
            num_vars = int(parts[2])
            num_clauses = int(parts[3])
            continue

        # Clause line
        literals = [int(x) for x in line.split() if x]
        if literals and literals[-1] == 0:
            literals = literals[:-1]  # Remove trailing 0
            if not literals:
                # Empty clause found - UNSAT
                if VERBOSE:
                    print("UNSAT detected: Empty clause in input", file=sys.stderr)
                return header_lines, num_vars, num_clauses, None
            clauses.append(literals)

    return header_lines, num_vars, num_clauses, clauses


def find_unit_clauses(clauses):
    """
    Find all unit clauses (clauses with exactly one literal).
    Returns set of unit literals.
    """
    units = set()
    for clause in clauses:
        if len(clause) == 1:
            units.add(clause[0])
    return units


def propagate_literal(clauses, lit):
    """
    Propagate a unit literal through the clause database.
    - Remove clauses containing lit (satisfied)
    - Remove -lit from remaining clauses (falsified literal)
    Returns (new_clauses, num_satisfied, num_shortened)
    """
    new_clauses = []
    num_satisfied = 0
    num_shortened = 0

    for clause in clauses:
        # If clause contains the literal, it's satisfied - remove it
        if lit in clause:
            num_satisfied += 1
            continue

        # If clause contains negated literal, remove it from clause
        if -lit in clause:
            new_clause = [x for x in clause if x != -lit]
            # Only add non-empty clauses
            if new_clause:
                new_clauses.append(new_clause)
                num_shortened += 1
            # If clause becomes empty, we have UNSAT
            else:
                # Return empty clause as signal of UNSAT
                return None, num_satisfied, num_shortened
        else:
            # Clause unchanged
            new_clauses.append(clause)

    return new_clauses, num_satisfied, num_shortened


def unit_propagate(clauses):
    """
    Perform unit propagation until fixpoint.
    Returns (simplified_clauses, assignments) or (None, assignments) if UNSAT.
    """
    assignments = set()
    iteration = 0

    while True:
        iteration += 1
        units = find_unit_clauses(clauses)

        if not units:
            # No more unit clauses - done
            break

        if VERBOSE:
            print(f"Iteration {iteration}: Found {len(units)} unit clause(s): "
                  f"{sorted(units)}", file=sys.stderr)

        # Check for conflicting unit clauses (both x and -x)
        for lit in units:
            if -lit in units:
                if VERBOSE:
                    print(f"UNSAT detected: Conflicting unit clauses {lit} and {-lit}",
                          file=sys.stderr)
                assignments.add(lit)
                assignments.add(-lit)
                return None, assignments

        # Propagate all unit clauses
        for lit in units:
            assignments.add(lit)
            result = propagate_literal(clauses, lit)

            if result[0] is None:
                # UNSAT - empty clause detected
                if VERBOSE:
                    print(f"UNSAT detected: Empty clause after propagating {lit}",
                          file=sys.stderr)
                return None, assignments

            clauses, num_sat, num_short = result
            if VERBOSE:
                print(f"  Propagated {lit}: {num_sat} clauses satisfied, "
                      f"{num_short} clauses shortened", file=sys.stderr)

    return clauses, assignments


def get_max_var(clauses):
    """Get the maximum variable number used in clauses."""
    max_var = 0
    for clause in clauses:
        for lit in clause:
            max_var = max(max_var, abs(lit))
    return max_var


def write_dimacs(header_lines, clauses, unit_clauses=None):
    """
    Write CNF in DIMACS format to stdout.
    Optionally prepend unit clauses that were propagated.
    """
    # Write original comments (but not old p cnf line)
    for line in header_lines:
        if not line.startswith('p cnf'):
            print(line)

    # Calculate total clauses including units
    total_clauses = len(clauses)
    if unit_clauses:
        total_clauses += len(unit_clauses)

    # Write new problem line
    num_vars = get_max_var(clauses)
    if unit_clauses:
        # Also consider variables in unit clauses
        for lit in unit_clauses:
            num_vars = max(num_vars, abs(lit))
    print(f"p cnf {num_vars} {total_clauses}")

    # Write unit clauses first (sorted by variable number, not literal value)
    if unit_clauses:
        for lit in sorted(unit_clauses, key=abs):
            print(f"{lit} 0")

    # Write remaining clauses
    for clause in clauses:
        print(' '.join(map(str, clause)) + ' 0')


def output_unsat(header_lines, assignments=None):
    """
    Output UNSAT result to stderr and write empty clause CNF to stdout.
    """
    print("Result: UNSAT", file=sys.stderr)
    if assignments is not None and len(assignments) > 0:
        print(f"Propagated literals before conflict: {sorted(assignments)}",
              file=sys.stderr)
    print(file=sys.stderr)

    # Output empty CNF (0 variables, 1 empty clause = UNSAT)
    for line in header_lines:
        if not line.startswith('p cnf'):
            print(line)
    print("p cnf 0 1")
    print("0")
    sys.exit(0)


def check_satisfiability(cnf_lines):
    """
    Check if the CNF is satisfiable using CryptoMiniSat.
    Takes the CNF lines as input and feeds them via stdin.
    Returns True if SAT, False if UNSAT, None if solver not found or error.
    """
    import subprocess
    import os

    cms_path = "../cryptominisat/build/cryptominisat5"

    if not os.path.exists(cms_path):
        return None  # Solver not found, skip check

    try:
        # Join lines back into a string to feed via stdin
        cnf_input = ''.join(cnf_lines)

        result = subprocess.run(
            [cms_path, "--verb=0", "/dev/stdin"],
            input=cnf_input,
            capture_output=True,
            text=True,
            timeout=30
        )

        # Check for UNSAT in output
        if "s UNSATISFIABLE" in result.stdout:
            return False
        elif "s SATISFIABLE" in result.stdout:
            return True
        else:
            return None  # Unknown result

    except subprocess.TimeoutExpired:
        return None  # Timeout, skip check
    except Exception:
        return None  # Error, skip check


def main():
    global VERBOSE

    # Parse arguments
    args = sys.argv[1:]
    if '--verb' in args:
        VERBOSE = True
        args.remove('--verb')

    if len(args) > 1:
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    # Read input
    filename = None
    if len(args) == 1:
        filename = args[0]
        if VERBOSE:
            print(f"Reading CNF from: {filename}", file=sys.stderr)
        with open(filename, 'r') as f:
            lines = f.readlines()
    else:
        if VERBOSE:
            print("Reading CNF from stdin", file=sys.stderr)
        lines = sys.stdin.readlines()

    # Parse DIMACS
    if VERBOSE:
        print("Parsing DIMACS format...", file=sys.stderr)
    header_lines, num_vars, num_clauses, clauses = parse_dimacs(lines)
    if VERBOSE:
        print(f"Original: {num_vars} variables, {num_clauses} clauses", file=sys.stderr)

    if clauses is None:
        # UNSAT from parsing (empty clause in input)
        output_unsat(header_lines)
        return  # Never reached, but helps type checker

    if VERBOSE:
        print(f"Parsed: {len(clauses)} clauses", file=sys.stderr)

    # Check satisfiability with CryptoMiniSat
    if VERBOSE:
        print("Checking satisfiability with CryptoMiniSat...", file=sys.stderr)
    sat_result = check_satisfiability(lines)

    if sat_result is False:
        # Formula is UNSAT according to SAT solver - ALWAYS show warning
        print(file=sys.stderr)
        print("\033[1;31m" + "="*80, file=sys.stderr)
        print("WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING", file=sys.stderr)
        print("="*80, file=sys.stderr)
        print("THE INPUT FORMULA IS UNSATISFIABLE!", file=sys.stderr)
        print("CryptoMiniSat determined the formula is UNSAT.", file=sys.stderr)
        print("Unit propagation may not detect this - the simplified output", file=sys.stderr)
        print("may still contain clauses even though the formula is UNSAT!", file=sys.stderr)
        print("="*80, file=sys.stderr)
        print("WARNING WARNING WARNING WARNING WARNING WARNING WARNING WARNING", file=sys.stderr)
        print("="*80 + "\033[0m", file=sys.stderr)
        print(file=sys.stderr)
    elif sat_result is True:
        if VERBOSE:
            print("CryptoMiniSat: Formula is SATISFIABLE", file=sys.stderr)
    else:
        if VERBOSE:
            print("CryptoMiniSat check skipped or failed", file=sys.stderr)

    if VERBOSE:
        print(file=sys.stderr)

    # Perform unit propagation
    if VERBOSE:
        print("Starting unit propagation...", file=sys.stderr)
    result_clauses, assignments = unit_propagate(clauses)
    if VERBOSE:
        print(file=sys.stderr)

    if result_clauses is None:
        # UNSAT from unit propagation
        output_unsat(header_lines, assignments)
        return  # Never reached, but helps type checker

    # SAT or simplified
    if VERBOSE:
        print("Result: Simplified (or SAT if no clauses remain)", file=sys.stderr)
        print(f"Total unit propagations: {len(assignments)}", file=sys.stderr)
        print(f"Propagated literals: {sorted(assignments)}", file=sys.stderr)
        print(f"Remaining clauses: {len(result_clauses)}", file=sys.stderr)

    if not result_clauses:
        if VERBOSE:
            print("Formula is SAT (no clauses remain)!", file=sys.stderr)
            print(f"Output will contain {len(assignments)} unit clause(s)", file=sys.stderr)
            print(file=sys.stderr)
            print("Writing simplified CNF to stdout...", file=sys.stderr)
        write_dimacs(header_lines, [], assignments)
        sys.exit(0)

    if VERBOSE:
        max_var = get_max_var(result_clauses)
        print(f"Remaining variables: {max_var}", file=sys.stderr)
        print(f"\nReduction: {num_clauses} -> {len(result_clauses) + len(assignments)} clauses "
              f"({100*(num_clauses-(len(result_clauses) + len(assignments)))/num_clauses:.1f}% reduction)",
              file=sys.stderr)
        print(file=sys.stderr)
        print("Writing simplified CNF to stdout...", file=sys.stderr)

    write_dimacs(header_lines, result_clauses, assignments)


if __name__ == '__main__':
    main()
