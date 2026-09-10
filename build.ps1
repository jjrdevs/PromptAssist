# PromptAssist - one-click build on Windows.
#
#   .\build.ps1             -> CLI + GUI, share folder, zip
#   .\build.ps1 -SkipGui    -> CLI only
#   .\build.ps1 -SkipCli    -> GUI only
#   .\build.ps1 -NoZip      -> skip the shareable zip
#
# Produces:  dist\PromptAssist.exe   (tray GUI)
#            dist\passist.exe        (one-file CLI, bundled prompts)
#            dist\setup\             (ready-to-share folder + README-USE.md)
#            PromptAssist-windows.zip
#
# If the GUI step fails (no WebView2/Rust), the CLI is still built and works.

$ErrorActionPreference = "Stop"
param([switch]$SkipCli, [switch]$SkipGui, [switch]$NoZip)

function Info($m) { Write-Host "  [ .. ] $m" -ForegroundColor DarkCyan }
function Ok($m)   { Write-Host "  [ OK ] $m" -ForegroundColor DarkGreen }
function Warn($m) { Write-Host "  [ !  ] $m" -ForegroundColor DarkYellow }
function Fail($m) { Write-Host "  [ XX ] $m" -ForegroundColor DarkRed; throw $m }
function SizeMB($f) { if (Test-Path $f) { [math]::Round((Get-Item $f).Length / 1MB, 1) } else { 0 } }

$Repo     = $PSScriptRoot
$Dist     = Join-Path $Repo "dist"
$Setup    = Join-Path $Dist "setup"
$CliExe   = Join-Path $Dist "passist.exe"
$GuiExe   = Join-Path $Dist "PromptAssist.exe"
$Zip      = Join-Path $Repo "PromptAssist-windows.zip"

Write-Host ""
Write-Host "  PromptAssist build" -ForegroundColor Cyan
Write-Host "  repo: $Repo"
Write-Host ""

# ----------------------------------------------------------------- 0. prereq
Info "0) checking prerequisites"
$pythonVer = (& python --version 2>&1) -join " "
if (-not $pythonVer) { Fail "python not found; install Python 3.10+ (python.org)" }
Ok "python: $pythonVer"

$guiWanted = -not $SkipGui
if ($guiWanted) {
    if ($env:TAURI_DEV) { Warn "TAURI_DEV set - GUI step disabled"; $guiWanted = $false }
    $cargoVer = (& cargo --version 2>&1) -join " "
    if (-not $cargoVer) { Warn "cargo not found - GUI step skipped"; $guiWanted = $false }
    else {
        Ok "cargo: $cargoVer"
        $nodeVer = (& node --version 2>&1) -join " "
        if (-not $nodeVer) { Warn "node not found - GUI step skipped"; $guiWanted = $false }
        else { Ok "node:  $nodeVer" }
    }
}
# ------------------------------------------------------------ 1. CLI build
if (-not $SkipCli) {
    Write-Host ""
    Info "1) building one-file CLI  (PyInstaller)"
    (& python -m pip install --quiet --upgrade pyinstaller 2>&1) | Out-Null
    if ($LASTEXITCODE -ne 0) { Fail "pip install pyinstaller failed" }

    (& python -m PyInstaller -y --clean passist.spec 2>&1) | Select-Object -Last 3 |
        ForEach-Object { Write-Host "       $_" }

    if (-not (Test-Path $CliExe)) { Fail "PyInstaller did not produce dist\passist.exe" }
    Ok "dist\passist.exe  ($((SizeMB $CliExe)) MB)"
} else {
    Write-Host ""
    Info "1) CLI skipped (-SkipCli)"
}

# ------------------------------------------------------------ 2. GUI build
if ($guiWanted) {
    Write-Host ""
    Info "2) building Tauri desktop GUI"
    Push-Location (Join-Path $Repo "gui")
    try {
        (& cargo tauri build 2>&1) | Select-Object -Last 8 | ForEach-Object { Write-Host "       $_" }
    }
    finally { Pop-Location }

    if (-not (Test-Path $GuiExe)) {
        Warn "cargo tauri build did not produce dist\PromptAssist.exe"
        Warn "       GUI is not bundled, but CLI remains usable."
        $guiWanted = $false
    } else {
        Ok "dist\PromptAssist.exe  ($((SizeMB $GuiExe)) MB)"
    }
} else {
    Write-Host ""
    Info "2) GUI skipped"
}
# ------------------------------------------------------------ 3. share folder
Write-Host ""
Info "3) assembling share folder  ->  dist\setup\"
if (Test-Path $Setup) { Remove-Item -Recurse -Force $Setup }
New-Item -ItemType Directory -Path $Setup | Out-Null
if (-not $SkipCli -and (Test-Path $CliExe)) { Copy-Item $CliExe (Join-Path $Setup "passist.exe") }
if ($guiWanted  -and (Test-Path $GuiExe)) { Copy-Item $GuiExe (Join-Path $Setup "PromptAssist.exe") }

$useReadme = Join-Path $Setup "README-USE.md"
@'
# PromptAssist

Two programs in one folder:

- **PromptAssist.exe** -- desktop GUI (tray app + shortcut window)
- **passist.exe**      -- command-line version (no GUI)

Both use the same feature store and settings:

    %LOCALAPPDATA%\PromptAssist\

## Quick start (terminal)

    passist new my_feature --target C:\myRepo
    passist run research my_feature
    passist run plan my_feature
    passist run check-plan my_feature
    passist run build my_feature
    passist run continue my_feature
    passist run review-code my_feature
    passist list-bindings

Each `passist run ...` prints a full paste-ready prompt to stdout and,
if you have clipboard access, also copies it. Paste it into your AI
coding tool's prompt box.

## Re-emit the agent-side workflow files (optional)

    passist sync-agent --target C:\myRepo

That writes CLAUDE.md, AGENTS.md, .github\copilot-instructions.md, and
GEMINI.md into your repo.

## Settings

Open PromptAssist.exe -> Settings. The stage names, stop-rule lines, and
the exact prompt text for each stage live in `prompts.yaml`. The global
auto-paste on/off flag lives in `%LOCALAPPDATA%\PromptAssist\settings.json`.
'@ | Set-Content -Path $useReadme -Encoding UTF8
Ok "dist\setup\"
if ($SkipCli -and $guiWanted) {
    Write-Host "      (PromptAssist.exe, README-USE.md)" -ForegroundColor DarkCyan
} else {
    Write-Host "      (PromptAssist.exe, passist.exe, README-USE.md)" -ForegroundColor DarkCyan
}

# ------------------------------------------------------------ 4. zip
if ($NoZip) {
    Write-Host ""
    Info "4) zip skipped (-NoZip)"
} else {
    Write-Host ""
    Info "4) zipping  ->  PromptAssist-windows.zip"
    if (Test-Path $Zip) { Remove-Item -Force $Zip }
    Compress-Archive -Path (Join-Path $Dist "setup") -DestinationPath $Zip -Force
    Ok "PromptAssist-windows.zip  ($((SizeMB $Zip)) MB)"
}

Write-Host ""
Write-Host "  build complete" -ForegroundColor Green
$ShareMsg = "   share dist\setup\ (or the zip) to your colleague; they just double-click."
Write-Host "  $ShareMsg" -ForegroundColor DarkCyan
if (-not $guiWanted) {
    Write-Host "  (GUI not built -- CLI only)" -ForegroundColor DarkYellow
}
