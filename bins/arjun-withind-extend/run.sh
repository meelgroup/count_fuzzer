#!/bin/bash

./arjun --extend 1 "$1" tmp
echo "c t mc" > "$2"
cat tmp >> $2
