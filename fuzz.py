#!/usr/bin/env python3

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

import optparse
import os
import random
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
from collections import namedtuple

Solver = namedtuple("Solver", "exe exact cwd", defaults=[None, True, None])
Preproc = namedtuple("Preproc", "exe cwd", defaults=[None, None])
Count = namedtuple("Count", "solver preproc count", defaults=[None, None, -1])

RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
BOLD = "\033[1m"
NC = "\033[0m"
maxtimediff = 1

current_proc = None

def _cleanup_and_exit(_signum, _frame):
    if current_proc is not None and current_proc.poll() is None:
        current_proc.kill()
        current_proc.wait()
    sys.exit(0)

signal.signal(signal.SIGHUP, _cleanup_and_exit)
signal.signal(signal.SIGTERM, _cleanup_and_exit)

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
      "--buddy", dest="buddy", default=False,
      action="store_true", help="Fuzz buddy, too")

    parser.add_option(
      "--disable-no-touch", dest="disable_no_touch", default=False,
      action="store_true", help="Don't use no-touch")

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
      "--zerocomps", dest="zerocomps", default=False,
      action="store_true", help="With this, weights are MESSY and they often add up to 0")

    parser.add_option(
        "--num-samples", dest="num_samples", type=int, default=3,
        help="How many samples to take for approximate counters. Default: %default")

    parser.add_option(
      "--threads", dest="threads", type=int, default=None,
      help="If set, fuzz ONLY with --threads K given to ganak. Default: random")

    return parser


def run(command, cwd):
    global current_proc
    if options.verbose:
        print(f"{MAGENTA}--> Executing: {NC}{' '.join(command)} in dir {cwd}")

    proc = subprocess.Popen(command, stderr=subprocess.STDOUT,
          stdout=subprocess.PIPE, universal_newlines=True, cwd=cwd)
    current_proc = proc

    try:
        out, _ = proc.communicate(timeout=options.maxtime)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, _ = proc.communicate()
        out = f"TIMEOUT: Process killed after {options.maxtime} seconds\n" + out

    current_proc = None
    return out, proc.returncode

def weighted_vars(cnf_path, projected_vars):
    nvars = get_nvars(cnf_path)
    if nvars == 0:
        print(f"ERROR: Can't find 'p cnf' in file {cnf_path}")
        sys.exit(-1)
    if projected_vars is not None:
        return list(projected_vars)
    return list(range(1, nvars+1))

def add_weights(cnf_path, projected_vars) :
    all_vars = weighted_vars(cnf_path, projected_vars)
    weights = []
    if options.zerocomps:
        for var in all_vars:
            weights.append([var, float(random.choice([-2, -1, 1, 2]))])
    elif options.messy_weights:
        for var in all_vars:
            if random.choice([True, False]):
                pos_w = float(random.randrange(-10, 10))/10.0
                weights.append([var, pos_w])
            if random.choice([True, False]):
                neg_w = float(random.randrange(-10, 10))/10.0
                weights.append([-var, neg_w])
    else:
        for var in all_vars:
            pos_w = float(random.randrange(0, 10))/10.0
            weights.append([var, pos_w])
            weights.append([-var, 1.0-pos_w])

    with open(cnf_path, "a") as f:
        for lit, weight in weights:
            f.write(f"c p weight {lit} {weight:f} 0\n")

def add_weights_cpx(cnf_path, projected_vars) :
    all_vars = weighted_vars(cnf_path, projected_vars)
    weights = []
    if options.zerocomps:
        for var in all_vars:
            real = float(random.choice([-1, 1]))
            imag = float(random.choice([-1, 1]))
            weights.append([var, real, imag])
    elif options.messy_weights:
        for var in all_vars:
            if random.choice([True, False]):
                real = float(random.randrange(-10, 10))/10.0
                imag = float(random.randrange(-10, 10))/10.0
                weights.append([var, real, imag])
                real = float(random.randrange(-10, 10))/10.0
                imag = float(random.randrange(-10, 10))/10.0
                weights.append([-var, real, imag])
    else:
        for var in all_vars:
            real = float(random.randrange(0, 10))/10.0
            imag = float(random.randrange(0, 10))/10.0
            weights.append([var, real, imag])
            weights.append([-var, 1.0-real, 1-imag])

    with open(cnf_path, "a") as f:
        for lit, real, imag in weights:
            f.write(f"c p weight {lit} {real:f} + {imag:f}i 0\n")

def get_nvars(cnf_path):
    with open(cnf_path, "r") as f:
        for line in f:
            line = line.strip()
            if len(line) < 3:
                continue
            if line[0] == "p":
                line = line.split(" ")
                assert line[1].strip() == "cnf"
                return int(line[2])
    return 0

# "c p no-touch" is the prefix 1..k, and all of it must also be in "c p show"
def pick_num_no_touch(nvars):
    if nvars < 2 or random.choice([True, False]):
        return 0
    return random.randint(1, max(1, int(nvars/4)))

def add_no_touch(cnf_path, num_no_touch):
    if num_no_touch == 0:
        return
    with open(cnf_path, "a") as f:
        f.write("c p no-touch ")
        for i in range(num_no_touch):
            f.write(f"{i+1} ")
        f.write("0\n")
    print(f"{MAGENTA}--> Added no-touch header{NC} to {cnf_path} for vars 1..{num_no_touch}")

def add_projection(cnf_path, num_no_touch) :
    nvars = get_nvars(cnf_path)
    if nvars == 0:
        print(f"ERROR: Can't find 'p cnf' in file {cnf_path}")
        sys.exit(-1)

    all_vars = list(range(1, nvars+1))
    if random.choice([True, False]):
        num_proj = random.randint(int(len(all_vars)/15), int(len(all_vars)/5))
        if random.choice([True, False]):
            num_proj = min(2, len(all_vars))
    else:
        num_proj = random.randint(int(len(all_vars)/4), int(len(all_vars)/3))

    proj_set = {}
    for _ in range(num_proj):
        proj_set[random.choice(all_vars)] = 1
    for i in range(num_no_touch):
        proj_set[i+1] = 1
    proj = list(proj_set)

    with open(cnf_path, "a") as f:
        f.write("c p show ")
        for var in proj:
            f.write(f"{var} ")
        f.write("0\n")
    return proj

def get_type(proj, weighted):
    cnf_type = "0"
    if proj and not weighted:
        cnf_type = "1"
    if not proj and weighted:
        cnf_type = "2"
    if proj and weighted:
        cnf_type = "3"
    return cnf_type

def gen_fuzz_call_biere(fuzzer, out_path, proj, weighted):
    seed = random.randint(0, 1000*1000*1000)
    cnf_type = get_type(proj, weighted)
    call = f"{fuzzer} {seed} {cnf_type} > {out_path}"
    return call


def gen_fuzz_call_brummayer(fuzzer, out_path, proj, weighted):
    seed = random.randint(0, 1000*1000*1000)
    cnf_type = get_type(proj, weighted)
    call = f"{fuzzer} -s {seed} -T {cnf_type} > {out_path}"
    return call


def unique_file(prefix, suffix=".cnf", max_num_files=10000):
    counter = 1
    while True:
        path = "out/" + prefix + '_' + str(counter) + suffix
        try:
            fd = os.open(
                path, os.O_CREAT | os.O_EXCL, stat.S_IREAD | stat.S_IWRITE)
            os.fdopen(fd).close()
            return str(path)
        except OSError:
            pass

        counter += 1
        if counter > max_num_files:
            print(f"Cannot create unique_file, last try was: {path}")
            sys.exit(-1)


# All meaningful options.
# * allindep changes the meaning of the CNF
#   and therefore the count! It cannot be used while fuzzing.
def gen_ganak_extra(epsilon, delta, mode):
    """Generate random ganak options targeting broad code coverage.

    Small values for cache/RDB/vivif thresholds are intentional:
    they trigger cleanup and maintenance code paths rarely hit on
    the tiny fuzz instances we generate.
    """
    choice_opts = [
        # Core accuracy params
        ("epsilon",              [str(epsilon)]),
        ("delta",                [str(delta)]),
        # Cache — tiny maxcache forces frequent cache eviction
        ("maxcache",             ["1", "5", "100"]),
        ("cache",                ["0", "1"]),
        ("cachetime",            ["0", "1", "2", "3"]),
        ("lru",                  ["0", "1"]),
        # Clause DB reduction — small targets trigger cleanup frequently
        ("rdbclstarget",         ["50", "500", "10000"]),
        ("rdbeveryn",            ["100", "1000", "10000"]),
        ("consolidateeveryn",    ["100", "1000", "30000"]),
        ("lbd",                  ["1", "2", "3"]),
        # Arjun simplification
        ("arjuncmsmult",         ["0.0001", "1"]),
        ("arjunoraclemult",      ["0", "0.0001", "1"]),
        ("arjunsamplcutoff",     ["2", "10", "100000"]),
        ("arjunweakenlim",       ["10", "8000", "100000"]),
        ("arjuniter1",           ["0", "1", "2"]),
        ("arjuniter2",           ["0", "1", "2"]),
        ("arjunbackwmaxc",       ["100", "20000"]),
        ("arjunextendmaxconfl",  ["100", "1000"]),
        ("puurabackbonemaxconfl", ["0", "10", "1000", "10000", "-1"]),
        # Tree decomposition — small tditers/tdsteps hits timeout paths
        ("td",                   ["0", "0", "1"]),
        ("tdlooktwcut",          ["2", "5", "26"]),
        ("tditers",              [str(random.randint(0, 30))]),
        ("tdsteps",              [str(random.randint(0, 1000))]),
        ("tdlimit",              ["100", "10000", "100000"]),
        ("tdmaxw",               ["20", "40", "60"]),
        ("tdminw",               ["3", "7"]),
        # Vivification — small vivifevery triggers vivif on tiny instances
        ("vivifevery",           ["10", "100", "10000000"]),
        ("vivifoutern",          ["1", "3"]),
        # SBVA
        ("sbvasteps",            ["0", "1", "100"]),
        # Decision / polarity heuristics
        ("polar",                ["0", "1", "2", "3"]),
        ("decide",               ["0", "1"]),
        ("vsadsadjust",          ["64", "256", "1024"]),
        # Precision
        ("mpfrprec",             ["64", "256"]),
        ("restart",              ["0", "1"]),
        ("rstfirst",             ["3", "10", "100", "10000"]),
        ("rsttype",              ["0", "4", "8"]),
        ("maxrst",               ["-1", "2", "5"]),
        ("maxcubesperrst",       ["2", "6"]),
        ("cuberesolve",          ["0", "1"]),
        ("cubeflp",              ["0", "1"]),
        ("smallcubedisable",     ["0", "1"]),
        ("extendcubes",          ["0", "1"]),
        ("tdwrstdecay",          ["1.0", "0.9", "0.5"]),
        # ("wlcanon",              ["0", "1", "4", "10", "20", "10000000"]),
        # # Kitten
        # ("kittengateticks", ["0", "1", "10000"]),
        # ("kittengatelimit", ["0", "1", "20000"]),
    ]

    if options.threads is not None:
        choice_opts.extend([
            ("bitsjobs",             ["1", "3", "5"]),
            ("threads",              [str(options.threads)]),
        ])

    # Binary (0/1) options
    binary_opts = [
        # Arjun
        "arjunoraclefindbins", "arjunprobe", "arjungates",
        "arjunextend", "arjunoraclegetlearnt", "arjunextendccnr",
        "sbvabreak",
        # Preprocessing
        "prebackbone", "resolvsub", "extraoracle",
        # Puura
        "puura", "puurabackbone", "puuraautarky",
        # TD
        "tdlook", "tdoptindep", "tduseadj", "tdcontract",
        # SAT solver internals
        "satrst", "satpolarcache", "satvsids",
        # Miscellaneous
        "initact", "rdbkeepused", "updatelbdcutoff",
        "stripoptindep", "rstreadjust",
        "vivif", "bumpreason", "prob",
    ]

    # weighted mode needs the sat solver
    if mode in [0]:
        binary_opts.append("satsolver")

    # only for exact counting modes
    if mode in [0, 1, 2, 3, 4, 5]:
        binary_opts.append("rstcheckcnt")

    parts = ["--mode", str(mode)]
    for flag, choices in choice_opts:
        parts.extend(["--" + flag, random.choice(choices)])
    for flag in binary_opts:
        parts.extend(["--" + flag, random.choice(["0", "1"])])

    if options.buddy and mode == 0:
        parts.extend(["--buddy", random.choice(["0", "0", "1"]),
                      "--buddymaxcls", random.choice(["3", "6", "10"])])
        if random.choice([False, False, False, True]):
            parts.extend(["--appmct", random.choice(["0.3", "0.1"])])

    if mode == 9 and random.randint(0, 2) == 0:
        parts.extend(["--mpqicrosscount", str(random.randint(0, 50)),
                      "--mpqiinitbytes",  str(random.randint(10, 200))])

    return " ".join(parts) + " "


def gen_arjun_extra(weighted, cpx):
    """Generate random arjun options for the standalone preproc binary.

    --allindep is excluded: it changes the meaning of the CNF and so the
    count. --renumber is excluded: 0 is a hard error with "c p no-touch".
    """
    choice_opts = [
        # Independent-set minimization
        ("maxc",            ["100", "20000"]),
        ("simp",            ["0", "1", "2", "3"]),
        ("nogatebelow",     ["0.0", "0.01", "0.5"]),
        # Puura
        ("iter1",           ["0", "1", "2"]),
        ("iter2",           ["0", "1", "2"]),
        ("iter1grow",       ["0", "4", "16"]),
        ("iter2grow",       ["0", "4", "16"]),
        ("bveresolvmaxsz",  ["-1", "4", "20"]),
        ("weakenlim",       ["10", "8000", "100000"]),
        ("puurastrategy",   ["0", "1", "2", "3", "4", "5", "6", "7"]),
        ("oraclemult",      ["0", "0.0001", "1"]),
        ("findbins",        ["0", "1", "2"]),
        ("cmsmult",         ["-1", "0.0001", "1"]),
        # SBVA
        ("sbva",            ["0", "1", "100"]),
        ("sbvaclcut",       ["2", "4", "20"]),
        ("sbvalitcut",      ["2", "5", "20"]),
        ("sbvamaxnewvars",  ["0", "5", "100"]),
    ]

    binary_opts = [
        "backward", "extend", "autarky", "prebackbone",
        "bve", "bvepresimp", "probe", "intree", "distill", "gaussj",
        "gates", "orgate", "irreggate", "itegate", "xorgate",
        "oraclesparsify", "oraclevivif", "oraclevivifgetl", "oracleextra",
        "sbvabreak", "red",
    ]

    parts = ["--verb", "0"]
    if cpx:
        parts.extend(["--mode", "2"])
    else:
        parts.extend(["--mode", "1" if weighted else "0"])

    for flag, choices in choice_opts:
        parts.extend(["--" + flag, random.choice(choices)])
    for flag in binary_opts:
        parts.extend(["--" + flag, random.choice(["0", "1"])])
    return " ".join(parts)


def make_ganak_solver(base, epsilon, delta, mode):
    extra = gen_ganak_extra(epsilon, delta, mode)
    exact = "--appmct" not in extra
    return Solver(base + extra, exact)


def gen_approxmc_extra(epsilon, delta):
    return f" --epsilon {epsilon} --delta {delta} --arjun {random.choice(['0', '1'])} "


def parse_frac(s):
    """"a", "a/b" -> float"""
    num, _, den = s.partition("/")
    if den: return float(num)/float(den)
    return float(num)


# "a/b + f/gi", spaces and denominators both optional
cpx_frac_re = re.compile(r"^([+-]?[\d.]+(?:/[\d.]+)?)([+-])([+-]?[\d.]+(?:/[\d.]+)?)i$")


def parse_frac_complex(s):
    """"a/b + f/gi" -> complex, or None if it doesn't parse"""
    match = cpx_frac_re.match("".join(s.split()))
    if match is None: return None
    imag = parse_frac(match.group(3))
    if match.group(2) == "-": imag = -imag
    return complex(parse_frac(match.group(1)), imag)


def short_exe(exe):
    """long command line -> "ganak mode=2", "arjun", "no-preproc" """
    if exe is None: return "no-preproc"
    name = os.path.basename(exe.split()[0])
    mode = re.search(r"--?mode[= ](\d+)", exe)
    return f"{name} mode={mode.group(1)}" if mode else name


def solver_desc(solver):
    desc = short_exe(solver.exe) + ("" if solver.exact else " (approx)")
    if solver.cwd is not None: desc += f" in {solver.cwd}"
    return desc


def run_desc(solver, preproc):
    approx = "" if solver.exact else " (approx)"
    return f"{short_exe(solver.exe)}{approx} + {short_exe(preproc.exe)}"


def report_mismatch(got, ref, cnf_path, name_w, kind=""):
    print(f"{RED}ERROR: {kind}counts disagree for {cnf_path}:{NC}")
    print(f"    {run_desc(got.solver, got.preproc):<{name_w}}  count = {CYAN}{got.count}{NC}")
    print(f"    {run_desc(ref.solver, ref.preproc):<{name_w}}  count = "
          f"{CYAN}{ref.count}{NC}   (used as reference)")
    sys.exit(-1)


def run_one_counter(solver, cnf_path, cpx, seed=42):
    curr_time = time.time()
    toexec = solver.exe.split()
    toexec.append(os.getcwd() + "/" + cnf_path)
    if not solver.exact:
        cnf_arg = toexec.pop()
        toexec.extend(["-s", str(seed), cnf_arg])

    if "ganak" in solver.exe and random.randint(1,100) == 30:
        toexec = "valgrind --leak-check=full --track-origins=yes".split() + toexec
    out, returncode = run(toexec, solver.cwd)
    diff_time = time.time() - curr_time
    if diff_time > options.maxtime - maxtimediff:
        print(f"{YELLOW}--> Too much time to solve with {solver_desc(solver)}, aborted!{NC}")
        return True, None
    if returncode != 0 and not out.startswith("TIMEOUT"):
        print(f"Solver crashed with exit code {returncode} (signal {-returncode})")
        return False, None

    count = None
    unsat_found = False
    for line in out.split("\n"):
        line = line.strip()
        if options.verbose:
            print(line)
        if "s UNSATIS" in line:
            unsat_found = True
        if "Assertion " in line and "failed" in line:
            return False, None
        # if "sat call" in line:
        #     print(line)
        if "ERROR Memory out!" in line:
            return True, None
        if "blocks are definitely lost" in line:
            print(f"ERROR: Memory leak in solver {solver.exe}, output was: ")
            for out_line in out.split("\n"):
                print(out_line.strip())
            return False, None
        if "ERROR" in line and "ERROR SUMMARY" not in line:
            print(f"{RED}ERROR in output: {NC}", line)
            for out_line in out.split("\n"):
                print(out_line.strip())
            return False, None
        if len(line) < 4:
            continue
        if "c s exact arb cpx" in line:
            # c s exact arb cpx 1.2650e+02 + -6.3250e+01i
            real = float(line.split()[5].strip())
            imag = float(line.split()[7].strip()[:-1])
            count = complex(real, imag)
            continue
        if line[0] == 'c' and line[:3] != "c s":
            continue
        if line[:4] == "s mc" or line[:13] == "c s exact arb" or line[:5] == "s pmc" or "s approx arb int" in line or "c s exact" in line:
            if count is not None:
                print("ERROR: Two 's mc' lines in output!!")
                # TODO: print command that got executed
                sys.exit(-1)
            if cpx:
                if unsat_found:
                    count = complex(0, 0)
                else:
                    # c s exact double prec-sci 0+0i
                    if "float" in line or "double" in line:
                        real = float(line.split()[5].strip())
                        imag = float(line.split()[7].strip()[:-1])
                        count = complex(real, imag)
                    elif "frac" in line:
                        # c s exact arb frac 3/2 + -1i
                        count = parse_frac_complex(line.split("frac", 1)[1])
                        if count is None:
                            print(f"{RED}ERROR, couldn't parse cpx frac line: {NC}", line)
                            sys.exit(-1)
                    else:
                        print(f"{RED}ERROR, couldn't parse cpx line: {NC}", line)
                        sys.exit(-1)
            elif line[:4] == "s mc" or line[:5] == "s pmc":
                count = int(line.split()[2])
            elif "c s exact arb int" in line:
                count = int(line.split()[5])
            elif "c s exact arb float " in line:
                count = float(line.split()[5])
            elif "c s exact quadruple float interval [" in line:
                # using middle of interval
                parts = line.split()
                count = (float(parts[7]) + float(parts[8])) / 2.0
            elif "c s exact octuple float" in line or \
                    "c s exact quadruple float" in line or \
                    "c s exact double float" in line:
                count = float(line.split()[5])
            elif "c s exact arb frac" in line:
                parts = line.split()
                if parts[5] == "[":
                    # mpqi rolled over to interval: [ left right ]
                    count = (parse_frac(parts[6]) + parse_frac(parts[7])) / 2.0
                else:
                    count = parse_frac(parts[5])
            elif "s exact double prec-sci" in line:
                count = float(line.split()[5])
            elif "c s approx arb int" in line:
                count = int(line.split()[5])
            else:
                print(f"{RED}ERROR, couldn't parse line: {NC}", line)
                sys.exit(-1)
    if unsat_found:
        return True, 0

    if count is None:
        print("ERROR, could not find 's mc', 'c s exact arb int', or 'c s exact arb frac' or 'c s approx arb int' in output")
        for out_line in out.split("\n"):
            print(out_line.strip())
        if ("ganak" in solver.exe or "approx" in solver.exe):
            return False, None
        else :
            print("Not erroring out, it's not our solver")
            return True, None

    return True, count

def check_header(cnf_path):
    with open(cnf_path, "r") as f:
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
            for lit in line.split():
                var = abs(int(lit))
                if var > max_vars:
                    max_vars = var

        if num_cls != header_cls:
            print(f"cls in CNF: {num_cls} but header said: {header_cls}")
            return False

        if max_vars > header_vars:
            print(f"max vars was: {max_vars} but header said: {header_vars}")
            return False
    return True

# Arjun must keep the no-touch vars as vars 1..k, in the sampling set
def check_no_touch_preserved(simp_path, num_no_touch):
    if num_no_touch == 0:
        return True
    nvars = get_nvars(simp_path)
    no_touch = None
    show_vars = None
    with open(simp_path, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("c p no-touch"):
                no_touch = [int(x) for x in line.split()[3:-1]]
            if line.startswith("c p show"):
                show_vars = set(int(x) for x in line.split()[3:-1])
    if show_vars is None:
        # no "c p show" means every var is in the sampling set
        show_vars = set(range(1, nvars+1))

    want_no_touch = list(range(1, num_no_touch+1))
    if no_touch != want_no_touch:
        print(f"ERROR: no-touch header in {simp_path} is {no_touch} but should be {want_no_touch}")
        return False
    if nvars < num_no_touch:
        print(f"ERROR: {simp_path} has only {nvars} vars, but {num_no_touch} are no-touch")
        return False
    missing = [v for v in want_no_touch if v not in show_vars]
    if missing:
        print(f"ERROR: no-touch vars {missing} of {simp_path} are not in 'c p show'")
        return False
    return True


def perc_diff(got, want):
    diff = abs(got.real-want.real) + abs(got.imag-want.imag)
    magnitude = abs(want.real) + abs(want.imag)
    if (got != want and magnitude == 0):
        return 100.0
    return diff/magnitude


def abs_diff(got, want):
    return abs(got.real-want.real) + abs(got.imag-want.imag)


def run_one_preproc(preproc, in_path, out_path, num_no_touch):
    curr_time = time.time()
    toexec = preproc.exe.split()
    toexec.append(os.getcwd() + "/" + in_path)
    toexec.append(os.getcwd() + "/" + out_path)

    if options.verbose:
        print(f"{MAGENTA}--> Executing preproc: {NC}{' '.join(toexec)} in dir {preproc.cwd}")
    else:
        print(f"{MAGENTA}--> Executing preproc:{NC} {short_exe(preproc.exe)} {in_path} -> {out_path}")
    # print("Executing preproc ", preproc)
    out, returncode = run(toexec, preproc.cwd)
    diff_time = time.time() - curr_time
    if diff_time > options.maxtime - maxtimediff:
        print(f"{YELLOW}--> Too much time to preproc with {short_exe(preproc.exe)}, aborted!{NC}")
        return False
    if out.startswith("TIMEOUT"):
        print(f"{YELLOW}--> Preproc {short_exe(preproc.exe)} timed out, skipping{NC}")
        return False
    if returncode != 0:
        print(f"ERROR: preproc {short_exe(preproc.exe)} crashed with exit code {returncode}, output was:")
        print(out)
        sys.exit(-1)
    assert check_header(out_path)
    if not check_no_touch_preserved(out_path, num_no_touch):
        sys.exit(-1)
    return True

def cleanup(cnf_path, simplified):
    os.unlink(cnf_path)
    for _, simp_path in simplified:
        os.unlink(simp_path)


def exit_if_single_seed():
    if options.rnd_seed is not None:
        print(f"{YELLOW}Exiting as we only wanted to run one test due to --seed{NC}")
        sys.exit(0)


if __name__ == "__main__":
    if os.path.isfile("out"):
        print("ERROR: file 'out' exists, but we need a directory named 'out'")
        sys.exit(-1)
    os.makedirs("out", exist_ok=True)
    os.makedirs("tmpdir", exist_ok=True)

    # parse options
    parser = set_up_parser()
    (options, args) = parser.parse_args()

    if options.rnd_seed is None:
        rnd_seed = int.from_bytes(os.urandom(8))
        print("Using seed:", rnd_seed)
    else:
        rnd_seed = options.rnd_seed
    random.seed(rnd_seed)

    for i in range(options.only):
        if options.rnd_seed is None:
            seed = int.from_bytes(os.urandom(8))
            random.seed(seed)
        else:
            seed = options.rnd_seed
        proj :bool = random.choice([True, False])
        if (options.projected):
            proj = True
        if (options.unprojected):
            proj = False

        weighted :bool = random.choice([True, False])
        if options.weighted:
            weighted = True
        if options.unweighted:
            weighted = False

        cpx :bool = random.choice([True, False, False])
        cnf_path = unique_file("fuzzTest")
        print(f"{GREEN}=== Seed: {seed}  projected: {proj}  weighted: {weighted}  cpx: {cpx}  file: {cnf_path}{NC}")

        # NOTE Baysian network: http://reasoning.cs.ucla.edu/ace/
        # Generate random PB formulas, translate with Stephan Gocht's translator to CNF, and count with CPLEX.
        # Majority vote + if count is small, we can count 1-by-1.
        # Mate TODO: add other binaries from competition, add CNF checker
        # Mate TODO: get https://github.com/vroland/sharptrace working together with https://github.com/vroland/sharpSAT/tree/proof-trace
        call = random.choice([
            gen_fuzz_call_biere("./biere-fuzz", cnf_path, proj, weighted),
            gen_fuzz_call_brummayer("./cnf-fuzz-brummayer.py", cnf_path, proj, weighted)])
        # print("TODO: ./dnfstream --eager 1 a.cnf -e 0.01 --delta 0.01 out.dnf");
        # print("TODO: ./cnftranslate out.dnf out.cnf");

        print(f"{MAGENTA}--> Calling: {NC}{call}")
        status = subprocess.call(call, shell=True)
        if status != 0:
            print("Failed fuzzer file generator call: ", call)
            sys.exit(-1)
        else:
            print(f"{MAGENTA}--> Generated fuzz file{NC} {cnf_path} with call: {call}")

        num_no_touch = pick_num_no_touch(get_nvars(cnf_path))
        if options.disable_no_touch:
            num_no_touch = 0
        projected_vars = None
        if proj:
            projected_vars = add_projection(cnf_path, num_no_touch)
        add_no_touch(cnf_path, num_no_touch)
        if not cpx and weighted:
            add_weights(cnf_path, projected_vars)
        if cpx:
            add_weights_cpx(cnf_path, projected_vars)
        counts = []
        solvers = []

        delta = random.choice([0.2, 0.4, 0.6])
        epsilon = random.choice([0.8, 6.0])
        approx_extra = gen_approxmc_extra(epsilon, delta)

        # MODES
        # 0=integer counting,
        # 1=weighted counting over the rationals,
        # 2=complex rational numbers,
        # 3=multivariate polynomials over the rational field,
        # 4=parity counting,
        # 5=counting over a prime field (see --prime),
        # 6=mpfr floating point complex numbers (see --mpfrprecision),
        # 7=mpfr floating point real numbers (see --mpfrprecision),
        # 8=mpfi intervals
        ganak_base = "../ganak/build/ganak --verb 0 "
        if not weighted:
            solvers.extend([
            Solver("../approxmc/build/approxmc " + approx_extra, False),
            make_ganak_solver(ganak_base, epsilon, delta, mode=0),
            # Solver("./bins/d4-mccomp2022/bin/d4_static -m counting  --output-format competition -i"),
            # Solver("./bins/c2d-mccomp2022/c2d -in ", True),
            ])
        else:
            solvers.extend([
            make_ganak_solver(ganak_base, epsilon, delta, mode=1),
            make_ganak_solver(ganak_base, epsilon, delta, mode=7),
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
                make_ganak_solver(ganak_base, epsilon, delta, mode=2),
                make_ganak_solver(ganak_base, epsilon, delta, mode=6),
                # Solver("./gpmc -mode=1", True, "./bins/gpmc-complex/"),
                ]

        preprocs = [
            Preproc( "../arjun/build/arjun " + gen_arjun_extra(weighted, cpx), None),
            Preproc(None, None)
        ]

        simplified = []
        for preproc in preprocs:
            simp_path = unique_file("fuzzTest")
            ok = False
            if preproc.exe is None:
                shutil.copyfile(cnf_path, simp_path)
                ok = True
                if options.verbose:
                    print(f"Copied file {cnf_path} to {simp_path} for the empty preproc")
            else:
                ok = run_one_preproc(preproc, cnf_path, simp_path, num_no_touch)
                if options.verbose:
                    print(f"Generated file {simp_path} by preproc {preproc.exe} which preprocessed {cnf_path}")
            if ok:
                simplified.append((preproc, simp_path))
            else:
                os.unlink(simp_path)

        exact_count = None
        print(f"{MAGENTA}--> Solvers to run ({len(solvers)}):{NC}")
        for i, solver in enumerate(solvers, 1):
            print(f"      [{i}] {solver_desc(solver)}")
            if options.verbose: print(f"          {' '.join(solver.exe.split())}")
        print(f"{MAGENTA}--> Preprocessors ({len(simplified)}):{NC}")
        pp_w = max(len(short_exe(pp.exe)) for pp, _ in simplified)
        for preproc, simp_path in simplified:
            print(f"      {short_exe(preproc.exe):<{pp_w}} -> {simp_path}")
        if len(solvers) == 1:
            print("ERROR, it makes no sense to run a single solver, exiting")
            sys.exit(-1)

        # only GANAK and ApproxMC understand arjun's "MUST MULTIPLY BY"
        runs = [(solver, preproc, simp_path)
                for solver in solvers
                for preproc, simp_path in simplified
                if preproc.exe is None or "arjun" not in preproc.exe
                or "ganak" in solver.exe or "approx" in solver.exe]

        # pad to the widest name so the counts line up in a column
        name_w = max(len(run_desc(so, pp)) for so, pp, _ in runs)
        idx_w = len(str(len(runs)))

        for run_idx, (solver, preproc, simp_path) in enumerate(runs, 1):
            tag = f"[{run_idx:>{idx_w}}/{len(runs)}] {run_desc(solver, preproc):<{name_w}}"
            print(f"{MAGENTA}--> Counting:{NC} {tag} on {simp_path}")
            to_run = solver
            if preproc.exe is not None and "arjun" in preproc.exe:
                # arjun's output has show < optshow, which arjun's backward
                # pass (re-run inside the counter) refuses
                exe = re.sub(r"--arjun\s+\S+", "", solver.exe) + " --arjun 0 "
                to_run = solver._replace(exe=exe)
            ok, count = run_one_counter(to_run, simp_path, cpx)
            if not ok:
                print(f"{RED}ERROR running {tag}{NC}")
                sys.exit(-1)
            if count is None:
                print(f"    {YELLOW}{tag}  NO COUNT (timed out/aborted){NC}")
            else:
                print(f"    {tag}  count = {CYAN}{count}{NC}")
            if count is not None and solver.exact and preproc.exe is None:
                exact_count = Count(solver, preproc, count)
            if count is not None:
                counts.append(Count(solver, preproc, count))

        if exact_count is None:
            exit_if_single_seed()
            cleanup(cnf_path, simplified)
            continue

        # print("counts is: ", counts)
        for got, _ in zip(counts, solvers):
            if weighted:
                assert(got.solver.exact)
                is_float_mode = "--mode 7" in got.solver.exe or "--mode 8" in got.solver.exe or "--mode 9" in got.solver.exe or \
                    "--mode 7" in exact_count.solver.exe or "--mode 8" in exact_count.solver.exe or "--mode 9" in exact_count.solver.exe
                abs_diff_threshold = 1e-10 if is_float_mode else 1e-50
                if got.count != exact_count.count and perc_diff(got.count, exact_count.count) > 0.02 and abs_diff(got.count, exact_count.count) > abs_diff_threshold:
                    report_mismatch(got, exact_count, cnf_path, name_w, "weighted ")

            if not weighted:
                if got.count != exact_count.count and got.solver.exact:
                    report_mismatch(got, exact_count, cnf_path, name_w)

                if got.count != exact_count.count and not got.solver.exact:
                    max_allowed = exact_count.count * (1.0 + epsilon)
                    min_allowed = exact_count.count * (1.0 / (1.0 + epsilon))

                    oob = got.count > max_allowed or got.count < min_allowed
                    col = RED if oob else YELLOW
                    print(f"    {run_desc(got.solver, got.preproc):<{name_w}}  count = {CYAN}{got.count}{NC}"
                          f"  vs exact {exact_count.count}"
                          f"  {col}(factor {exact_count.count / float(got.count)} off){NC}")
                    print(f"    allowed with epsilon={epsilon}: [{min_allowed}, {max_allowed}] -> "
                          f"{RED + 'OUT OF RANGE' + NC if oob else 'in range'}")
                    if oob:
                        num_wrong = 0
                        num_reruns = 100
                        num_done = 0
                        num_failed = 0
                        while num_done < num_reruns and num_failed < 5:
                            ok, rerun_count = run_one_counter(got.solver, cnf_path, cpx, random.randint(0, 1000*1000*1000))
                            if rerun_count is None:
                                num_failed += 1
                                continue
                            num_done += 1
                            print(f"Rerun gives count = {rerun_count}")
                            if not ok:
                                print(f"{RED}ERROR: rerun failed?{NC}")
                                sys.exit(-1)
                            if rerun_count > max_allowed or rerun_count < min_allowed:
                                num_wrong += 1
                        if num_failed < 5:
                            perc_wrong = float(num_wrong) / float(num_reruns) * 100.0
                            print(f"Out of {num_reruns} reruns, {num_wrong} were outside the allowed range, percentage {perc_wrong}%")

                            allowed_perc_wrong = (delta) * 100.0
                            if perc_wrong > allowed_perc_wrong:
                                print(f"{RED}ERROR: Delta was exceeded. It was allowed to be only {allowed_perc_wrong} %{NC}")
                                sys.exit(-1)
                            else:
                                print(f"{GREEN}OK within delta after reruns. Delta was {allowed_perc_wrong} %{NC}")
                        else:
                            print("Too many failed reruns, not checking delta.")


            print(f"{GREEN}OK{NC}  {run_desc(got.solver, got.preproc):<{name_w}}  count = {CYAN}{got.count}{NC}"
                  f"  matches {run_desc(exact_count.solver, exact_count.preproc)}")

        print(f"{GREEN}=== Checking with file {cnf_path} finished{NC}")
        exit_if_single_seed()
        cleanup(cnf_path, simplified)




