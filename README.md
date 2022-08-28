# Model Counter Fuzzer

Currently requires GANAK, SharpSAT, and ApproxMC to be built, and available from the following locations, relative to this path:

```
../ganak/build/ganak
../sharpSAT/build/sharpSAT
../approxmc/build/approxmc
```

However, you can give them as options to the fuzzer.

Before you run, you must build:
```
cmake .
make
```

Then you can run:

```
./fuzz.py
```

# TODOs

Some ideas:
* Projected model counting is not done at all
* We should have our own fuzz generator. Currently only cnf-fuzz-biere is hooked up
* Maybe our fuzz generator should generate instances that have a known number of solutions? Or we should use the proof system that was published at SAT 2022, and verify the proof of a counter, and use that as a baseline?
* ApproxMC is not set to be used -- since it's probabilistic, this is a bit tricky.
* Arjun should be checked, too, as a preprocessor. So run it before e.g. sharpSAT and GANAK to see if the count changes.
* We should use valgrind: we should run executables under `valgrind` once in a while, to see if they leak memory, or do oother incorrect things. We could also use address sanitizer from clang, actually, would be faster and more thorough (e.g. overflow/underflow checks).

Notes:
* SharpSAT is broken, we need to fix the latest issue -- see `bugs_found/` subdirectory. Otherwise, we'll keep bumping into the same issue instead of finding new ones
