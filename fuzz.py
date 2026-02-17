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
maxtimediff = 1

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
      "--only", type=int, dest="only", default=2**40,
      help="Only run N tests. Default: %default")

    parser.add_option(
      "--cpx", dest="cpx", default=False,
      action="store_true", help="Complex numbers only")

    parser.add_option(
      "--weighted", dest="weighted", default=False,
      action="store_true", help="Weighted only")

    parser.add_option(
      "--unweighted", dest="unweighted", default=False,
      action="store_true", help="UnWeighted only")

    parser.add_option(
      "--proj", dest="projected", default=False,
      action="store_true", help="Projected only")

    parser.add_option(
      "--unproj", dest="unprojected", default=False,
      action="store_true", help="UNProjected only")

    parser.add_option(
      "--tout", "-t", dest="maxtime", type=int, default=4,
      help="Max time to run. Default: %default")

    parser.add_option(
      "--nomessyweight", dest="messy_weights", default=True,
      action="store_false", help="With this, weights are NOT fully given, and can contain negative values")

    parser.add_option(
      "--noimag", dest="noimag", default=False, action="store_true",
      help="Set imag to 0. Default: %default")

    # sandbox, sampling ,etc
    parser.add_option(
      "--sandbox", dest="sandbox", default=False,
      action="store_true", help="Do experiments in the sandbox")

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
          stdout=subprocess.PIPE, universal_newlines=True, cwd=dir)

    try:
        consoleOutput, err = p.communicate(timeout=options.maxtime)
    except subprocess.TimeoutExpired:
        p.kill()
        consoleOutput, err = p.communicate()
        consoleOutput = "TIMEOUT: Process killed after %d seconds\n" % options.maxtime + consoleOutput

    if options.verbose:
        print("CPU limit of parent (pid %d) after child finished executing" % os.getpid(),
            resource.getrlimit(resource.RLIMIT_CPU))
    return consoleOutput, err

def add_weights(fname, projected_vars) :
    vars = 0
    with open(fname, "r") as f:
        for line in f:
            line = line.strip()
            if len(line) < 3:continue
            if line[0] == "p":
                line = line.split(" ")
                assert line[1].strip() == "cnf"
                vars = int(line[2])
    if vars == 0:
        print("ERROR: Can't find 'p cnf' in file %s" % fname)
        exit(-1)

    all_vars = []
    if projected_vars is not None:
        all_vars = list(projected_vars)
    else:
        all_vars = []
        for i in range(vars):
            all_vars.append(i+1)

    weights = []
    if options.messy_weights:
        for var in all_vars:
            if random.choice([True, False]):
                w = float(random.randrange(-10, 10))/10.0
                weights.append([var, w])
            if random.choice([True, False]):
                w2 = float(random.randrange(-10, 10))/10.0
                weights.append([-var, w2])
    else:
        for var in all_vars:
            w = float(random.randrange(0, 10))/10.0
            weights.append([var, w])
            weights.append([-var, 1.0-w])

    with open(fname, "a") as f:
        for v,w in weights:
            f.write("c p weight %d %lf 0\n" % (v, w))

def add_weights_cpx(fname, projected_vars) :
    vars = 0
    with open(fname, "r") as f:
        for line in f:
            line = line.strip()
            if len(line) < 3:continue
            if line[0] == "p":
                line = line.split(" ")
                assert line[1].strip() == "cnf"
                vars = int(line[2])
    if vars == 0:
        print("ERROR: Can't find 'p cnf' in file %s" % fname)
        exit(-1)

    all_vars = []
    if projected_vars is not None:
        all_vars = list(projected_vars)
    else:
        all_vars = []
        for i in range(vars):
            all_vars.append(i+1)

    weights = []
    if options.messy_weights:
        for var in all_vars:
            if random.choice([True, False]):
                w = float(random.randrange(-10, 10))/10.0
                w2 = float(random.randrange(-10, 10))/10.0
                weights.append([var, w, w2])
                w = float(random.randrange(-10, 10))/10.0
                w2 = float(random.randrange(-10, 10))/10.0
                weights.append([-var, w, w2])
    else:
        for var in all_vars:
            w = float(random.randrange(0, 10))/10.0
            w2 = float(random.randrange(0, 10))/10.0
            weights.append([var, w, w2])
            weights.append([-var, 1.0-w, 1-w2])

    weights2 = list(weights)
    weights = []
    if options.noimag:
        for v,w,w2 in weights2:
            w2 = 0.0
            weights.append([v, w, w2])
    else: weights = weights2

    with open(fname, "a") as f:
        for v,w,w2 in weights:
            f.write("c p weight %d %lf %lf 0\n" % (v, w, w2))

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
    proj_set = {}
    if vars == 0:
        print("ERROR: Can't find 'p cnf' in file %s" % fname)
        exit(-1)

    if random.choice([True, False]):
        num : int = random.randint(int(len(all_vars)/15), int(len(all_vars)/5))
        if random.choice([True, False]):
            num = min(2, len(all_vars))
    else:
        num : int = random.randint(int(len(all_vars)/4), int(len(all_vars)/3))
    for i in range(num):
        proj_set[random.choice(all_vars)] = 1

    for a,_ in proj_set.items():
        proj.append(a)

    with open(fname, "a") as f:
        f.write("c p show ")
        for a in proj:
            f.write("%d " % a)
        f.write("0\n")
    return proj

def get_type(proj, weighted):
    ty = "0"
    if proj and not weighted: ty = "1"
    if not proj and weighted: ty = "2"
    if proj and weighted: ty = "3"
    return ty

def gen_fuzz_call_biere(fuzzer, fname, proj, weighted):
    seed = random.randint(0, 1000*1000*1000)
    ty = get_type(proj, weighted)
    call = "{0} {1} {2} > {3}".format(fuzzer, seed, ty, fname)
    return call


def gen_fuzz_call_brummayer(fuzzer, fname, proj, weighted):
    seed = random.randint(0, 1000*1000*1000)
    ty = get_type(proj, weighted)
    call = "{0} -s {1} -T {2} > {3}".format(fuzzer, seed, ty, fname)
    return call


def unique_file(fname_begin, fname_end=".cnf", max_num_files=2700):
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
        last = toexec[len(toexec)-1]
        toexec = toexec[:len(toexec)-1]
        toexec.extend(["-s", str(seed)])
        toexec.extend([last])

    if "ganak" in solver.exe:
        if random.randint(1,4) == 4:
            toexec = "valgrind --leak-check=full --track-origins=yes".split() + toexec
    out, err = run(toexec, solver.dir)
    if err is None:
        if options.verbose:
            print("No error.")
    else:
        print("Error string is: ", err)
    diff_time = time.time() - curr_time
    if diff_time > options.maxtime - maxtimediff:
        print("Too much time to solve with %s, aborted!" % solver.exe)
        return True, None

    num = None
    unsat_found = False
    for l in out.split("\n"):
        l = l.strip()
        if options.verbose:
            print(l)
        if "s UNSATIS" in l:
            unsat_found = True
        if "Assertion " in l and "failed" in l:
            return False, None
        # if "sat call" in l:
        #     print(l)
        if "ERROR Memory out!" in l:
            return True, None
        if "blocks are definitely lost" in l:
            print("ERROR: Memory leak in solver %s, output was: " % solver.exe)
            for l in out.split("\n"):
                l = l.strip()
                print(l)
            return False, None
        if "ERROR" in l:
            if ("ERROR SUMMARY" not in l):
                print("ERROR in output: ", l)
                for l in out.split("\n"):
                    l = l.strip()
                    print(l)
                return False, None
        if len(l) < 4:
            continue
        if "c s exact arb cpx" in l:
            # c s exact arb cpx 1.2650e+02 + -6.3250e+01i
            real = float(l.split()[5].strip())
            imag = float(l.split()[7].strip()[:-1])
            print("Complex number is: ", real, " ## ", imag)
            num = complex(real, imag)
            continue
        if l[0] == 'c' and l[:3] != "c s":
            continue
        if l[:4] == "s mc" or l[:13] == "c s exact arb" or l[:5] == "s pmc" or "s approx arb int" in l or "c s exact" in l:
            if num is not None:
                print("ERROR: Two 's mc' lines in output!!")
                # TODO: print command that got executed
                exit(-1)
            if cpx:
                if unsat_found:
                    num = complex(0, 0)
                else:
                    # c s exact double prec-sci 0+0i
                    real = float(l.split()[5].strip())
                    imag = float(l.split()[7].strip()[:-1])
                    print("Complex number is: ", real, " ## ", imag)
                    num = complex(real, imag)
            elif l[:4] == "s mc" or l[:5] == "s pmc":
                num = int(l.split()[2])
            elif "c s exact arb int" in l:
                num = float(l.split()[5])
            elif "c s exact arb float " in l:
                num = float(l.split()[5])
            elif "c s exact quadruple float interval [" in l:
                # using left interval bound, TODO: chek the right one as well
                num = float(l.split()[7])
            elif "c s exact quadruple float" in l:
                num = float(l.split()[5])
            elif "c s exact arb int" in l:
                num = int(l.split()[5])
            elif "c s exact arb frac" in l:
                frac = l.split()[5].split("/")
                num1 = int(frac[0])
                if len(frac) < 2:
                    num = float(num1)
                else:
                    num2 = int(l.split()[5].split("/")[1])
                    num = float(num1)/ float(num2)
            elif "s exact double prec-sci" in l:
                num = float(l.split()[5])
            elif "c s approx arb int" in l:
                num = float(l.split()[5])
            else:
                print("ERROR")
                exit(-1)
    if unsat_found:
        return True, 0

    if num is None:
        print("ERROR, could not find 's mc', 'c s exact arb int', or 'c s exact arb frac' or 'c s approx arb int' in output")
        for l in out.split("\n"):
            print(l.strip())
        if ("ganak" in solver.exe or "approx" in solver.exe): return False, None
        else :
            print("Not erroring out, it's not our solver")
            return True, None

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
    if diff_time > options.maxtime - maxtimediff:
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

    if options.rnd_seed is None:
        b = os.urandom(8)
        rnd_seed = int.from_bytes(b)
        print("Using seed:", rnd_seed)
    else:
        rnd_seed = options.rnd_seed
    random.seed(rnd_seed)

    for i in range(options.only):
        if options.rnd_seed is None:
            b = os.urandom(8)
            seed = int.from_bytes(b)
            random.seed(seed)
        else:
            seed = options.rnd_seed
        proj :bool = random.choice([True, False])
        if (options.projected): proj = True
        if (options.unprojected): proj = False

        weighted :bool = random.choice([True, False])
        if (options.weighted): weighted = True
        if (options.unweighted): weighted = False

        cpx = options.cpx
        if cpx:
            proj = False
            weighted = True

        fname = unique_file("fuzzTest")
        print("Seed: ", seed, " projected: ", proj, "weighted: ", weighted, " checking fname: ", fname)

        # NOTE Baysian network: http://reasoning.cs.ucla.edu/ace/
        # Generate random PB formulas, translate with Stephan Gocht's translator to CNF, and count with CPLEX.
        # Majority vote + if count is small, we can count 1-by-1.
        # Mate TODO: add other binaries from competition, add CNF checker
        # Mate TODO: get https://github.com/vroland/sharptrace working together with https://github.com/vroland/sharpSAT/tree/proof-trace
        call = random.choice([
            gen_fuzz_call_biere("./biere-fuzz", fname, proj, weighted),
            gen_fuzz_call_brummayer("./cnf-fuzz-brummayer.py", fname, proj, weighted)])
        # print("TODO: ./dnfstream --eager 1 a.cnf -e 0.01 --delta 0.01 out.dnf");
        # print("TODO: ./cnftranslate out.dnf out.cnf");

        print("Calling: ", call)
        status = subprocess.call(call, shell=True)
        if status != 0:
            print("Failed fuzzer file generator call: ", call)
            exit(-1)
        else:
            print("Generated fuzz file %s with call: %s" % (fname, call));

        projected_vars = None
        if proj:
            projected_vars = add_projection(fname)
        if not cpx and weighted:
            add_weights(fname, projected_vars)
        if cpx:
            add_weights_cpx(fname, projected_vars)
        counts = []
        solvers = [
            # Solver("../ganak/build/ganak --verb 0 --buddy 1 --td 0 ", True),
            # Solver("../ganak/build/ganak --verb 0 --satsolver 0 --arjun 0 --td 0", True),
            # Solver("../ganak/build/ganak --verb 0 --satsolver 0 --chronobt 0 --arjun 0 --td 0", True),
            # Solver("../ganak/build/ganak --verb 0 --satrstmult 1 --arjun 0 --td 0", True),
            # Solver("./bins/d4-mccomp2022/bin/d4_static -m counting  --output-format competition -i"),
            # Solver("./bins/c2d-mccomp2022/c2d -in ", True),
        ]

        delta = random.choice([0.2, 0.4, 0.6])
        epsilon = random.choice([0.8, 6.0])
        ganak_exact = True
        ganak_extra = \
            " --rstfirst " + random.choice(["100", "10000"]) +\
            " --arjuncmsmult " +  random.choice(["0.0001", "1"]) +\
            " --epsilon " + str(epsilon) +\
            " --delta " + str(delta) +\
            " --puuraautarky " + random.choice(["1", "0"]) +\
            " --puura " + random.choice(["0", "1", "1"]) +\
            " --arjunsamplcutoff  " + random.choice(["2", "10", "100000"]) +\
            " --td " + random.choice(["1", "0", "0"]) +\
            " --tdlooktwcut " + random.choice(["2", "5"]) +\
            " --tditers " + str(random.randint(0,30)) +\
            " --tdsteps " + str(random.randint(0, 1000)) +\
            " --bitsjobs " + random.choice(["1", "3", "5"]) +\
            " --mpfrprecision " + random.choice(["100", "80", "256"]) +\
            " --arjunweakenlim " + random.choice(["8000", "10", "100000"]) +\
            " "
            # " --hc " + random.choice(["1", "1", "0"]) +\
        binary_options = [ "arjunoraclefindbins" ,"bce" ,"prob" ,"puurabackbone" ,"tdlook "
                          ,"tdoptindep", "resolvsub", "arjunextendccnr"]
        for opt in binary_options:
            ganak_extra += " --" + opt + " " + random.choice(["0", "1"]) + " "

        if random.choice([False, False, False, True]):
            ganak_extra += " --appmct " + random.choice(["0.3"])
            ganak_exact = False

        if ganak_exact and random.choice([False, False, False, True]):
            ganak_extra += " --threads 4"

        approx_extra = " --epsilon " + str(epsilon) +\
            " --delta " + str(delta) + " " +\
            " --arjun " + random.choice(["0", "1"]) + " "

        # ganak modes: --mode                  0=counting, 1=weighted counting, 2=complex numbers, 3=multivariate polynomials over the rational field, 4=parity counting, 5=counting over prime field, 6=mpfr complex numbers, 7=mpfr normal numbers [nargs=0..1] [default: 0]

        if not weighted:
            solvers.extend([
            Solver("../approxmc/build/approxmc " + approx_extra, False),
            # Solver("../ganak/build/ganak --mode 0 --verb 0 --arjun 0 --td 0", False),
            Solver("../ganak/build/ganak --mode 0 --verb 0 " + ganak_extra, ganak_exact),
            ])
        else:
            solvers.extend([
            Solver("../ganak/build/ganak --mode 1 --verb 0 --arjun 0 --td 0", True),
            # appmc is not working in weighted mode, so always exact
            Solver("../ganak/build/ganak --mode 7 --verb 0 " + ganak_extra, True),
            # try interval arithmetic for weighted counting
            Solver("../ganak/build/ganak --mode 8 --verb 0 " + ganak_extra, True),
                # Solver("./KCBox ExactMC --heur minfill --competition --weighted --memo 4  --mpf_prec 20 --quiet", True, "./bins/exactmc-2023"),
                # Solver("./sharpSAT -WE -decot 1 -decow 1 -tmpdir tmpdir -cs 5 --prec 20 ", True, "./bins/sharpsat-td-precise/bin/")
            ])

        if weighted and proj:
            solvers.extend([
                # Solver("../gpmc2023/gpmc -mode=3", True),
            ])
        if weighted and not proj:
            solvers.extend([
                # Solver("../gpmc2023/gpmc -mode=1", True),
            ])

        if cpx:
            weighted = True
            proj = False
            solvers = [
                Solver("../ganak/build/ganak --mode 6 --verb 0 --arjun 0 --td 0", True),
                # appmc is not working in weighted mode, so always exact
                Solver("../ganak/build/ganak --mode 6 --verb 0 " + ganak_extra, True),
                Solver("./gpmc -mode=1", True, "./bins/gpmc-complex/"),
                ]

        preprocs = [
            # Preproc("./run.sh", "./bins/bpe-april2016/"),
            # Preproc("./run.sh", "./bins/arjun-withind/"),
            # Preproc("./run.sh", "./bins/arjun-withind-extend/"),
            Preproc(None, None)
        ]

        simplified = []
        for preproc in preprocs:
            fname2 = unique_file("fuzzTest")
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
                if not OK:
                    print("Error running ", solver)
                    exit(-1)
                print("got back: ", OK, " , ", count)
                if count is not None and solver.exact and preproc.exe is None:
                    exact_count = Count(solver, preproc, count)
                if count is not None:
                    counts.append(Count(solver, preproc, count))
                if not cpx and (count is not None) and count > 10000 and ('approx' in solver.exe) and options.sandbox:
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
                        'epsilon': epsilon,
                        'delta': delta,
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
            if options.rnd_seed is not None:
                print("Exiting as we only wanted to run one test due to --seed")
                exit(0)
            os.unlink(fname)
            for _, fname2 in simplified:
                os.unlink(fname2)
            continue

        print("counts is: ", counts)
        def perc_diff(a, b):
            amnt = abs(a.real-b.real) + abs(a.imag-b.imag)
            val_r = abs(b.real) + abs(b.imag)
            val = amnt/val_r
            # print("perc diff is: ", val)
            return val

        def abs_diff(a, b):
            amnt = abs(a.real-b.real) + abs(a.imag-b.imag)
            return amnt

        for (a,b) in zip(counts, solvers):
            if weighted:
                assert(a.solver.exact)
                if a.count != exact_count.count and perc_diff(a.count, exact_count.count) > 0.02 and abs_diff(a.count, exact_count.count) > 1e-50:
                    print("ERROR: One weighted count is %s, but other count is %s" % (a.count, exact_count.count))
                    exit(-1)

            if not weighted:
                if a.count != exact_count.count and a.solver.exact:
                    print("ERROR!")
                    print("%s with preproc %s counted: %s" %(a.solver, a.preproc, a.count))
                    print("%s with preproc %s counted: %s" %(
                        exact_count.solver, exact_count.preproc, exact_count.count))
                    exit(-1)

                if a.count != exact_count.count and not a.solver.exact:
                    max_allowed = exact_count.count * (1.0 + epsilon)
                    min_allowed = exact_count.count * (1.0 / (1.0 + epsilon))

                    print(f"Count is {a.count} for {fname}, but the exact count is {exact_count.count}.")
                    print(f"Non-exact is |{exact_count.count} - {a.count}| = {abs(exact_count.count - a.count)} off.")
                    print(f"Non-exact is a factor {exact_count.count / float(a.count)} off.")
                    print(f"With epsilon = {epsilon}, min_allowed = {min_allowed}, max_allowed = {max_allowed}.")
                    print(f"Wrong counting: {a.solver.exe} with preproc {a.preproc}")
                    if a.count > max_allowed or a.count < min_allowed:
                        wrong = 0
                        numruns = 50
                        num = 0
                        failed = 0
                        while num < numruns and failed < 5:
                            OK, count2 = run_one_counter(a.solver, fname, random.randint(0, 1000*1000*1000))
                            if count2 is None:
                                failed+=1
                                continue
                            num += 1
                            print(f"Rerun gives count = {count2}")
                            if not OK:
                                print("ERROR: rerun failed?")
                                exit(-1)
                            if count2 > max_allowed or count2 < min_allowed:
                                wrong += 1
                        if failed < 5:
                            perc_wrong = float(wrong) / float(numruns) * 100.0
                            print(f"Out of {numruns} reruns, {wrong} were outside the allowed range, percentage {perc_wrong}%")

                            allowed_perc_wrong = (delta) * 100.0
                            if perc_wrong > allowed_perc_wrong:
                                print("ERROR: Delta was exceeded. It was allowed to be only %s %%" % allowed_perc_wrong)
                                exit(-1)
                            else:
                                print("OK within delta after reruns. Delta was %s %%" % allowed_perc_wrong)
                        else:
                            print("Too many failed reruns, not checking delta.")


            print("OK, count is %s. Solve %s with preproc %s matches solver %s count with preproc %s" %
                      (a.count, a.solver.exe, a.preproc, exact_count.solver, exact_count.preproc))

        print(" --------------------------- \n")
        if options.rnd_seed is not None:
            print("Exiting as we only wanted to run one test due to --seed")
            exit(0)

        print("Checking with file %s finished" % fname)
        os.unlink(fname)
        for _, fname2 in simplified: os.unlink(fname2)




