#!/usr/bin/env bash
# Wrapper so agents can report task metrics from their role subdirectories.
# Usage mirrors agent_metrics.py record, plus --task-id for reference.
# Agents call: ../scripts/report-task-metrics.sh --feature-name X --task-id T001 ...

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
METRICS_PY="${REPO_ROOT}/project-administrator/agent_metrics.py"

feature_name=""
task_id=""
task_description=""
time_spent_seconds=""
tokens_spent=""
token_source="self-reported"
model_used=""
notes=""
agent_name=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --feature-name)    feature_name="$2";    shift 2 ;;
    --task-id)         task_id="$2";         shift 2 ;;
    --task-description) task_description="$2"; shift 2 ;;
    --time-spent-seconds) time_spent_seconds="$2"; shift 2 ;;
    --tokens-spent)    tokens_spent="$2";    shift 2 ;;
    --token-source)    token_source="$2";    shift 2 ;;
    --model-used)      model_used="$2";      shift 2 ;;
    --notes)           notes="$2";           shift 2 ;;
    --agent-name)      agent_name="$2";      shift 2 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$feature_name" || -z "$task_description" || -z "$model_used" ]]; then
  echo "Usage: report-task-metrics.sh --feature-name NAME --task-description DESC --model-used MODEL [--task-id ID] [--time-spent-seconds N] [--tokens-spent N] [--token-source TYPE] [--agent-name NAME] [--notes TEXT]" >&2
  exit 1
fi

# Derive agent name from caller's directory name if not supplied
if [[ -z "$agent_name" ]]; then
  agent_name="$(basename "$(pwd)")"
fi

# Prepend task-id to description if provided
if [[ -n "$task_id" ]]; then
  task_description="${task_id}: ${task_description}"
fi

args=(
  --agent-name "$agent_name"
  --feature-name "$feature_name"
  --task-description "$task_description"
  --model-used "$model_used"
  --token-source "$token_source"
)

[[ -n "$time_spent_seconds" ]] && args+=(--time-spent-seconds "$time_spent_seconds")
[[ -n "$tokens_spent" ]]        && args+=(--tokens-spent "$tokens_spent")
[[ -n "$notes" ]]               && args+=(--notes "$notes")

python3 "${METRICS_PY}" record "${args[@]}"
