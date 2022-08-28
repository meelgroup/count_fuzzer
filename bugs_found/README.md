# Bugs Found

## SharpSAT -- manual

```
p cnf 4 4
-2 4 0
3 4 0
-3 -4 0
3 -4 0
```

Bug output:

```
soos@tiresias:count_fuzzer$ ../sharpSAT/build/sharpSAT a.cnf 
Solving a.cnf
variables (all/used/free):      4/4/0
clauses (all/long/binary/unit): 4/0/4/0

Preprocessing .. DONE
variables (all/used/free):      1/0/1
clauses (all/long/binary/unit): 0/0/0/0
56 16
sharpSAT: /home/soos/development/sat_solvers/sharpSAT/src/component_types/difference_packed_component.h:119: DifferencePackedComponent::DifferencePackedComponent(Component&): Assertion `(data_size >> bits_of_data_size()) == 0' failed.
Aborted (core dumped)`
```

Bug reported [here](https://github.com/marcthurley/sharpSAT/pull/15). Bug fix diff: `4448d8e69af30df98b370f37d8acf3d95b5385a6`


# SharpSAT -- fuzzed

File: `fuzzTest_85.cnf`. Seed: 747327, git of fuzzer: `b613ebba4fd993d0f72df1a0880594629430ec31`. git of sharpSAT: `edfbde3424ce17d72d7f8d8f5b8681f2247f4932`. Bug is:

```
../../../sharpSAT/build/sharpSAT fuzzTest_85.cnf 
sharpSAT: /home/soos/development/sat_solvers/sharpSAT/src/instance.h:211: ClauseIndex Instance::addClause(std::vector<LiteralID>&): Assertion `!isUnitClause(literals[0].neg())' failed.
Aborted (core dumped)
```
