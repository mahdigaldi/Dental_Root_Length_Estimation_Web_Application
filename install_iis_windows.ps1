param(
    [string]$PythonCommand = "py -3.12",
    [string]$AppPoolName = "DentalWeb"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

New-Item -ItemType Directory -Force -Path ".\logs", ".\static\uploads", ".\static\outputs" | Out-Null

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Invoke-Expression "$PythonCommand -m venv .venv"
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

$identity = "IIS AppPool\$AppPoolName"
icacls ".\logs" /grant "${identity}:(OI)(CI)M" /T
icacls ".\static\uploads" /grant "${identity}:(OI)(CI)M" /T
icacls ".\static\outputs" /grant "${identity}:(OI)(CI)M" /T

Write-Host "IIS web app dependencies are installed."
Write-Host "If your App Pool name is different, rerun with: .\install_iis_windows.ps1 -AppPoolName YourAppPoolName"
