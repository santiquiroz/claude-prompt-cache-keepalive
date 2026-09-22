param(
    [Parameter(Mandatory)][double]$Minutes,
    [string]$Label = 'tick',
    [string]$StateDir = (Join-Path $HOME '.claude/keepalive/default')
)

$ErrorActionPreference = 'Stop'
$pollSeconds = 60
$stopFile = Join-Path $StateDir 'stop'
New-Item -ItemType Directory -Force -Path $StateDir | Out-Null

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
Set-WakeLock $true
try {
    while ((Get-Date) -lt $deadline) {
        if (Test-Path $stopFile) { "KEEPALIVE_STOPPED $Label"; exit 0 }
        $left = ($deadline - (Get-Date)).TotalSeconds
        Start-Sleep -Seconds ([math]::Max(1, [math]::Min($pollSeconds, $left)))
    }
}
finally {
    Set-WakeLock $false
}
if (Test-Path $stopFile) { "KEEPALIVE_STOPPED $Label"; exit 0 }
"KEEPALIVE_TICK $Label $((Get-Date).ToString('s')) - reply with one short line, no tools"
