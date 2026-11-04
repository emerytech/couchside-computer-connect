# Private/local portable build. Does not sign, publish, install or contact SignPath.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.build-venv/Scripts/python.exe')) {
    py -3.12 -m venv .build-venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 venv creation failed' }
}
$python = Join-Path $PSScriptRoot '.build-venv/Scripts/python.exe'
& $python -m pip install --only-binary=:all: --require-hashes --force-reinstall -r requirements.lock -r build-requirements.lock
if ($LASTEXITCODE -ne 0) { throw 'Hash-locked dependency installation failed' }
& $python -m PyInstaller --noconfirm --clean --onefile --windowed --name CouchsideComputerConnect --paths . --icon computer_connect/assets/couchside.ico --add-data "computer_connect/assets;computer_connect/assets" --copy-metadata websocket-client --copy-metadata Pillow --add-data "LICENSE;." --add-data "THIRD_PARTY.md;." run_connect.py
if ($LASTEXITCODE -ne 0) { throw 'Computer Connect build failed' }
& $python tools/collect_notices.py
if ($LASTEXITCODE -ne 0) { throw 'License inventory failed' }
(Get-FileHash -Algorithm SHA256 dist/CouchsideComputerConnect.exe).Hash.ToLower() + '  CouchsideComputerConnect.exe' | Set-Content -Encoding ascii dist/CouchsideComputerConnect.exe.sha256
Write-Host 'Local unsigned build ready. No installed agent was changed.'
