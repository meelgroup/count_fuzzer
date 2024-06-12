# Possible bugs found for d4


## 12 June 2024

The projected weighted cnf in `fuzzTest_20.cnf` yields a model count of 160 when counted by `bins/d4-mccomp2022/bin/d4_static -m counting --output-format competition -i`, and a model count of 1 for all other tested solvers.

```
counts is:  [
    Count(
        solver=Solver(exe='bins/ganak-2024/ganak  --td 0 ', exact=True, dir=None), preproc=Preproc(exe=None, dir=None), 
        count=1.0), 
    Count(
        solver=Solver(exe='bins/ganak-2024/ganak  --satrstmult 1 --arjun 0 --td 0', exact=True, dir=None), preproc=Preproc(exe=None, dir=None), 
        count=1.0), 
    Count(
        solver=Solver(exe='bins/ganak-2024/ganak  --arjun 1 --td 0', exact=True, dir=None), preproc=Preproc(exe=None, dir=None), 
        count=1.0), 
    Count(
        solver=Solver(exe='./bins/d4-mccomp2022/bin/d4_static -m counting  --output-format competition -i', exact=True, dir=None), preproc=Preproc(exe=None, dir=None), 
        count=160.0), 
    Count(
        solver=Solver(exe='bins/ganak-2024/ganak  --arjun 1 --td 0 --precise 1', exact=True, dir=None), preproc=Preproc(exe=None, dir=None), 
        count=1.0), 
    Count(
        solver=Solver(exe='../gpmc2023/gpmc -mode=3', exact=True, dir=None), preproc=Preproc(exe=None, dir=None), 
        count=1.0)
    ]
```

Repo commit: `dd43adcfd311f0a0e0ba25aff45e82d775bc3e76`.