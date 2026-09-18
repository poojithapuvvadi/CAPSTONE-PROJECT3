<#
Run this from the project root to create a venv, install dependencies,
create/update .env, and start the Streamlit app.

Usage examples:
  # Basic (no LLM usage)
  .\scripts\run_local.ps1

  # Enable LLM and pass OpenAI key
  .\scripts\run_local.ps1 -UseLLM -OpenAIKey "sk-..."

Notes:
- PowerShell execution policy may block script execution. Run: `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` if needed.
- The script will back up any existing `.env` to `.env.bak` before creating a new one.
#>

param(
    [switch]$UseLLM,
    [string]$OpenAIKey = "",
    [string]$AnthropicKey = ""
)

function Assert-ProjectRoot {
    if (-not (Test-Path "app.py")) {
        Write-Error "Run this script from the project root (where app.py exists)."
        exit 1
    }
}

Assert-ProjectRoot

Write-Host "--- Preparing local runtime for AI IT Support Assistant ---"

# Check Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Error "Python not found on PATH. Install Python 3.10+ and re-run."
    exit 1
}

# Create venv if missing
if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment .venv..."
    python -m venv .venv
} else {
    Write-Host ".venv already exists."
}

# Activate venv for this script
Write-Host "Activating virtual environment..."
& .\.venv\Scripts\Activate.ps1

Write-Host "Upgrading pip and installing dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

# Prepare .env
if (Test-Path ".env") {
    Write-Host "Backing up existing .env -> .env.bak"
    Copy-Item .env .env.bak -Force
}

Write-Host "Creating .env file"
$envLines = @()
$envLines += "LLM_PROVIDER=openai"
$envLines += "USE_LLM_RESPONSES=$($UseLLM.IsPresent.ToString().ToLower())"
if ($OpenAIKey -ne "") { $envLines += "OPENAI_API_KEY=$OpenAIKey" } else { $envLines += "OPENAI_API_KEY=" }
if ($AnthropicKey -ne "") { $envLines += "ANTHROPIC_API_KEY=$AnthropicKey" } else { $envLines += "ANTHROPIC_API_KEY=" }

$envLines | Set-Content -Path .env -Encoding UTF8

Write-Host ".env created. (backup: .env.bak if existed)"

Write-Host "Ensuring data folder exists"
if (-not (Test-Path "data")) { New-Item -ItemType Directory -Path data | Out-Null }

Write-Host "Starting Streamlit app on port 8501..."
streamlit run app.py --server.port=8501 --server.address=0.0.0.0
