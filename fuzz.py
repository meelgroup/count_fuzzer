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

import json
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
Preproc = namedtuple("Preproc", "exe dir", defaults=[None, None])
Count = namedtuple("Count", "solver preproc count", defaults=[None, None, -1])

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
      "--sandbox", dest="sandbox", default=False,
      action="store_true", help="Do experiments in the sandbox")

    parser.add_option(
      "--valgrindfreq", dest="valgrind_freq", type=int,
      default=10, help="1 out of X times valgrind will be used. Default: %default in 1")

    parser.add_option(
      "--tout", "-t", dest="maxtime", type=int, default=4,
      help="Max time to run. Default: %default")

    parser.add_option(
        "--textra", dest="maxtimediff", type=int, default=1,
        help="Extra time on top of timeout for processing."
        " Default: %default")

    parser.add_option(
      "--appmc", dest="approxmc", type=str, default="../approxmc/build/approxmc",
      help="Location of approxmc. Default: %default")

    parser.add_option(
      "--delta", dest="delta", type=float, default="0.2",
      help="TODO. Default: %default")

    parser.add_option(
      "--epsilon", dest="epsilon", type=float, default="0.2",
      help="TODO. Default: %default")

    parser.add_option(
      "--keep-bugs-only", dest="keep_bugs_only", default=True,
        action="store_true",
        help="Only keep the CNFs that yield bugs, clean up the others. Default: %default")

    parser.add_option(
        "--max-num-files", dest="max_num_files", type=int, default=700,
        help="Maximum number of files to generate. Default: %default")

    parser.add_option(
      "--sample-approxmc", dest="sample_approxmc", default=False,
        action="store_true",
        help="Query ApproxMC for different seeds and store the counts. Default: %default")

    parser.add_option(
        "--num-samples", dest="num_samples", type=int, default=3,
        help="How many samples to take for approximate counters. Default: %default")
    return parser


def run(command, dir):
    print("--> Executing: %s in dir %s" % (" ".join(command), dir))
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

def add_projection(fname) :
    vars = 0
    with open(fname, "r") as f:
        for line in f:
            line = line.strip()
            if len(line) < 3:continue
            if line[0] == "p":
                line = line.split(" ")
                assert line[1].strip() == "cnf"
                vars = int(line[2])

    all_vars = []
    for i in range(vars): all_vars.append(i+1)
    proj = []
    optproj = []
    if vars == 0:
        print("ERROR: Can't find 'p cnf' in file %s" % fname)
        exit(-1)

    num : int = random.randint(1, int(len(all_vars)/4))
    for i in range(num):
        proj.append(i+1)

    num : int = random.randint(min(len(proj)+20, len(all_vars)), len(all_vars))
    for i in range(num):
        optproj.append(i+1)

    with open(fname, "a") as f:
        f.write("c p show ")
        for a in proj:
            f.write("%d " % a)
        f.write("0\n")
        # f.write("c p optshow ")
        # for a in optproj:
        #     f.write("%d " % a)
        # f.write("0\n")

def gen_fuzz_call_biere(fuzzer, fname):
    seed = random.randint(0, 1000000)
    call = "{0} {1} > {2}".format(fuzzer, seed, fname)
    return call


def gen_fuzz_call_brummayer(fuzzer, fname):
    seed = random.randint(0, 1000000)
    call = "{0} -I 21 -s {1} > {2}".format(fuzzer, seed, fname)
    return call


def unique_file(fname_begin, fname_end=".cnf", max_num_files=700):
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


def run_one_counter(solver, fname, seed=42):
    curr_time = time.time()
    toexec = solver.exe.split()
    toexec.append(os.getcwd() + "/" + fname)
    if not solver.exact:
        toexec.extend(["--epsilon", str(options.epsilon),
                       "--delta", str(options.delta),
                       "-s", str(seed)])
    out, err = run(toexec, solver.dir)
    if err is None:
        if options.verbose:
            print("No error.")
    else:
        print("Error string is: ", err)
    diff_time = time.time() - curr_time
    if diff_time > options.maxtime - options.maxtimediff:
        print("Too much time to solve with %s, aborted!" % solver.exe)
        return True, None

    num = None
    for l in out.split("\n"):
        l = l.strip()
        if options.verbose:
            print(l)
        if len(l) < 4:
            continue
        if l[0] == 'c' and l[:3] != "c s":
            continue
        if l[:4] == "s mc" or l[:13] == "c s exact arb" or l[:5] == "s pmc":
            if num is not None:
                print("ERROR: Two 's mc' lines in output!!")
                # TODO: print command that got executed
                exit(-1)
            if l[:4] == "s mc" or l[:5] == "s pmc":
                num = int(l.split()[2])
            elif l[:13] == "c s exact arb":
                num = int(l.split()[5])
            else:
                print("ERROR")
                exit(-1)
    if num is None:
        print("ERROR, could not find 's mc' or 'c s exact arb int' in output")
        return False, None

    return True, num

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

def run_one_preproc(preproc, fname, fname2):
    curr_time = time.time()
    toexec = preproc.exe.split()
    toexec.append(os.getcwd() + "/" + fname)
    toexec.append(os.getcwd() + "/" + fname2)
    print("Executing preproc ", preproc)
    out, err = run(toexec, preproc.dir)
    if err is None:
        pass
    else:
        print("Error string is: ", err)
        print("output was: ", out)
    diff_time = time.time() - curr_time
    if diff_time > options.maxtime - options.maxtimediff:
        print("Too much time to preproc with %s, aborted!" % solver.exe)
        return False
    assert check_header(fname2)
    return True

if __name__ == "__main__":
    if os.path.exists("out") and  os.path.isfile("out"):
        print("ERROR: file 'out' exists, but we need a directory named 'out'")
        exit(-1)

    if not os.path.isdir("out"):
        print("Directory for outputs, 'out' not present, creating it.")
        os.mkdir("out")

    # Create directories needed to run fuzzer
    os.makedirs("sandbox/approxmc-results/arjun", exist_ok=True)
    os.makedirs("sandbox/approxmc-results/nopreproc", exist_ok=True)
    os.makedirs("sandbox/approxmc-results/bpe", exist_ok=True)
    os.makedirs("tmpdir", exist_ok=True)
    os.makedirs("out", exist_ok=True)

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
        if options.rnd_seed is None:
            seed  = random.randint(0, 1000*1000*1000)
            random.seed(seed)
        else:
            seed = options.rnd_seed
        proj :bool = random.choice([True, False])
        fname = unique_file("fuzzTest", max_num_files=options.max_num_files)
        print("Seed: ", seed, " proj: ", proj, " checking fname: ", fname)

        # NOTE Baysian network: http://reasoning.cs.ucla.edu/ace/
        # Generate random PB formulas, translate with Stephan Gocht's translator to CNF, and count with CPLEX.
        # Majority vote + if count is small, we can count 1-by-1.
        # Mate TODO: add other binaries from competition, add CNF checker
        # Mate TODO: get https://github.com/vroland/sharptrace working together with https://github.com/vroland/sharpSAT/tree/proof-trace
        call = random.choice([
            gen_fuzz_call_biere("./biere-fuzz", fname),
            gen_fuzz_call_brummayer("./cnf-fuzz-brummayer.py", fname)])
        # print("TODO: ./dnfstream --eager 1 a.cnf -e 0.01 --delta 0.01 out.dnf");
        # print("TODO: ./cnftranslate out.dnf out.cnf");

        status = subprocess.call(call, shell=True)
        if status != 0:
            print("Failed fuzzer file generator call: ", call)
            exit(-1)
        else:
            print("Generated fuzz file %s with call: %s" % (fname, call));

        if proj:
            add_projection(fname)
        counts = []
        solvers = [
            # Solver("../approxmc/build/approxmc", False),
            # Solver("../approxmc/build/approxmc --withe 0", False),
            # Solver("../approxmc/build/approxmc --arjun 0", False),
            # Solver("../old_ganak/build/ganak", True),

            Solver("../ganak/build/ganak --maxcache 100 --td 0 --arjun 1", True),
            Solver("../ganak/build/ganak --maxcache 100 --td 0 --arjun 0", True),
            # Solver("../ganak/build/ganak --maxcache 100 --td 0 --arjun 0 --rdbeveryn 20 --consolidateevery 40 --rdbclstarget 40 --vivif 1 --vivifevery 30", True),
            # Solver("../ganak/build/ganak --maxcache 100 --td 0 --arjun 1 --rdbeveryn 20 --consolidateevery 30 --rdbclstarget 40 --vivif 1 --vivifevery 40", True),

            # Solver("./bins/d4-mccomp2022/bin/d4_static -m counting  --output-format competition -p sharp-equiv -i"),
            # Solver("./bins/c2d-mccomp2022/c2d -in ", True),
            # Solver("./sharpSAT -decot 1 -decow 1 -tmpdir tmpdir -cs 5 ", True, "./bins/sharpsat-td-mccomp2022/bin/")
        ]

        if proj:
            # solvers.append(Solver("./bins/gpmc-2023/gpmc -mode=2", True));
            pass
        else:
            # solvers.append(Solver("./bins/gpmc-2023/gpmc -mode=0", True));
            pass


        preprocs = [
            # Preproc("./run.sh", "./bins/bpe-april2016/"),
            # Preproc("./run.sh", "./bins/arjun-withind/"),
            # Preproc("./run.sh", "./bins/arjun-withind-extend/"),
            Preproc(None, None)
        ]
        # if not proj: preprocs.append(Preproc("./run.sh", "./bins/arjun/"))

        simplified = []
        for preproc in preprocs:
            fname2 = unique_file("fuzzTest", max_num_files=options.max_num_files)
            OK = False
            if preproc.exe == None:
                shutil.copyfile(fname, fname2)
                OK = True
                if options.verbose:
                    print("Copied file %s to %s for the empty preproc" % (fname, fname2))
            else:
                OK = run_one_preproc(preproc, fname, fname2)
                if options.verbose:
                    print("Generated file %s by preproc %s which preprocessed %s" % (fname2, preproc.exe, fname))
            if OK: simplified.append((preproc, fname2))
            else: os.unlink(fname2)

        exact_count = None
        print("Set of solvers is: ", solvers)
        if len(solvers) == 1:
            print("ERROR, it makes no sense to run a single solver, exiting")
            exit(-1)

        for solver in solvers:
            for preproc, fname2 in simplified:
                if (preproc.exe is not None and "arjun" in preproc.exe) and \
                        ("ganak" not in solver.exe and "approx" not in solver.exe):
                    # only GANAK and ApproxMC understand "MUST MULTIPLY BY"
                    continue
                OK, count = run_one_counter(solver, fname2)
                if not OK and ("ganak" in solver.exe or "approx" in solver.exe):
                    print("Error running ", solver)
                    exit(-1)
                print("got back: ", OK, " , ", count)
                if count is not None and solver.exact and preproc.exe is None:
                    exact_count = Count(solver, preproc, count)
                if count is not None:
                    counts.append(Count(solver, preproc, count))
                if (count is not None) and count > 10000 and ('approxmc' in solver.exe) and options.sandbox:
                    samples = []
                    preproc_name = "nopreproc"
                    if preproc.exe is not None:
                        preproc_name = 'arjun' if 'arjun' in preproc.exe else 'bpe'
                    print("fname is: ", fname)
                    new_fname = fname.replace('out/', f'sandbox/approxmc-results/{preproc_name}/')
                    new_fname2 = fname2.replace('out/', f'sandbox/approxmc-results/{preproc_name}/')
                    shutil.copyfile(fname, new_fname)
                    shutil.copyfile(fname2, new_fname2)
                    data = {
                        'samples': samples,
                        'epsilon': options.epsilon,
                        'delta': options.delta,
                        'fname': new_fname,
                        'fname2': new_fname2,
                        'preproc': preproc_name,
                    }
                    for i in range(options.num_samples):
                        count = run_one_counter(solver, new_fname2, seed=i)
                        if count is not None:
                             print("COUNT:", count)
                             data['samples'].append((i, int(count)))
                             with open(f'{new_fname2}.json', 'w') as fp:
                                 json.dump(data, fp)

        if exact_count is None:
            os.unlink(fname)
            for _, fname2 in simplified:
                os.unlink(fname2)
            continue

        print("counts is: ", counts)
        for a in counts:
            if a.count != exact_count.count and a.solver.exact:
                print("ERROR!")
                print("%s with preproc %s counted: %s" %(a.solver, a.preproc, a.count))
                print("%s with preproc %s counted: %s" %(
                    exact_count.solver, exact_count.preproc, exact_count.count))
                exit(-1)

            if a.count != exact_count.count and not a.solver.exact:
                print(f"Count is {a.count} for {fname}, but the exact count is {exact_count.count}.")
                print(f"Non-exact is |{exact_count.count} - {a.count}| = {abs(exact_count.count - a.count)} off.")
                print(f"Non-exact is a factor {exact_count.count / float(a.count)} off.")

                if exact_count.count*1.5 < a.count or \
                    exact_count.count*0.7 > a.count:
                        exit(-1)

            print("OK, count is %s. Solve %s with preproc %s matches solver %s count with preproc %s" %
                      (a.count, a.solver.exe, a.preproc, exact_count.solver, exact_count.preproc))

        print(" --------------------------- \n")
        if options.rnd_seed is not None:
            print("Exiting as we only wanted to run one test due to --seed")
            exit(0)

        print("Checking with file %s finished" % fname)
        if options.keep_bugs_only:
            os.unlink(fname)
            for _, fname2 in simplified: os.unlink(fname2)




