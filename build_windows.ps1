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
        $process = Start-Process -FilePath (Join-Path $PSScriptRoot "dist\RobotDePrecios.exe") -ArgumentList @("--self-test", ('"' + $report + '"')) -WindowStyle Hidden -Wait -PassThru
        if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $report)) { throw "Executable startup check failed." }
        $result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
        if (-not $result.ok) { throw "Executable smoke test failed: $($result.error)" }
    } finally {
        $env:BAP_ROBOT_DATA_DIR = $previousDataDir
    }
    Write-Host "Built: $PSScriptRoot\dist\RobotDePrecios.exe"

    # Installer (Inno Setup 6.3+). If it isn't installed yet, install it with winget, then build.
    function Find-Iscc {
        $candidates = @()
        $onPath = Get-Command ISCC.exe -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1
        if ($onPath) { $candidates += $onPath }
        # where the Inno Setup installer says it put itself (per-user or per-machine install)
        foreach ($key in @("HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup*",
                           "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup*",
                           "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup*")) {
            foreach ($entry in @(Get-ItemProperty -Path $key -ErrorAction SilentlyContinue)) {
                if ($entry.InstallLocation) { $candidates += (Join-Path $entry.InstallLocation "ISCC.exe") }
            }
        }
        # the usual folders (Inno Setup 6 or newer)
        foreach ($base in @((Join-Path $env:LOCALAPPDATA "Programs"), ${env:ProgramFiles(x86)}, $env:ProgramFiles)) {
            if ($base -and (Test-Path -LiteralPath $base)) {
                $candidates += @(Get-ChildItem -Path $base -Filter "Inno Setup*" -Directory -ErrorAction SilentlyContinue |
                                 Sort-Object Name -Descending | ForEach-Object { Join-Path $_.FullName "ISCC.exe" })
            }
        }
        return $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
    }
    $iscc = Find-Iscc
    if (-not $iscc -and (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host "Inno Setup not found: installing it with winget..."
        winget install --id JRSoftware.InnoSetup -e --accept-package-agreements --accept-source-agreements
        $iscc = Find-Iscc
    }
    if (-not $iscc) {
        throw "Inno Setup 6 is needed to build the installer. Install it from https://jrsoftware.org/isdl.php (or: winget install JRSoftware.InnoSetup), then run this script again."
    }
    Write-Host "Using Inno Setup: $iscc"
    & $iscc (Join-Path $PSScriptRoot "installer.iss")
    if ($LASTEXITCODE -ne 0) { throw "Installer build failed." }
    Write-Host ""
    Write-Host "Installer ready: $PSScriptRoot\dist\RobotDePrecios_Instalador.exe" -ForegroundColor Green
} finally {
    Pop-Location
}
