#requires -Version 5.1
<#
 .SYNOPSIS
  Build a single-file Windows executable for the GUI using PyInstaller.

 .DESCRIPTION
  This script packages `app/gui.py` into `dist/nanosamfw-gui.exe` with
  necessary resources and hidden imports to ensure runtime completeness.

 .USAGE
  Run from repo root in PowerShell:
    pwsh -File tools/windows_build.ps1

 .NOTES
  - Requires the project virtual environment and PyInstaller installed.
  - Uses the AppIcons/app_icon.ico when available.
#>

param(
  [switch]$Clean
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }

# Resolve repo root
$Root = Split-Path -Parent $PSCommandPath | Split-Path -Parent
Set-Location $Root

# Ensure venv Python
if (-not (Test-Path ".venv/Scripts/python.exe")) {
  Write-Warn "Virtual environment not found at .venv. Using system Python."
  $python = "python"
} else {
  $python = ".venv/Scripts/python.exe"
}

# Ensure PyInstaller is available
Write-Info "Ensuring PyInstaller is installed"
& $python -m pip install --quiet --upgrade pip | Out-Null
& $python -m pip show pyinstaller | Out-Null
if ($LASTEXITCODE -ne 0) {
  & $python -m pip install pyinstaller | Out-Null
}

if ($Clean) {
  Write-Info "Cleaning previous build artifacts"
  # Preserve config.toml in dist if it exists
  $configBackup = $null
  $distConfig = Join-Path $Root "dist/config.toml"
  if (Test-Path $distConfig) {
    $configBackup = Get-Content -Path $distConfig -Raw
    Write-Info "Preserving config.toml from dist/"
  }
  
  Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build, dist
  Get-ChildItem -Filter "*.spec" | Remove-Item -Force -ErrorAction SilentlyContinue
  
  # Restore config.toml if it was backed up
  if ($configBackup) {
    New-Item -ItemType Directory -Force -Path (Join-Path $Root "dist") | Out-Null
    Set-Content -Path $distConfig -Value $configBackup -NoNewline
    Write-Info "Restored config.toml to dist/"
  }
}

$iconPath = Join-Path $Root "AppIcons/app_icon.ico"
if (-not (Test-Path $iconPath)) {
  Write-Warn "Icon not found at $iconPath. Building without icon."
  $iconArg = @()
} else {
  $iconArg = @('--icon', $iconPath)
}

# Data files to include (icons now loaded via importlib.resources, SQL embedded in Python)
$dataArgs = @()
if (Test-Path (Join-Path $Root 'AppIcons')) {
  $dataArgs += '--add-data'; $dataArgs += "AppIcons;AppIcons"
}

# Hidden imports to ensure runtime modules are bundled
$hidden = @(
  'customtkinter',
  'pyperclip',
  'serial',
  'serial.tools.list_ports',
  'device',
  'download',
  'fus',
  'app.config',
  'app.device_monitor',
  'app.progress_tracker',
  'app.ui_builder',
  'app.ui_updater'
)
$hiddenArgs = @()
foreach ($m in $hidden) { $hiddenArgs += @('--hidden-import', $m) }

Write-Info "Running PyInstaller"
& $python -m PyInstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name nanosamfw-gui `
  $iconArg `
  $dataArgs `
  $hiddenArgs `
  app/gui.py

if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed" }

# Show result
$exe = Join-Path $Root 'dist/nanosamfw-gui.exe'
if (Test-Path $exe) {
  Write-Info "Build complete: $exe"
  
  # Copy config.toml to dist if not already present
  $distConfig = Join-Path $Root "dist/config.toml"
  if (-not (Test-Path $distConfig)) {
    $sourceConfig = Join-Path $Root "app/config.toml"
    if (Test-Path $sourceConfig) {
      Copy-Item $sourceConfig $distConfig
      Write-Info "Copied config.toml to dist/"
    } else {
      Write-Warn "Source config.toml not found at app/config.toml"
    }
  }
} else {
  throw "Build completed but executable not found in dist/"
}
