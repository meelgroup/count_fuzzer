#!/bin/bash

./arjun --extend 1 "$1" tmp || exit 255
echo "c t mc" > "$2"
cat tmp >> $2
