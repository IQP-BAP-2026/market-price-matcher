param([string]$Python = "python")
$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
try {
    & $Python -m PyInstaller --noconfirm PriceRobot.spec
    if ($LASTEXITCODE -ne 0) { throw "Executable build failed." }
    $smokeFolder = Join-Path $PSScriptRoot "build\standalone-smoke"
    New-Item -ItemType Directory -Force -Path $smokeFolder | Out-Null
    $report = Join-Path $smokeFolder "report.json"
    $previousDataDir = $env:BAP_ROBOT_DATA_DIR
    try {
        $env:BAP_ROBOT_DATA_DIR = $smokeFolder
        $process = Start-Process -FilePath (Join-Path $PSScriptRoot "dist\PriceRobot.exe") -ArgumentList @("--self-test", ('"' + $report + '"')) -WindowStyle Hidden -Wait -PassThru
        if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $report)) { throw "Executable startup check failed." }
        $result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
        if (-not $result.ok) { throw "Executable smoke test failed: $($result.error)" }
    } finally {
        $env:BAP_ROBOT_DATA_DIR = $previousDataDir
    }
    Write-Host "Built: $PSScriptRoot\dist\PriceRobot.exe"
} finally {
    Pop-Location
}
