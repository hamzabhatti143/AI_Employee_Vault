#!/bin/bash
# Ralph Loop — keeps Claude CLI working until task is done
# Usage: ./ralph_loop.sh "your task description" [max_iterations]

TASK="$1"
MAX_ITERATIONS=${2:-10}
VAULT=/mnt/d/ai-employee-vault
iteration=0

if [ -z "$TASK" ]; then
    echo "Usage: ./ralph_loop.sh 'task description' [max_iterations]"
    exit 1
fi

echo "Starting Ralph Loop: $TASK"
echo "Max iterations: $MAX_ITERATIONS"

while [ $iteration -lt $MAX_ITERATIONS ]; do
    iteration=$((iteration + 1))
    echo "--- Iteration $iteration ---"

    output=$(cd "$VAULT" && unset CLAUDECODE && claude --print --model haiku -p "$TASK. When ALL steps are fully complete, output exactly: TASK_COMPLETE" 2>&1)

    echo "$output" | tail -5

    if echo "$output" | grep -q 'TASK_COMPLETE'; then
        echo "Task completed in $iteration iteration(s)."
        exit 0
    fi

    echo "Task not complete. Retrying..."
    sleep 5
done

echo "ERROR: Max iterations ($MAX_ITERATIONS) reached without completion."
exit 1
