#!/bin/bash

./arjun "$1" tmp
echo "c t mc" > "$2"
grep -v "^c" tmp >>"$2"
