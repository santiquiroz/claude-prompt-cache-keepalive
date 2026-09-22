param(
    [Parameter(Mandatory)][double]$Minutes,
    [string]$Label = 'tick',
    [string]$StateDir = (Join-Path $HOME '.claude/keepalive/default')
)

$ErrorActionPreference = 'Stop'
$pollSeconds = 60
$stopFile = Join-Path $StateDir 'stop'
$rungDir = Join-Path $StateDir 'rungs'
New-Item -ItemType Directory -Force -Path $rungDir | Out-Null
$aliveFile = Join-Path $rungDir (($Label -replace '[^0-9A-Za-z]', '-') + '.alive')

function Set-WakeLock([bool]$On) {
    if (-not ('KeepAlive.Power' -as [type])) {
        Add-Type -Namespace KeepAlive -Name Power -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint esFlags);'
    }
    $continuous = [uint32]'0x80000000'
    $systemRequired = [uint32]'0x00000001'
    $flags = if ($On) { $continuous -bor $systemRequired } else { $continuous }
    [KeepAlive.Power]::SetThreadExecutionState($flags) | Out-Null
}

$deadline = (Get-Date).AddMinutes($Minutes)

function Write-Heartbeat {
    Set-Content -LiteralPath $aliveFile -Value ("{0}|pid {1}|vence {2}" -f $Label, $PID, $deadline.ToString('s')) -Encoding utf8
}

Set-WakeLock $true
Write-Heartbeat
try {
    while ((Get-Date) -lt $deadline) {
        if (Test-Path $stopFile) { "KEEPALIVE_STOPPED $Label"; exit 0 }
        Write-Heartbeat
        $left = ($deadline - (Get-Date)).TotalSeconds
        Start-Sleep -Seconds ([math]::Max(1, [math]::Min($pollSeconds, $left)))
    }
}
finally {
    Set-WakeLock $false
    # A stale .alive file is the watchdog's only evidence that a rung was killed, so only a clean exit clears it.
    Remove-Item -LiteralPath $aliveFile -Force -ErrorAction SilentlyContinue
}
if (Test-Path $stopFile) { "KEEPALIVE_STOPPED $Label"; exit 0 }
"KEEPALIVE_TICK $Label $((Get-Date).ToString('s')) - reply with one short line, no tools"
