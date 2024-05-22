#!/bin/bash

echo "c o This script is for Track 2 in model counting competition 2023"

# STAREXEC_WALLCLOCK_LIMIT=3600
# STAREXEC_MAX_MEM=32000

file=$1
clean_file=$(mktemp XXXXXX.cnf)
preprocessed_file=$(mktemp XXXXXX.cnf)

mc=$(grep "^c t " $file)
echo "c o found header: $mc"
echo "c o file: ${file} preprocessed_file: ${preprocessed_file}"

timeout_total=${STAREXEC_WALLCLOCK_LIMIT}

time_begin=$(date +%s)
timeout_be=$((timeout_total/12))
echo "c o Running SharpSatTD-Pre with timeout: ${timeout_be} seconds"
./doalarm ${timeout_be} ./sharpSATPre -W -cpu-lim=${timeout_be} ${file} > ${preprocessed_file}

preprocessing_status=$(grep "^p cnf" ${preprocessed_file})
if [[ ${preprocessing_status} == *"p cnf"* ]]; then
   echo "c o SharpSatTD-Pre succeeded"
else
   echo "c o WARNING! SharpSATTD-Pre did NOT succeed"
   cat ${file} > ${preprocessed_file}
fi
time_end=$(date +%s)

factor=1
log10_factor=0

log10_fact_status=$(grep "^c o log10-wf" ${preprocessed_file})
if [[ ${log10_fact_status} == *"c o log10-wf"* ]]; then
   echo "c o SharpSATPre find log10 weight factor: ${log10_fact_status}"
   log10_factor=$(echo ${log10_fact_status} | cut -d " " -f 4 | bc -l)
fi
echo "c o log10-wf ${log10_factor}"

fact_status=$(grep "^c o wf" ${preprocessed_file})
if [[ ${fact_status} == *"c o wf"* ]]; then
   echo "c o SharpSATPre find weight factor: ${fact_status}"
   factor=$(echo ${fact_status} | cut -d " " -f 4 | bc -l)
fi
echo "c o wf ${factor}"

timeout_mc=$((timeout_total + time_begin - time_end))
total_mem_gb=$(echo "scale=3; ${STAREXEC_MAX_MEM}/1024*0.75" | bc)

prec_failed_str="Assertion \`normalized_weights\[i + i\] != 0 && normalized_weights\[i + i\] != 1' failed."
find_ans_str="c s log10-estimate"
solved_file=$(mktemp XXXXXX.out)

if [[ $(echo "$factor == 1.0" | bc) -ne 1 ]]; then 
   mpf_prec=1
   while [ $mpf_prec -le 32 ]; do
      time_end=$(date +%s)
      timeout_mc=$((timeout_total + time_begin - time_end))

      echo "c o Running ExactMC, timeleft: ${timeout_mc} seconds, memo: ${total_mem_gb} GB, prec: ${mpf_prec}"
      echo "" > ${solved_file}
      ./KCBox ExactMC --competition --weighted --memo ${total_mem_gb}  --mpf_prec ${mpf_prec} --quiet ${preprocessed_file} 1>>${solved_file} 2>>${solved_file}

      prec_failed=$(grep "${prec_failed_str}" ${solved_file})
      if [ -n "${prec_failed}" ]; then
         mpf_prec=$((${mpf_prec} * 2))
      else
         break;
      fi
   done

   state=$(grep "^s" ${solved_file})
   log10_count=$(grep "c s log10-estimate" ${solved_file} | cut -d " " -f 4 | bc -l)
   echo "c o log10-count: ${log10_count}"

   count=$(grep "c s exact arb float" ${solved_file} | cut -d " " -f 6 | bc -l)
   
   export BC_LINE_LENGTH=1000000000
   log10_count=$(echo "${log10_count} + ${log10_factor}" | bc -l)
   tuned_count=$(echo "${factor} * ${count}" | bc -l)

   while read line; do
      echo "c o $line"
   done < ${solved_file}

   echo $state
   echo "c s type wmc"
   printf "c s log10-estimate %.16f\n" ${log10_count}
   printf "c s exact arb float %.16f\n" ${tuned_count}

else  
   echo "c o Running ExactMC, timeleft: ${timeout_mc} seconds, memo: ${total_mem_gb} GB"
   ./KCBox ExactMC --competition --weighted --memo ${total_mem_gb} --quiet ${preprocessed_file}

   mpf_prec=1
   while [ $mpf_prec -le 32 ]; do
      time_end=$(date +%s)
      timeout_mc=$((timeout_total + time_begin - time_end))

      echo "c o Running ExactMC, timeleft: ${timeout_mc} seconds, memo: ${total_mem_gb} GB, prec: ${mpf_prec}"
      echo "" > ${solved_file}
      ./KCBox ExactMC --competition --weighted --memo ${total_mem_gb}  --mpf_prec ${mpf_prec} --quiet ${preprocessed_file} 1>>${solved_file} 2>>${solved_file}

      prec_failed=$(grep "${prec_failed_str}" ${solved_file})
      if [ -n "${prec_failed}" ]; then
         mpf_prec=$((${mpf_prec} * 2))
      else
         break;
      fi
   done

   cat ${solved_file}
fi

