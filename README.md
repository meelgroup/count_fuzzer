# The tale of the count_fuzzer
count_fuzzer is an alternate, somewhat different and in many ways less capable
version of [SharpVelvet](https://github.com/meelgroup/SharpVelvet), originally
written for fuzzing [Ganak](https://github.com/meelgroup/ganak/) and
[ApproxMC](https://github.com/meelgroup/approxmc/) model counters by Anna Latour.
We are incredibly grateful for her help.

This messy version of SharpVelvet is used by the team working on ApproxMC and
Ganak, so it gets to have a lot of mess and bad features. It's a bit of an odd
child. If you are looking for a full-featured fuzzer that is NOT messy and NOT
tuned for specific counters, check out
[SharpVelvet](https://github.com/meelgroup/SharpVelvet)! This is a VERY crude
fork

## Build&Use instructions

Build the desired instance generator(s):
```bash
$ cd generators
$ g++ cnf-fuzz-biere.c -o biere-fuzz
```

Now run one of:
```bash
./fuzz.py --unweighted     # only unweighted
./fuzz.py --weighted       # only weighted
./fuzz.py --nomessyweight  # weights are NOT fully given and can contain
                           # negative values
./fuzz.py --zerocomps      # weights are MESSY and often add up to 0
./fuzz.py --proj           # projected only
./fuzz.py --unproj         # unprojected only
./fuzz.py --cpx            # complex only
./fuzz.py --exact          # only exact counting (no approximate)
./fuzz.py --noimag         # set imaginary part to 0
./fuzz.py --only N         # only run N tests
./fuzz.py --tout T         # max time to run (default: 4 seconds)
./fuzz.py --threads K      # fuzz ONLY with --threads K given to ganak
./fuzz.py                  # non-stop run, EVERYTHING: cpx, proj, unproj,
                           # weighted, unweighted, etc.
```

## Minimization tools

When the fuzzer finds a crash or incorrect count, you can use these tools to
minimize the test case:

### minim_all.py (Recommended)
Automated minimization pipeline that runs all minimizers in sequence. This is
the easiest way to minimize a test case - it automatically detects the failure
type (crash or timeout), backs up the original file, and runs the appropriate
minimizers in optimal order:

1. Minimizes command-line options (for crashes)
2. Minimizes weight lines (if present)
3. Minimizes CNF clauses
4. Verifies each step preserves the failure

```bash
./minim_all.py "../ganak/build/ganak --mode 1 --polar 1 file.cnf"
```

This will produce a fully minimized test case with all three minimization
techniques applied and verified. The original CNF file is backed up
automatically.

### minim_cnf.py
Minimizes CNF files by removing clauses using delta debugging while preserving
a crash. Useful for creating minimal reproducible test cases from large
fuzzer-generated files.

```bash
./minim_cnf.py "../ganak/build/ganak --mode 1 --polar 1 file.cnf"
```

This will create `file_min_clauses.cnf` with the minimal set of clauses that
still causes the crash.

### minim_weights.py
Minimizes weight lines in CNF files while preserving a crash. Removes
`c p weight` lines one by one to find the minimal set of weights needed to
reproduce the issue.

```bash
./minim_weights.py "../ganak/build/ganak --mode 1 --polar 1 file.cnf"
```

This will create `file_min_weights.cnf` with the minimal set of weight lines.

### minim_opts_crash.py
Minimizes command-line options for a crashing command. Removes options one by
one to find the minimal set of flags that still cause the crash.

```bash
./minim_opts_crash.py "../ganak/build/ganak --mode 1 --polar 1 --cache 0 --lru 1 file.cnf"
```

### minim_opts_count.py
Minimizes command-line options for a counting issue. Removes options that
don't affect the count (within 0.1% tolerance) to find the minimal command
that reproduces the issue.

```bash
./minim_opts_count.py "../ganak/build/ganak --mode 1 --polar 1 --cache 0 --lru 1 file.cnf"
```

### Model counters
ONLY Ganak and ApproxMC are supported, and NO other support is planned to be added.
You MUST use [SharpVelvet](https://github.com/meelgroup/SharpVelvet) for that.

### Authors and maintainers
`#fuzz` was developed and is currently being maintained by:
- [Anna L.D. Latour](https://latower.github.io): [@latower](https://github.com/latower)
- [Mate Soos](https://www.msoos.org/): [@msoos](https://github.com/msoos)

