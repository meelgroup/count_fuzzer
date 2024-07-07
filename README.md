# Model Counter Fuzzer

## Build instructions (internal, temporary)
Before you run, you must build:
```bash
cmake .
make
```
And create the following symbolic links:
```bash
user@machine /path/to/count_fuzz$ ln -s /path/to/mc_experiments/eval/scripts scripts
user@machine /path/to/count_fuzz$ ln -s /path/to/mc_experiments/eval/scripts/fuzzer_utils.py fuzzer_utils.py
user@machine /path/to/count_fuzz$ ln -s /path/to/mc_experiments/eval/scripts/count_replication/parse_counts_util.py parse_counts_util.py
```
And compile our modified version of Armin Biere's instance generator:
```bash
user@machine /path/to/count_fuzz$ g++ cnf-fuzz-biere.c -o biere-fuzz
```

Then, create configuration files to communicate to the fuzzer which counters to evaluate and which instance generators to use. For example:
```bash
user@machine /path/to/count_fuzz$ cat counter_config.json
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
user@machine /path/to/count_fuzz$ cat generator_config.json
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

Then you can run:

```bash
user@machine /path/to/count_fuzz$ 
```

# TODOs

Some ideas:
* We should have our own fuzz generator. Currently only cnf-fuzz-biere and brummayer are hooked up
* We should add functionality for determining the exact count of an instance. We could use Tbuddy for that, maybe?