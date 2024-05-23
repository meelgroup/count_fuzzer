# Model Counter Fuzzer

Currently requires Ganak and ApproxMC to be built, and available from the following locations, relative to this path:

```
../ganak/build/ganak
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
* We should have our own fuzz generator. Currently only cnf-fuzz-biere is hooked up
* Maybe our fuzz generator should generate instances that have a known number of solutions? Or we should use the proof system that was published at SAT 2022, and verify the proof of a counter, and use that as a baseline?
