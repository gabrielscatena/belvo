param(
    [ValidateSet('clients', 'loan_snapshots', 'payment_attempts')]
    [string[]]$Datasets = @('clients', 'loan_snapshots', 'payment_attempts')
)

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$edaPython = Join-Path $projectRoot '.venv-eda/Scripts/python.exe'
$edaScript = Join-Path $projectRoot 'tools/eda/eda_report.py'

if (-not (Test-Path -LiteralPath $edaPython)) {
    throw 'Missing .venv-eda. Create it with Python 3.12 and install conf/requirements-eda.txt.'
}

& $edaPython -X utf8 -c "import sys; assert sys.version_info[:2] == (3, 12), 'Use Python 3.12'; import pandas, numpy; from ydata_profiling import ProfileReport"
if ($LASTEXITCODE -ne 0) {
    throw 'EDA environment validation failed. Install conf/requirements-eda.txt in .venv-eda.'
}

foreach ($dataset in $Datasets) {
    $inputFile = Join-Path $projectRoot "data/raw/$dataset.csv"
    if (-not (Test-Path -LiteralPath $inputFile)) {
        throw "Missing input: $inputFile"
    }
}

$runId = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
$outputRoot = Join-Path $projectRoot "reports/eda/$runId"

foreach ($dataset in $Datasets) {
    $inputFile = Join-Path $projectRoot "data/raw/$dataset.csv"
    $outputDir = Join-Path $outputRoot $dataset
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
    Write-Host "Running EDA: $dataset" -ForegroundColor Cyan

    # Keep the upstream script's log alongside this dataset's reports.
    Push-Location -LiteralPath $outputDir
    try {
        & $edaPython -X utf8 $edaScript $inputFile --output-dir $outputDir --log-level INFO --skip-evidently
        if ($LASTEXITCODE -ne 0) {
            throw "EDA failed for $dataset. See $outputDir/eda_analysis.log."
        }
        # The upstream CLI can return zero even if HTML generation failed.
        foreach ($report in @('ydata_profiling_report.html', 'summary_report.txt')) {
            $reportPath = Join-Path $outputDir $report
            if (-not (Test-Path -LiteralPath $reportPath) -or (Get-Item -LiteralPath $reportPath).Length -eq 0) {
                throw "Missing or empty report: $reportPath. See $outputDir/eda_analysis.log."
            }
        }
    }
    finally {
        Pop-Location
    }
}

# Reached only after every requested dataset has both reports.
Write-Host "EDA completed. Reports: $outputRoot" -ForegroundColor Green
