[CmdletBinding()]
param(
    [string]$OutputDirectory = (Join-Path (Split-Path -Parent $PSScriptRoot) 'dist-windows')
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$python = Get-Command python -ErrorAction Stop
$node = Get-Command node -ErrorAction Stop
$pyinstallerVersion = (Get-Content (Join-Path $repo 'packaging/windows-version.txt') -Raw).Trim()
if ($pyinstallerVersion -notmatch '^\d+\.\d+\.\d+$') { throw 'Invalid PyInstaller pin.' }
$resolvedOutput = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $resolvedOutput) {
    throw "Output directory already exists: $resolvedOutput. Choose a new empty directory; existing files are never removed."
}
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'

Push-Location $repo
try {
    Write-Host 'Running Python test suite...'
    & $python.Source -B -m unittest discover -p 'test_*.py'
    if ($LASTEXITCODE -ne 0) { throw "Python tests failed ($LASTEXITCODE)." }

    Write-Host 'Running JavaScript tests...'
    & $node.Source scripts/test-js.cjs
    if ($LASTEXITCODE -ne 0) { throw "JavaScript tests failed ($LASTEXITCODE)." }

    Write-Host 'Checking public release files...'
    & $python.Source -B scripts/check-release.py
    if ($LASTEXITCODE -ne 0) { throw "Release hygiene check failed ($LASTEXITCODE)." }

    Write-Host 'Checking scenario bank and generated HTML...'
    & $python.Source -B validate_bank.py
    if ($LASTEXITCODE -ne 0) { throw "Scenario validation failed ($LASTEXITCODE)." }
    & $python.Source -B build.py
    if ($LASTEXITCODE -ne 0) { throw "HTML build failed ($LASTEXITCODE)." }
    & git diff --exit-code -- index.html
    if ($LASTEXITCODE -ne 0) { throw 'Generated index.html is out of date; rebuild and commit it before packaging.' }

    $work = Join-Path $resolvedOutput 'work'
    $stage = Join-Path $resolvedOutput 'stage/ArchitecturePractice'
    New-Item -ItemType Directory -Path $resolvedOutput | Out-Null
    New-Item -ItemType Directory -Path $work, (Join-Path $resolvedOutput 'stage'), $stage | Out-Null

    & $python.Source -m pip install --disable-pip-version-check "pyinstaller==$pyinstallerVersion"
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller install failed ($LASTEXITCODE)." }

    $pyArgs = @(
        '-B', '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--console',
        '--name', 'ArchitecturePractice', '--distpath', (Join-Path $resolvedOutput 'pyinstaller-dist'),
        '--workpath', $work, '--specpath', $work,
        '--add-data', "$(Join-Path $repo 'index.html');.",
        '--add-data', "$(Join-Path $repo 'data/api.json');data",
        '--add-data', "$(Join-Path $repo 'data/integration.json');data",
        '--add-data', "$(Join-Path $repo 'data/design.json');data",
        '--add-data', "$(Join-Path $repo 'data/micro.json');data",
        '--hidden-import', 'requirements_backend', '--hidden-import', 'scenarios',
        (Join-Path $repo 'launcher.py')
    )
    & $python.Source @pyArgs
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed ($LASTEXITCODE)." }

    Copy-Item -LiteralPath (Join-Path $resolvedOutput 'pyinstaller-dist/ArchitecturePractice/ArchitecturePractice.exe') -Destination $stage
    Copy-Item -LiteralPath (Join-Path $resolvedOutput 'pyinstaller-dist/ArchitecturePractice/_internal') -Destination $stage -Recurse
    Copy-Item -LiteralPath (Join-Path $repo 'docs/WINDOWS.md') -Destination (Join-Path $stage 'README-Windows.md')
    $exeHash = (Get-FileHash -LiteralPath (Join-Path $stage 'ArchitecturePractice.exe') -Algorithm SHA256).Hash.ToLowerInvariant()
    "$exeHash  ArchitecturePractice.exe" | Set-Content -LiteralPath (Join-Path $stage 'SHA256SUMS.txt') -Encoding ascii

    $smoke = Join-Path $PSScriptRoot 'smoke-windows.ps1'
    & (Get-Command powershell.exe -ErrorAction Stop).Source -NoProfile -ExecutionPolicy Bypass -File $smoke -Executable (Join-Path $stage 'ArchitecturePractice.exe')
    if ($LASTEXITCODE -ne 0) { throw "Frozen executable smoke check failed ($LASTEXITCODE)." }

    @'
@echo off
cd /d "%~dp0"
start "Architecture Practice" ArchitecturePractice.exe
'@ | Set-Content -LiteralPath (Join-Path $stage 'Start.cmd') -Encoding ascii

    $archive = Join-Path $resolvedOutput 'ArchitecturePractice-Windows-x64.zip'
    Compress-Archive -LiteralPath $stage -DestinationPath $archive -CompressionLevel Optimal
    $zipHash = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
    "$zipHash  ArchitecturePractice-Windows-x64.zip" | Set-Content -LiteralPath "$archive.sha256" -Encoding ascii
    Write-Host "Windows package created: $archive"
}
finally { Pop-Location }
