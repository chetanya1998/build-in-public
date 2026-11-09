# Build Your Product in Public · installer for Windows (PowerShell)
#   irm https://raw.githubusercontent.com/chetanya1998/build-in-public/main/install.ps1 | iex
$ErrorActionPreference = "Stop"
$Pkg = if ($env:BIP_PACKAGE) { $env:BIP_PACKAGE } else { "git+https://github.com/chetanya1998/build-in-public.git" }

function Say($m) { Write-Host $m -ForegroundColor Cyan }
$py = (Get-Command py -ErrorAction SilentlyContinue)
$pyArgs = @("-3")
if (-not $py) { $py = (Get-Command python -ErrorAction SilentlyContinue); $pyArgs = @() }
if (-not $py) { Write-Host "Python 3.9+ is required: winget install Python.Python.3.12"; exit 1 }

Say "Installing Build Your Product in Public…"
if (Get-Command uv -ErrorAction SilentlyContinue) {
  uv tool install --force "build-in-public[full] @ $Pkg"
} elseif (Get-Command pipx -ErrorAction SilentlyContinue) {
  pipx install --force $Pkg; pipx inject build-in-public playwright psutil keyring pygments
} else {
  & $py.Source @pyArgs -m pip install --user --upgrade $Pkg playwright psutil keyring pygments
}

Say "Installing the browser used for screenshots (Chromium)…"
$bip = Get-Command buildinpublic -ErrorAction SilentlyContinue
try { if ($bip) { buildinpublic install-browser } else { & $py.Source @pyArgs -m buildinpublic install-browser } } catch { Write-Host "  (skipped: run 'buildinpublic install-browser' later)" }

Say "Starting setup…"
if (Get-Command buildinpublic -ErrorAction SilentlyContinue) { buildinpublic setup } else { & $py.Source @pyArgs -m buildinpublic setup }
