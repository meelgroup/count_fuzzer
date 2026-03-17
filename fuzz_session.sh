#!/bin/bash
#
# Create a tmux session with 24 fuzzing windows running fuzz.py
#
# Usage:
#   ./fuzz_session.sh [options]
#
# Examples:
#   ./fuzz_session.sh                    # Run fuzz.py with default options
#   ./fuzz_session.sh --exact --threads 1  # Run with --exact --threads 1
#   ./fuzz_session.sh --weighted --proj    # Run weighted projected fuzzing
#
# All arguments passed to this script are forwarded to fuzz.py in each window.
# If the session already exists, it will attach to it instead of creating a new one.

SESSION="fuzzing"
DIR="/home/soos/development/sat_solvers/count_fuzzer"
CMD="./fuzz.py $@"

# Attach if session already exists
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Session '$SESSION' already exists, attaching..."
  tmux attach -t "$SESSION"
  exit 0
fi

# Create session with first window
tmux new-session -d -s "$SESSION" -c "$DIR" -n "fuzz-1"
tmux send-keys -t "$SESSION:1" "$CMD" Enter

# Create remaining windows
for i in $(seq 2 24); do
  tmux new-window -t "$SESSION" -c "$DIR" -n "fuzz-$i"
  tmux send-keys -t "$SESSION:$i" "$CMD" Enter
done

# Select first window and attach
tmux select-window -t "$SESSION:1"
tmux attach -t "$SESSION"
