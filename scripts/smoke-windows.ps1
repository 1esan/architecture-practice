[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Executable,
    [int]$Port = 0
)

$ErrorActionPreference = 'Stop'
$exePath = (Resolve-Path -LiteralPath $Executable).Path

function Get-FreeLoopbackPort {
    $probe = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, 0)
    try {
        $probe.Start()
        return ([Net.IPEndPoint]$probe.LocalEndpoint).Port
    }
    finally { $probe.Stop() }
}

function Wait-ForApplication([int]$ListenPort, [int]$TimeoutSeconds = 15) {
    $baseUrl = "http://127.0.0.1:$ListenPort"
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-RestMethod -Uri "$baseUrl/api/health" -TimeoutSec 1
            if ($response.app -eq 'architecture-practice') { return $baseUrl }
        }
        catch { Start-Sleep -Milliseconds 200 }
        Start-Sleep -Milliseconds 100
    }
    throw "Application did not become healthy on port $ListenPort."
}

function Test-ServedPage([string]$BaseUrl) {
    $page = Invoke-WebRequest -UseBasicParsing -Uri $BaseUrl -TimeoutSec 10
    if ($page.StatusCode -ne 200 -or $page.Content -notmatch 'Практика') {
        throw 'The UTF-8 HTML page was not served as expected.'
    }
}

function Find-OwnedServerProcess([int]$ParentId, [datetime]$StartedAt) {
    Get-CimInstance Win32_Process -Filter "ParentProcessId = $ParentId" |
        Where-Object {
            $_.ExecutablePath -eq $exePath -and $_.CreationDate -ge $StartedAt
        } | Select-Object -First 1
}

function Stop-OwnedServerProcess($ServerProcess) {
    if (-not $ServerProcess) { return }
    $current = Get-CimInstance Win32_Process -Filter "ProcessId = $($ServerProcess.ProcessId)" -ErrorAction SilentlyContinue
    if ($current -and $current.ExecutablePath -eq $exePath -and
        $current.ParentProcessId -eq $ServerProcess.ParentProcessId -and
        $current.CreationDate -eq $ServerProcess.CreationDate) {
        Stop-Process -Id $current.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

if ($Port -eq 0) { $Port = Get-FreeLoopbackPort }
$portForNormalLaunch = Get-FreeLoopbackPort
while ($portForNormalLaunch -eq $Port) { $portForNormalLaunch = Get-FreeLoopbackPort }
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("arch-practice-smoke-" + [guid]::NewGuid().ToString('N'))
$stateServe = Join-Path $tempRoot 'serve-state'
$stateLaunch = Join-Path $tempRoot 'launch-state'
New-Item -ItemType Directory -Path $stateServe, $stateLaunch | Out-Null

$oldUtf8 = $env:PYTHONUTF8
$oldStateDir = $env:ARCH_TRAINER_STATE_DIR
$oldPort = $env:ARCH_TRAINER_PORT
$serveProcess = $null
$launchProcess = $null
$launchChild = $null
try {
    $env:PYTHONUTF8 = '1'
    $env:ARCH_TRAINER_STATE_DIR = $stateServe
    $env:ARCH_TRAINER_PORT = [string]$Port
    $serveProcess = Start-Process -FilePath $exePath -ArgumentList @('--serve', '--port', [string]$Port) `
        -PassThru -WorkingDirectory (Split-Path $exePath)
    $base = Wait-ForApplication -ListenPort $Port
    Test-ServedPage -BaseUrl $base

    $stateValue = @{
        version = 1
        attempts = @()
        drafts = @{}
        plans = @{}
        settings = @{ goal = 1; mode = 'quick'; theme = 'light' }
    }
    $payload = @{ revision = 0; state = $stateValue } | ConvertTo-Json -Depth 8 -Compress
    $headers = @{ 'X-Trainer' = '1'; Origin = $base }
    $saved = Invoke-RestMethod -Uri "$base/api/state" -Method Post -Headers $headers `
        -ContentType 'application/json; charset=utf-8' `
        -Body ([Text.Encoding]::UTF8.GetBytes($payload))
    if ($saved.revision -ne 1) { throw 'State save endpoint did not return revision 1.' }
    if (-not (Get-ChildItem -LiteralPath $stateServe -Filter '*.sqlite3' -File)) {
        throw 'The app did not create SQLite state in its configured user data directory.'
    }
    Stop-Process -Id $serveProcess.Id -Force
    $serveProcess = $null

    # Exercise the actual double-click path: the foreground launcher should return
    # successfully while its own child server remains healthy on the second port.
    $env:ARCH_TRAINER_STATE_DIR = $stateLaunch
    $env:ARCH_TRAINER_PORT = [string]$portForNormalLaunch
    $launchStarted = Get-Date
    $launchProcess = Start-Process -FilePath $exePath -ArgumentList @('--no-open', '--port', [string]$portForNormalLaunch) `
        -PassThru -WorkingDirectory (Split-Path $exePath)
    if (-not $launchProcess.WaitForExit(20000)) { throw 'Normal launcher did not return after starting its server.' }
    if ($launchProcess.ExitCode -ne 0) { throw "Normal launcher exited with code $($launchProcess.ExitCode)." }

    $launchChild = Find-OwnedServerProcess -ParentId $launchProcess.Id -StartedAt $launchStarted
    if (-not $launchChild) { throw 'Could not identify the server child created by the normal launcher.' }
    $launchBase = Wait-ForApplication -ListenPort $portForNormalLaunch
    Test-ServedPage -BaseUrl $launchBase
    if (-not (Get-ChildItem -LiteralPath $stateLaunch -Filter '*.sqlite3' -File)) {
        throw 'Normal launcher did not persist state under the configured user data directory.'
    }
    Write-Host 'Windows smoke check passed: server mode and normal --no-open launch.'
}
finally {
    if ($serveProcess -and -not $serveProcess.HasExited) { Stop-Process -Id $serveProcess.Id -Force }
    if (-not $launchChild -and $launchProcess) {
        $launchChild = Find-OwnedServerProcess -ParentId $launchProcess.Id -StartedAt $launchStarted
    }
    Stop-OwnedServerProcess -ServerProcess $launchChild
    if ($oldUtf8) { $env:PYTHONUTF8 = $oldUtf8 } else { Remove-Item Env:PYTHONUTF8 -ErrorAction SilentlyContinue }
    if ($oldStateDir) { $env:ARCH_TRAINER_STATE_DIR = $oldStateDir } else { Remove-Item Env:ARCH_TRAINER_STATE_DIR -ErrorAction SilentlyContinue }
    if ($oldPort) { $env:ARCH_TRAINER_PORT = $oldPort } else { Remove-Item Env:ARCH_TRAINER_PORT -ErrorAction SilentlyContinue }
    Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
}
