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
./fuzz.py --unweighted # only unweighted
./fuzz.py --weighted # only weighted
./fuzz.py --nomessyweight # weights without negative values
./fuzz.py --proj # projected only
./fuzz.py --unproj # unprojected only
./fuzz.py --cpx # complex only
./fuzz.py --only N # only run N tests
./fuzz.py # non-stop run, EVERYTHING: cpx, proj, unproj, weighted, unweighted, etc.
```

### Model counters
ONLY Ganak and ApproxMC are supported, and NO other support is planned to be added.
You MUST use [SharpVelvet](https://github.com/meelgroup/SharpVelvet) for that.

### Authors and maintainers
`#fuzz` was developed and is currently being maintained by:
- [Anna L.D. Latour](https://latower.github.io): [@latower](https://github.com/latower)
- [Mate Soos](https://www.msoos.org/): [@msoos](https://github.com/msoos)

