#!/usr/bin/env bash
# Run from project root. Creates venv, installs deps, creates .env, and starts Streamlit.

set -euo pipefail

USE_LLM=false
OPENAI_KEY=""
ANTHROPIC_KEY=""

while [[ "$#" -gt 0 ]]; do
  case $1 in
    --use-llm|-l) USE_LLM=true; shift ;;
    --openai-key) OPENAI_KEY="$2"; shift 2 ;;
    --anthropic-key) ANTHROPIC_KEY="$2"; shift 2 ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

if [[ ! -f app.py ]]; then
  echo "Run this script from the project root (where app.py exists)."
  exit 1
fi

python3 -m venv .venv || python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [[ -f .env ]]; then
  cp .env .env.bak
fi

cat > .env <<EOF
LLM_PROVIDER=openai
USE_LLM_RESPONSES=$USE_LLM
OPENAI_API_KEY=$OPENAI_KEY
ANTHROPIC_API_KEY=$ANTHROPIC_KEY
EOF

mkdir -p data

streamlit run app.py --server.port=8501 --server.address=0.0.0.0
