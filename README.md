# AI IT Support Assistant

This project is a realistic local agentic AI assistant for an IT support team. It demonstrates LangGraph orchestration, LLM-based intent detection, stateful multi-turn conversations, local tool calling, and SQLite-backed data storage.

**Now with LLM integration!** The system uses either OpenAI (GPT-4) or Anthropic (Claude) for:
- Natural language intent classification
- Human-like response generation
- Context-aware support interactions

## Included capabilities

- LLM-based intent detection (with keyword matching fallback)
- LLM-based response generation (with template fallback)
- Knowledge search over a local IT knowledge base
- Employee lookup by employee ID
- Ticket lookup by employee or ticket ID
- Ticket creation with validation and duplicate checks
- Ticket status updates (Open, In Progress, Resolved, Closed)
- System health checks for common internal services
- Conversation memory across turns
- Conditional routing in a LangGraph workflow
- Local SQLite persistence with JSON seed data for quick setup
- Streamlit-based UI with chat history and tool trace visibility

## Setup

### Prerequisites
- Python 3.10+
- An API key from either:
  - OpenAI: https://platform.openai.com/api-keys
  - Anthropic: https://console.anthropic.com/

### Installation

1. Clone the repository and create a virtual environment:
```bash
cd Capstone-project3
python -m venv .venv
.venv\Scripts\activate  # On Windows
source .venv/bin/activate  # On macOS/Linux
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure your LLM provider by creating a `.env` file (copy from `.env.example`):
```bash
cp .env.example .env
```

4. Edit `.env` and add your API key:
```
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
USE_LLM_RESPONSES=true
```

Or for Anthropic Claude:
```
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key-here
USE_LLM_RESPONSES=true
```

### Running the app

```bash
streamlit run app.py
```

The app will be available at http://localhost:8501

## Docker Deployment

### Using Docker Compose (Recommended)

1. Create a `.env` file with your API keys:
```bash
cp .env.example .env
# Edit .env and add your OpenAI or Anthropic API key
```

2. Build and run the container:
```bash
docker-compose up --build
```

3. Access the app at http://localhost:8501

4. Stop the container:
```bash
docker-compose down
```

### Using Docker CLI

1. Build the image:
```bash
docker build -t ai-it-support-assistant .
```

2. Run the container:
```bash
docker run -p 8501:8501 \
  -e OPENAI_API_KEY=sk-your-key-here \
  -e LLM_PROVIDER=openai \
  -v $(pwd)/data:/app/data \
  ai-it-support-assistant
```

On Windows (PowerShell):
```powershell
docker run -p 8501:8501 `
  -e OPENAI_API_KEY=sk-your-key-here `
  -e LLM_PROVIDER=openai `
  -v ${PWD}/data:/app/data `
  ai-it-support-assistant
```

3. Access the app at http://localhost:8501

### Environment Variables for Docker

Pass these as `-e` flags or in the `docker-compose.yml`:
- `OPENAI_API_KEY` — Your OpenAI key
- `ANTHROPIC_API_KEY` — Your Anthropic key
- `LLM_PROVIDER` — `openai` or `anthropic` (default: `openai`)
- `USE_LLM_RESPONSES` — `true` or `false` (default: `true`)

### Persisting Data

The SQLite database is stored in the `data/` volume. Use `-v` or the `volumes` section in docker-compose.yml to persist data across container restarts.

## LLM Configuration

The system can use either OpenAI GPT-4 or Anthropic Claude for intelligence. Configuration is via environment variables:

| Variable | Options | Purpose |
|----------|---------|---------|
| `LLM_PROVIDER` | `openai`, `anthropic` | Which LLM to use |
| `USE_LLM_RESPONSES` | `true`, `false` | Enable LLM response generation (fallback to templates if disabled) |
| `OPENAI_API_KEY` | sk-... | OpenAI API key |
| `ANTHROPIC_API_KEY` | sk-ant-... | Anthropic API key |

If no API key is configured, the system gracefully falls back to rule-based intent detection and template-based responses.

## Project structure

- `app.py` — Streamlit interface
- `src/agent.py` — LangGraph workflow and routing logic
- `src/data_store.py` — SQLite-backed local data layer
- `src/llm_service.py` — LLM integration (OpenAI/Anthropic)
- `data/` — seed JSON files and SQLite database files
- `requirements.txt` — Python dependencies

## Example prompts

- How do I reset my VPN password?
- Show my employee profile
- What is the status of my ticket?
- My VPN is not working. Please raise a ticket.
- Update ticket IT-1001 to resolved.
- Check the system status for VPN.

## Run locally

1. Install dependencies:
   `python -m pip install -r requirements.txt`
2. Start the app:
   `streamlit run app.py`

## Using the LLM as SQL query generator (Option 3)

This project supports a safe hybrid mode where the LLM writes a read-only SQL query for lookup operations instead of using a hardcoded SQL shape. This is helpful when you want more natural-language-driven database queries while still keeping data access controlled.

### Environment variables

```powershell
$Env:USE_LLM_SQL='true'
$Env:LLM_PROVIDER='openai'   # or 'anthropic'
$Env:OPENAI_API_KEY='your-key'
```

### Safety rules

- Only `SELECT` queries are allowed.
- Mutating statements are rejected.
- The schema is passed to the model for grounding.
- The DB remains SQLite-backed for persistence.

### Example run

```powershell
streamlit run app.py
```

Your agent can now do lookups like:
- "What is the status of IT-1001?"
- "Show me employee EMP1024"
- "Are the VPN systems healthy?"

This still uses the local SQLite database under the hood, but the query generation is LLM-driven and constrained to safe reads.

## Notes

This is intentionally realistic and local-only. It avoids external enterprise system integrations and uses a SQLite database for persistence so the project remains simple enough to run on a normal machine while still demonstrating agentic workflow patterns.
