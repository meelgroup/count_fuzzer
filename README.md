# `#fuzz`: a fuzzer for Model Counters

- [`#fuzz`: a fuzzer for Model Counters](#fuzz-a-fuzzer-for-model-counters)
  - [Build instructions](#build-instructions)
  - [Preparing the run](#preparing-the-run)
    - [Instance generators](#instance-generators)
    - [Model counters](#model-counters)
    - [Verifier](#verifier)
  - [Running `#fuzz`](#running-fuzz)
  - [About](#about)
    - [Found any bugs?](#found-any-bugs)
    - [Current limitations](#current-limitations)
    - [TODOs \& Contributing](#todos--contributing)
    - [Authors and maintainers](#authors-and-maintainers)
    - [License information](#license-information)
    - [Citing](#citing)


`#fuzz` is a fuzzer for propositional model counters. It has support for verifying the model counts of unweighted, unprojected model counters ('`mc`'). Additionally, it can be used to fuzz weighted model counters ('`wmc`'), and has some rudimentary support for projected (weighted) model counters ('`pmc`' and '`pwmc`'). For now, the focus is on exact counters, but it can to some extent be used to fuzz approximate counters (although we haven't tested that).


## Build instructions

Build the desired instance generator(s):
```bash
$ cd generators
$ g++ cnf-fuzz-biere.c -o biere-fuzz
```

If your use of `conda` is within the updated [terms of service](https://legal.anaconda.com/policies/en/), install [miniconda 3](https://docs.anaconda.com/miniconda/) and create a `conda` environment:
```bash
$ conda env create -f env/sharp_fuzz.yml
$ conda activate sharp_fuzz
```
Otherwise, install the packages listed in `env/sharp_fuzz.yml` using `pip`.

## Preparing the run

### Instance generators

Create a configuration file to communicate to the instance generation script (`src/generate_instances.py`) which instance generators to use.

Make sure that, if your favourite generator takes a random seed as input, that you add `{seed}` to the configuration. Similarly, make sure that you use `{outfile}` to the configuration as a placeholder for the path where you want to write the generated `dimacs` instance to. If `{outfile}` is omitted, the fuzzer will simply add the path to the outfile as the last argument.

If you want to use the (currently limited) support that `#fuzz` offers for turning `mc` problems into `wmc`, `pmc` or `pmc` problems, it's best to let the generator scripts generate `mc` problems.

Also: each run of the fuzzer only processes one type of model counting, so it's best to have generators that generate only one particular type of model counting instance in the same run.

Note that some instance generators take an integer as input to specify the type of instance to generate (as demonstrated above), according to the following key:
```
0: mc
1: wmc
2: pmc
3: pwmc
```

This is an example generator config file for generating `mc` instances:
```bash
$ cat generator_config_mc.json
{
   "biere-mc": {
      "path":"/path/to/sharp_fuzz/generators/biere-fuzz",
      "config":"{seed} 0 > {out_file}"
   },
   "brummayer-mc": {
      "path":"/path/to/sharp_fuzz/generators/cnf-fuzz-brummayer.py",
      "config":"-I 21 -s {seed} -T 0 > {out_file}"
   }
}
```
And this is one for generating `pwmc` instances:
```bash
$ cat generator_config_pwmc.json
{
   "biere-pwmc": {
      "path":"/path/to/sharp_fuzz/generators/biere-fuzz",
      "config":"{seed} 3 > {out_file}"
   },
   "brummayer-pwmc": {
      "path":"/path/to/sharp_fuzz/generators/cnf-fuzz-brummayer.py",
      "config":"-I 21 -s {seed} -T 3 > {out_file}"
   }
}
```

### Model counters

Similarly, create configuration files to communicate the counters that you want to evaluate, again sticking with one type of counter per file. 

For example:

```bash
$ cat counter_config_mc.json
{
   "my-mc-counter-cnfg1": {
      "path":"/path/to/my/counter.py",
      "config":"--thisarg=1 --thatarg=2",
      "exact":"True"
   },
   "my-mc-counter-cnfg2": {
      "path":"/path/to/my/counter.py",
      "config":"--thisarg=2 --thatarg=4",
      "exact":"True"
   },
   "my-other-mc-counter": {
      "path":"/path/to/my/other_counter",
      "config":"",
      "exact":"True"
   }
}
```

If you want to communicate the allowed time and memory per run to a counter (and your counter has functionality for dealing with that info), add the `{STAREXEC_WALLCLOCK_LIMIT}` and `{STAREXEC_MAX_MEM}` placeholders to your configuration.

The `src/run_fuzzer.py` script takes a timeout time (in seconds) as an optional argument (`-t {TIMEOUT}`) and a maximum allowed amount of memory (`-m {MEMOUT}`, in MB). The script will assign the values given by these arguments to `STAREXEC_WALLCLOCK_LIMIT` and `STAREXEC_MAX_MEM`. Hence, if you call the script with arguments `-t 10 -m 3200`, the `STAREXEC_WALLCLOCK_LIMIT` environment variable will get value `10 s`, and the `STAREXEC_MAX_MEM` environment variable will get value `3200 MB`. If you want to communicate these values as command line arguments to your counter, you can specify them with `{STAREXEC_WALLCLOCK_LIMIT}` and `{STAREXEC_MAX_MEM}` in the command line. For example:
```bash
$ cat counter_config_limits.json
{
   "yet-another-counter": {
      "path":"/path/to/my/other_counter",
      "config":"--timeout {STAREXEC_WALLCLOCK_LIMIT} --memout {STAREXEC_MAX_MEM}",
      "exact":"True"
   }
}
```
Note that it is possible to evaluate just a single counter at a time. This can be useful if your aim is to try to trigger crashes. If you also want to evaluate the correctness of the returned count, make sure that you set up a verifier.

### Verifier

Currently, the most reliable way of verifying model counts for this fuzzer is to use []`cpog`](https://github.com/rebryant/cpog).

To set this up, first download and install/compile [cpog](https://github.com/rebryant/cpog) and all its dependencies. Make sure to run `make linstall` in the process.

Then, create the following symbolic links:
```bash
cd /path/to/count_fuzzer/verifiers
ln -s /path/to/d4/d4
ln -s /path/to/cpog/VerifiedChecker/build/bin/checker cpog_checker
ln -s /path/to/cpog/src/cpog-gen
```

In the future, we would like to make different scripts available, so you can use your favourite certified model counting tool. Feel free to send us a pull request.


## Running `#fuzz`

`#fuzz` is set up in such a way that you have to first generate the problem instances, and optionally also formally verify their model counts, and run the fuzzer afterwards on the generated instances.

If everything is set up correctly, you can run `#fuzz` as follows:
```bash
$ python src/generate_instances.py --generators /path/to/generator_config.json
$ python src/run_fuzzer.py --counters /path/to/counter_config.json
```
or 
```bash
$ python src/generate_instances.py --generators /path/to/generator_config.json --verifier /path/to/verifier/script
$ python src/run_fuzzer.py --counters /path/to/counter_config.json --verified_counts /path/to/verified_counts.csv
```

## About

### Found any bugs?
If you have used this tool to find any bugs, please let [us](#authors-and-maintainers) know? Thanks!

### Current limitations

- no support for verifying counts in the `wmc`, `pmc` or `pwmc` settings (only for `mc`).

### TODOs & Contributing

A non-exhaustive list of thing we want to add:
- [ ] More instance generators
- [ ] Verification support for `wmc`, `pmc` and `pwmc`
- [ ] Features that will help fuzz approximate model counters

### Authors and maintainers
`#fuzz` was developed and is currently being maintained by:
- [Anna L.D. Latour](https://latower.github.io): [@latower](https://github.com/latower)
- [Mate Soos](https://www.msoos.org/): [@msoos](https://github.com/msoos)

### License information


### Citing
