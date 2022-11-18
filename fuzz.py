#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright (C) 2022 Mate Soos
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

Solver = namedtuple("Solver", "exe exact dir", defaults=[None, True, None])
Presimp = namedtuple("Presimp", "exe dir", defaults=[None, None])
Count = namedtuple("Count", "solver presimp count", defaults=[None, None, -1])

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
      "--novalgrind", dest="dovalgrind", default=True,
      action="store_false", help="Use valgrind")

    parser.add_option(
      "--valgrindfreq", dest="valgrind_freq", type=int,
      default=10, help="1 out of X times valgrind will be used. Default: %default in 1")

    parser.add_option(
      "--tout", "-t", dest="maxtime", type=int, default=3,
      help="Max time to run. Default: %default")

    parser.add_option(
        "--textra", dest="maxtimediff", type=int, default=2,
        help="Extra time on top of timeout for processing."
        " Default: %default")

    parser.add_option(
      "--ganak", dest="ganak", type=str, default="../ganak/build/ganak",
      help="Location of ganak. Default: %default")

    parser.add_option(
      "--appmc", dest="appmc", type=str, default="../approxmc/build/approxmc",
      help="Location of approxmc. Default: %default")

    parser.add_option(
      "--sharpsat", dest="sharpsat", type=str, default="../sharpSAT/build/sharpSAT",
      help="Location of approxmc. Default: %default")

    parser.add_option(
      "--delta", dest="delta", type=float, default="0.2",
      help="TODO. Default: %default")

    parser.add_option(
      "--epsilon", dest="epsilon", type=float, default="0.2",
      help="TODO. Default: %default")

    return parser


def run(command, dir):
    print("Executing: %s in dir %s" % (" ".join(command), dir))
    if options.verbose:
        print("CPU limit of parent (pid %d)" % os.getpid(), resource.getrlimit(resource.RLIMIT_CPU))

    p = subprocess.Popen(command, stderr=subprocess.STDOUT,
          stdout=subprocess.PIPE, universal_newlines=True, cwd=dir,
          preexec_fn=partial(setlimits, options.maxtime))

    consoleOutput, err = p.communicate()
    if options.verbose:
        print("CPU limit of parent (pid %d) after child finished executing" % os.getpid(),
            resource.getrlimit(resource.RLIMIT_CPU))
    return consoleOutput, err


def gen_fuzz_call(fuzzer, fname):
    seed = random.randint(0, 1000000)
    print("Fuzzer individual seed:", seed)
    call = "{0} {1} > {2}".format(fuzzer, seed, fname)

    return call


def unique_file(fname_begin, fname_end=".cnf"):
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
        if counter > 300:
            print("Cannot create unique_file, last try was: %s" % fname)
            exit(-1)


def run_one_counter(solver, fname):
    curr_time = time.time()
    toexec = solver.exe.split()
    toexec.append(os.getcwd() + "/" + fname)
    if not solver.exact:
        toexec.extend(["--epsilon", str(options.epsilon),
                       "--delta", str(options.delta)])
    out, err = run(toexec, solver.dir)
    if err is not None and err.strip() != "":
        print("Error string is: ", err)
    diff_time = time.time() - curr_time
    if diff_time > options.maxtime - options.maxtimediff:
        print("Too much time to solve with %s, aborted!" % solver.exe)
        return None

    num = None
    for l in out.split("\n"):
        l = l.strip()
        print(l)
        if len(l) < 4:
            continue
        if l[0] == 'c' and l[:3] != "c s":
            continue
        if l[:4] == "s mc" or l[:13] == "c s exact arb":
            if num is not None:
                print("ERROR: Two 's mc' lines in output!!")
                # TODO: print command that got executed
                exit(-1)
            if l[:4] == "s mc":
                num = int(l.split()[2])
            elif l[:13] == "c s exact arb":
                num = int(l.split()[5])
            else:
                print("ERROR")
                exit(-1)
    if num is None:
        print("ERROR, could not find 's mc' or 'c s exact arb int' in output")
        exit(-1)

    return num

def check_header(fname):
    with open(fname, "r") as f:
        num_cls = 0
        max_vars = 0
        header_cls = 0;
        header_vars = 0;
        for line in f:
            line = line.strip()
            if len(line) == 0:
                print("Empty line is NOT part of DIMACS, error\n");
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
            for l in line:
                l = abs(int(l))
                if l > max_vars:
                    max_vars = l


        if num_cls != header_cls:
            print("cls in CNF: %d but header said: %d" % (num_cls, header_cls))
            return False

        if max_vars > header_vars:
            print("max vars was: %d but header said: %d" % (max_vars, header_vars))
            return False
    return True

def run_one_presimp(presimp, fname, fname2):
    curr_time = time.time()
    toexec = presimp.exe.split()
    toexec.append(os.getcwd() + "/" + fname)
    toexec.append(os.getcwd() + "/" + fname2)
    out, err = run(toexec, presimp.dir)
    if err != "":
        print("Error string is: ", err)
    diff_time = time.time() - curr_time
    if diff_time > options.maxtime - options.maxtimediff:
        print("Too much time to presimp with %s, aborted!" % solver.exe)
        return False
    assert check_header(fname2)

if __name__ == "__main__":
    if os.path.exists("out") and  os.path.isfile("out"):
        print("ERROR: file 'out' exists, but we need a directory named 'out'")
        exit(-1)

    if not os.path.isdir("out"):
        print("Directory for outputs, 'out' not present, creating it.")
        os.mkdir("out")

    # parse options
    parser = set_up_parser()
    (options, args) = parser.parse_args()
    if options.valgrind_freq <= 0:
        print("Valgrind Frequency must be at least 1")
        exit(-1)

    if options.rnd_seed is None:
        rnd_seed = random.randint(0, 1000*1000*1000)
        print("Using seed:", rnd_seed)
    else:
        rnd_seed = options.rnd_seed
    random.seed(rnd_seed)

    while True:
        fname = unique_file("fuzzTest")
        print("Checking fname: ", fname)

        # NOTE Baysian network: http://reasoning.cs.ucla.edu/ace/
        # Generate random PB formulas, translate with Stephan Gocht's translator to CNF, and count with CPLEX.
        # Majority vote + if count is small, we can count 1-by-1.
        # Mate TODO: add other binaries from competition, add CNF checker
        # Mate TODO: get https://github.com/vroland/sharptrace working together with https://github.com/vroland/sharpSAT/tree/proof-trace
        call = gen_fuzz_call("./biere-fuzz", fname)
        status = subprocess.call(call, shell=True)
        if status != 0:
            print("Failed call: ", call)
            exit(-1)

        counts = []
        solvers = [
            Solver(options.ganak, True),
            # Solver(options.sharpsat, True),
            Solver(options.appmc, False),
            # Solver("./bins/gpmc-mccomp2022/bin/gpmc -mode=0", True),
            # Solver("./bins/d4-mccomp2022/bin/d4_static -m counting  --output-format competition -p sharp-equiv -i"),
            # Solver("./bins/c2d-mccomp2022/c2d -in ", True),
            # Solver("./sharpSAT -decot 1 -decow 1 -tmpdir tmpdir -cs 5 ", True, "./bins/sharpsat-td-mccomp2022/bin/"),
        ]

        presimps = [
            Presimp("./run.sh", "./bins/bpe-april2016/"),
            Presimp("./run.sh", "./bins/arjun/"),
            Presimp(None, None)
            #Presimp(options.arjun)
        ]

        simplified = []
        for presimp in presimps:
            fname2 = unique_file("fuzzTest")
            if presimp.exe == None:
                shutil.copyfile(fname, fname2)
            else:
                run_one_presimp(presimp, fname, fname2)
            simplified.append((presimp, fname2))

        exact_count = None
        for solver in solvers:
            for presimp, fname2 in simplified:
                count = run_one_counter(solver, fname2)
                if count is not None and solver.exact and presimp.exe is None:
                    exact_count = Count(solver, presimp, count)
                if count is not None:
                    counts.append(Count(solver, presimp, count))

        if exact_count is None:
            os.unlink(fname)
            for _, fname2 in simplified: os.unlink(fname2)
            continue

        for a in counts:
            if a.count != exact_count.count and a.solver.exact:
                print("ERROR!")
                print("%s with presimp %s counted: %s" %(a.exe, a.presimp, a.count))
                print("%s with presimp %s counted: %s" %(exact_count.solver, exact_count.presimp, exact_count.count))
                exit(-1)

            if a.count != exact_count.count and not a.solver.exact:
                print(f"Count is {a.count} for {fname}, but the exact count is {exact_count.count}.")
                print(f"Non-exact is |{exact_count.count} - {a.count}| = {abs(exact_count.count - a.count)} off.")
                print(f"Non-exact is a factor {exact_count.count / float(a.count)} off.")

                if exact_count.count*1.5 < a.count or \
                    exact_count.count*0.7 > a.count:
                        exit(-1)

            print("OK, count is %s. Solve %s with presimp %s matches solver %s count with presimp %s" %
                      (a.count, a.solver.exe, a.presimp, exact_count.solver, exact_count.presimp))

        print("Checking with file %s finished" % fname)
        os.unlink(fname)
        for _, fname2 in simplified: os.unlink(fname2)



