#/bin/bash
cd ./bins/sharpsat-td-precise/bin
./sharpSAT -WE -decot 1 -decow 1 -tmpdir tmpdir -cs 5 --prec 1000 "$1"
