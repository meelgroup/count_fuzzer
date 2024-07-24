#!/bin/bash

# get relevant paths
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PROJECT_DIR=$(dirname "$SCRIPT_DIR")

f=$(realpath "$1")

# create relevant directories if necessary
proof_dir=$PROJECT_DIR/proofs
mkdir -p $proof_dir

# get filenames
ddnnf_file="${f##*/}.nnf"
proof_file="${f##*/}.trace"
output_file="${f##*/}.output"

# Run 
./d4 -dDNNF $f -out=$proof_dir/$ddnnf_file
cd $SCRIPT_DIR/nnf2trace
cargo run --release $f $proof_dir/$ddnnf_file > $proof_dir/$proof_file
cd $SCRIPT_DIR
./sharptrace_checker $proof_dir/$proof_file &> $proof_dir/$output_file