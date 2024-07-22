# Model Counter Fuzzer

## Prerequisites:

- [miniconda 3](https://docs.anaconda.com/miniconda/)
- cmake

## Build instructions (internal, temporary)

Before you run, you must build:
```bash
cmake .
make
```

**TODO: revise `CMakeFiles.txt` and other instructions. Seems overkill now.**

And create the right `conda` environment:
```bash
conda env create -f env/sharp_fuzz.yml
conda activate sharp_fuzz
```

<!-- And compile our modified version of Armin Biere's instance generator:
```bash
user@machine /path/to/count_fuzz$ g++ cnf-fuzz-biere.c -o biere-fuzz
``` -->

Then, create configuration files to communicate to the fuzzer which counters to evaluate and which instance generators to use. For example:
```bash
cat counter_config.json
{
   "my-counter-cnfg1": {
      "path":"/path/to/my/counter.py",
      "config":"--thisarg=1 --thatarg=2",
      "exact":"True"
   },
   "my-counter-cnfg2": {
      "path":"/path/to/my/counter.py",
      "config":"--thisarg=2 --thatarg=4",
      "exact":"True"
   },
   "my-other-counter": {
      "path":"/path/to/my/other_counter",
      "config":"",
      "exact":"True"
   }
}
```
and
```bash
cat generator_config.json
{
   "biere": {
      "path":"/path/to/count_fuzzer/biere-fuzz",
      "config":"{seed} {type_num} > {out_file}"
   },
   "brummayer": {
      "path":"/path/to/count_fuzzer/cnf-fuzz-brummayer.py",
      "config":"-I 21 -s {seed} -T {type_num} > {out_file}"
   }
}
```

Note: the allowed time and memory per run of a counter can be set with the environment variables `STAREXEC_WALLCLOCK_LIMIT` and `STAREXEC_MAX_MEM`. The `run_fuzzer.py` script takes a timeout time (in seconds) as an optional argument (`-t {TIMEOUT}`) and a maximum allowed amount of memory (`-m {MAX_MEM}`, in MB). The script will assign the values given by these arguments to `STAREXEC_WALLCLOCK_LIMIT` and `STAREXEC_MAX_MEM`. Hence, if you call the script with arguments `-t 10 -m 3200`, the `STAREXEC_WALLCLOCK_LIMIT` environment variable will get value `10 s`, and the `STAREXEC_MAX_MEM` environment variable will get value `3200 MB`. If you want to communicate these values as command line arguments to your counter, you can specify them with `{STAREXEC_WALLCLOCK_LIMIT}` and `{STAREXEC_MAX_MEM}` in the command line. For example:

```bash
cat counter_config.json
{
   "yet-another-counter": {
      "path":"/path/to/my/other_counter",
      "config":"--timeout {STAREXEC_WALLCLOCK_LIMIT} --memout {STAREXEC_MAX_MEM}",
      "exact":"True"
   }
}
```

Then you can run:

```bash
cd src
./run_fuzzer -c /path/to/counter_config.json -g /path/to/generator_config.json 
```




# TODOs

Some ideas:
* We should have our own fuzz generator. Currently only cnf-fuzz-biere and brummayer are hooked up
* We should add functionality for determining the exact count of an instance. We could use Tbuddy for that, maybe?
* Figure out license information for Biere and Brummayer and include them in the repository the right way.