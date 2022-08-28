# Model Counter Fuzzer

Currently requires GANAK, SharpSAT, and ApproxMC to be built, and available from the following locations, relative to this path:

```
../ganak/build/ganak
../sharpSAT/build/sharpSAT
../approxmc/build/approxmc
```

However, you can give them as options to the fuzzer.

To run:
```
cmake .
make
./fuzz.py
```

