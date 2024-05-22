#!/bin/bash

echo "c o This script is for Track 2 in model counting competition 2023"

# STAREXEC_WALLCLOCK_LIMIT=3600
# STAREXEC_MAX_MEM=32000

file=$1
solved_file=$(mktemp XXXXXX.out)

mc=$(grep "^c t " $file)
echo "c o found header: $mc"
echo "c o file: ${file} solved_file: ${solved_file}"

timeout_total=${STAREXEC_WALLCLOCK_LIMIT}

time_begin=$(date +%s)



total_mem_gb=$(echo "scale=3; ${STAREXEC_MAX_MEM}/1024*0.75" | bc)

prec_failed_str="Assertion \`normalized_weights\[i + i\] != 0 && normalized_weights\[i + i\] != 1' failed."
find_ans_str="c s log10-estimate"

mpf_prec=1

while [ $mpf_prec -le 32 ]; do
    time_end=$(date +%s)
    timeout_mc=$((timeout_total + time_begin - time_end))

    echo "c o Running ExactMC, timeleft: ${timeout_mc} seconds, memo: ${total_mem_gb} GB, prec: ${mpf_prec}"
    echo "" > ${solved_file}
    ./KCBox ExactMC --heur minfill --competition --weighted --memo ${total_mem_gb}  --mpf_prec ${mpf_prec} --quiet ${file} 1>>${solved_file} 2>>${solved_file}

    prec_failed=$(grep "${prec_failed_str}" ${solved_file})
    if [ -n "${prec_failed}" ]; then
        mpf_prec=$((${mpf_prec} * 2))
    else
        break;
    fi
done

cat ${solved_file}
