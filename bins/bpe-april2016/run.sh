#!/bin/bash
./bpe_linux $1 | grep -v "^c" > tmp
 if  grep -q '^s UNSAT' tmp; then
     echo "c t mc" > $2
     echo "p cnf 1 1" >> $2
     echo "0" >> $2
 else
    echo "c t mc" > $2
    cat tmp >> $2
fi
