#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2022  Anna Latour
#                     Mate Soos
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

import subprocess
import os
import time
import random
import resource
import optparse
import stat
import shutil
from collections import namedtuple
from functools import partial
import re

Solver = namedtuple("Solver", "exe dir", defaults=[None, None])
Preproc = namedtuple("Preproc", "exe dir", defaults=[None, None])


def setlimits(t):
    # Set maximum CPU time to 1 second in child process, after fork() but before exec()
    print("Setting resource limit in child (pid %d)" % os.getpid())
    resource.setrlimit(resource.RLIMIT_CPU, (t, t))


def set_up_parser():
    usage = "usage: %prog [options] "
    desc = "Fuzz model counter\n"

    parser = optparse.OptionParser(
      usage=usage, description=desc)

    parser.add_option(
      "--verbose", "-v", action="store_true", default=False,
      dest="verbose", help="Print more output")

    parser.add_option(
      "--seed", dest="rnd_seed",
      help="Fuzz test start seed. Otherwise, random seed is picked", type=int)

    parser.add_option(
      "--tout", "-t", dest="maxtime", type=int, default=3,
      help="Max time to run. Default: %default")

    parser.add_option(
      "--textra", dest="maxtimediff", type=int, default=2,
      help="Extra time on top of timeout for processing."
      " Default: %default")

    parser.add_option(
      "--arjun", dest="arjun", type=str, default="../arjun/build/arjun",
      help="Location of arjun. Default: %default")

    parser.add_option(
      "--cadical", dest="cadical", type=str, default="../cadical/build/cadical",
      help="Location of cadical. Default: %default")

    return parser


def run(command, dir):
    print("Executing: %s in dir %s" % (" ".join(command), dir))
    if options.verbose:
        print("CPU limit of parent (pid %d)" % os.getpid(), resource.getrlimit(resource.RLIMIT_CPU))

    p = subprocess.Popen(command, stderr=subprocess.PIPE,
          stdout=subprocess.PIPE, universal_newlines=True, cwd=dir,
          preexec_fn=partial(setlimits, options.maxtime))

    consoleOutput, err = p.communicate()
    if options.verbose:
        print("CPU limit of parent (pid %d) after child finished executing" % os.getpid(),
            resource.getrlimit(resource.RLIMIT_CPU))
    return consoleOutput, err


def gen_fuzz_call_biere(fuzzer, fname):
    seed = random.randint(0, 1000000)
    call = "{0} {1} > {2}".format(fuzzer, seed, fname)
    return call


def gen_fuzz_call_brummayer(fuzzer, fname):
    seed = random.randint(0, 1000000)
    call = "{0} -s {1} > {2}".format(fuzzer, seed, fname)
    return call


def unique_file(fname_begin, fname_end=".cnf"):
    max_num_files = 300
    counter = 1
    while True:
        fname = "out/" + fname_begin + '_' + str(counter) + fname_end
        try:
            fd = os.open(
                fname, os.O_CREAT | os.O_EXCL, stat.S_IREAD | stat.S_IWRITE)
            os.fdopen(fd).close()
            return str(fname)
        except OSError:
            pass

        counter += 1
        if counter > max_num_files:
            print("Cannot create unique_file, last try was: %s" % fname)
            exit(-1)


def parse_solution_from_output(output_lines):
    if len(output_lines) == 0:
        print("Error! SAT solver output is empty!")
        print("output lines: %s" % output_lines)
        exit(-1)

    # solution will be put here
    satunsatfound = False
    vlinefound = False
    solution = {}
    sat = None

    # parse in solution
    for line in output_lines:
        # skip comment
        if re.match("^Setting resource limit", line):
            continue
        if (re.match('^c', line)):
            continue

        # SAT/UNSAT
        if (re.match('^s ', line)):
            if (satunsatfound):
                print("ERROR: solution twice in solver output!")
                exit(-1)

            if 'UNSAT' in line:
                sat = False
                satunsatfound = True
                continue

            if 'SAT' in line:
                sat = True
                satunsatfound = True
                continue

            print("ERROR: line starts with 's' but no SAT/UNSAT on line")
            exit(-1)

        # parse in solution
        if (re.match('^v ', line)):
            vlinefound = True
            myvars = line.split(' ')
            for var in myvars:
                var = var.strip()
                if var == "" or var == 'v':
                    continue
                if (int(var) == 0):
                    break
                intvar = int(var)
                solution[abs(intvar)] = (intvar >= 0)
            continue

        if (line.strip() == ""):
            continue

        print("Error! SAT solver output contains a line that is neither 'v' nor 'c' nor 's'!")
        print("Line is:", line.strip())
        exit(-1)

    if (satunsatfound is False):
        print("Error: Cannot find if SAT or UNSAT. Maybe didn't finish running?")
        exit(-1)

    if (sat is True and vlinefound is False):
        print("Error: Solution is SAT, but no 'v' line")
        exit(-1)

    return sat, solution


def run_one_solver(solver, fname: str):
    curr_time = time.time()
    toexec = solver.exe.split()
    toexec.append(os.getcwd() + "/" + fname)
    out, err = run(toexec, solver.dir)
    if err is None or err.strip() == "":
        pass
        # print("No error during execution")
    else:
        print("Error string is: ", err)
        exit(-1)
    diff_time = time.time() - curr_time
    if diff_time > options.maxtime - options.maxtimediff:
        print("Too much time to solve with %s, aborted!" % solver.exe)
        return None, None

    return parse_solution_from_output(out.split("\n"))


def check_header(fname):
    with open(fname, "r") as f:
        num_cls = 0
        max_vars = 0
        header_cls = 0
        header_vars = 0
        for line in f:
            line = line.strip()
            if len(line) == 0:
                print("Empty line is NOT part of DIMACS, error\n")
                return False
            if line[0] == "p":
                header = line.split()
                if len(header) != 4:
                    print("Header is not 4 pieces?!")
                    return False
                assert header[0] == "p"
                assert header[1] == "cnf"
                header_vars = int(header[2])
                header_cls = int(header[3])
                continue
            if line[0] == "c":
                continue

            num_cls += 1
            line = line.split()
            for tok in line:
                lit = abs(int(tok))
                if lit > max_vars:
                    max_vars = lit

        if num_cls != header_cls:
            print("cls in CNF: %d but header said: %d" % (num_cls, header_cls))
            return False

        if max_vars > header_vars:
            print("max vars was: %d but header said: %d" % (max_vars, header_vars))
            return False
    return True


def check_regular_clause(line, solution):
    lits = line.split()
    for lit in lits:
        numlit = int(lit)
        if numlit == 0:
            break

        if abs(numlit) not in solution:
            continue

        if solution[abs(numlit)] ^ (numlit < 0):
            return True

    # print not set vars
    for lit in lits:
        numlit = int(lit)
        if numlit == 0:
            break

        if abs(numlit) not in solution:
            print("var %d in XOR clause not set" % abs(numlit))

    print("Error: clause '%s' not satisfied." % line.strip())
    raise NameError("Error: clause '%s' not satisfied." % line)


def check_xor_clause(line, solution):
    line = line.lstrip('x')
    lits = line.split()
    final = False
    for lit in lits:
        numlit = int(lit)
        if numlit != 0:
            if abs(numlit) not in solution:
                raise NameError("Error: var %d not solved, but referred to in a xor-clause of the CNF" % abs(numlit))
            final ^= solution[abs(numlit)]
            final ^= numlit < 0
    if final is False:
        print("Error: xor-clause '%s' not satisfied." % line.strip())
        raise NameError("Error: xor-clause '%s' not satisfied." % line)


def test_found_solution(solution, fname):
    print("Verifying solution.")
    f = open(fname, "r")
    clauses = 0

    for line in f:
        line = line.rstrip()

        # skip empty lines
        if len(line) == 0:
            continue

        # check solution against clause
        try:
            if line[0] != 'c' and line[0] != 'p':
                if line[0] != 'x':
                    check_regular_clause(line, solution)
                else:
                    assert line[0] == 'x', "Line must start with p, c, v or x"
                    check_xor_clause(line, solution)

            clauses += 1
        except:
            raise

    f.close()
    print("Verified %d original xor&regular clauses" % clauses)


def write_sol_to_file(solution, fname: str):
    with open(fname, "w") as f:
        f.write("s SATISFIABLE\n")
        v_line = "v "
        for a, b in solution.items():
            if b:
                v_line += "%d " % a
            else:
                v_line += "%d " % -a
        f.write(v_line + "0\n")


def postproc(solution, reconstruct):
    fname_tmp = unique_file("fuzzTest")
    write_sol_to_file(solution, fname_tmp)
    toexec = ["./bins/arjun/solextend", reconstruct, fname_tmp]
    out, err = run(toexec, solver.dir)
    if err is None or err.strip() == "":
        pass
        # print("No error during execution.")
    else:
        print("Error string is: ", err)
        exit(-1)
    ret = parse_solution_from_output(out.split("\n"))
    os.unlink(fname_tmp)
    return ret


def run_one_preproc(preproc, fname: str, fname2: str, reconstruct: str):
    curr_time = time.time()
    toexec = preproc.exe.split()
    toexec.append(os.getcwd() + "/" + fname)
    toexec.append(os.getcwd() + "/" + fname2)
    toexec.append(os.getcwd() + "/" + reconstruct)
    print("Executing preproc ", preproc)
    _, err = run(toexec, preproc.dir)
    if err is None or err.strip() == "":
        pass
    else:
        print("Error during preproc:", err)
        exit(-1)
    diff_time = time.time() - curr_time
    if diff_time > options.maxtime - options.maxtimediff:
        print("Too much time to preproc with %s, aborted!" % solver.exe)
        return False
    assert check_header(fname2)
    return True


if __name__ == "__main__":
    if os.path.exists("out") and os.path.isfile("out"):
        print("ERROR: file 'out' exists, but we need a directory named 'out'")
        exit(-1)

    if not os.path.isdir("out"):
        print("Directory for outputs, 'out' not present, creating it.")
        os.mkdir("out")

    # Create directories needed to run fuzzer
    os.makedirs("sandbox", exist_ok=True)
    os.makedirs("tmpdir", exist_ok=True)
    os.makedirs("out", exist_ok=True)

    # parse options
    parser = set_up_parser()
    (options, args) = parser.parse_args()

    if options.rnd_seed is None:
        rnd_seed = random.randint(0, 1000*1000*1000)
        print("Using seed:", rnd_seed)
    else:
        rnd_seed = options.rnd_seed
    random.seed(rnd_seed)

    while True:
        fname = unique_file("fuzzTest")
        print("Checking fname: ", fname)

        call = random.choice([gen_fuzz_call_biere("./biere-fuzz", fname)
                               , gen_fuzz_call_brummayer("./cnf-fuzz-brummayer.py", fname)])
        status = subprocess.call(call, shell=True)
        if status != 0:
            print("Failed fuzzer file generator call: ", call)
            exit(-1)
        else:
            print("Generated fuzz file %s with call: %s" % (fname, call))

        solvers = [
            Solver(options.cadical, "./"),
        ]

        preprocs = [
            Preproc("./arjun", "./bins/arjun/"),
        ]

        simplified = []
        for preproc in preprocs:
            fname2 = unique_file("fuzzTest")
            reconstruct = unique_file("fuzzTest")
            shutil.copyfile(fname, fname2)
            OK = run_one_preproc(preproc, fname, fname2, reconstruct)
            if OK:
                print("Generated CNF file %s by preproc %s which preprocessed %s" % (fname2, preproc.exe, fname))
                print("Generated reconstruction %s by preproc %s which preprocessed %s"
                      % (reconstruct, preproc.exe, fname))
                simplified.append((preproc, fname2, reconstruct))
            else:
                os.unlink(fname2)

        for solver in solvers:
            for preproc, fname2, reconstruct in simplified:
                sat2, solution2 = run_one_solver(solver, fname2)
                if sat2 is True:
                    test_found_solution(solution2, fname2)
                    sat, solution = postproc(solution2, reconstruct)
                    test_found_solution(solution, fname)
                else:
                    print("It's UNSAT so can't check reconstruction")

        print(" ------ Checking with file %s finished -------" % fname)
        print("")
        os.unlink(fname)
        for _, fname2, reconstruct in simplified:
            pass
            os.unlink(fname2)
            os.unlink(reconstruct)
