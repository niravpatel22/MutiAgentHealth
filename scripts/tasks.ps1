<#
.SYNOPSIS
  Windows task runner (mirrors the Makefile).
.EXAMPLE
  ./scripts/tasks.ps1 test
#>
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('install', 'lint', 'format', 'test', 'api', 'web')]
    [string]$Task
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

function Invoke-Step([string]$Dir, [scriptblock]$Block) {
    Push-Location (Join-Path $root $Dir)
    try {
        & $Block
        if ($LASTEXITCODE -ne 0) { throw "Step failed in $Dir (exit $LASTEXITCODE)" }
    }
    finally { Pop-Location }
}

switch ($Task) {
    'install' {
        Invoke-Step 'backend' { uv sync --frozen }
        Invoke-Step 'frontend' { npm ci }
    }
    'lint' {
        Invoke-Step 'backend' { uv run ruff check .; if ($LASTEXITCODE -eq 0) { uv run black --check . } }
        Invoke-Step 'frontend' { npm run lint; if ($LASTEXITCODE -eq 0) { npm run format:check } }
    }
    'format' {
        Invoke-Step 'backend' { uv run ruff check --fix .; uv run black . }
        Invoke-Step 'frontend' { npm run format }
    }
    'test' {
        Invoke-Step 'backend' { uv run pytest --cov=app -m 'not live_llm' }
        Invoke-Step 'frontend' { npm test }
    }
    'api' { Invoke-Step 'backend' { uv run uvicorn app.main:app --reload } }
    'web' { Invoke-Step 'frontend' { npm run dev } }
}
