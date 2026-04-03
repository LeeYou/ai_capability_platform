param(
    [string]$BaseUrl = "http://127.0.0.1:26000",
    [string]$Mode = "normal",
    [string]$AdminToken = "demo-admin-token",
    [int]$AutoReloadWaitSeconds = 0,
    [int]$RepeatCount = 1,
    [int]$HealthTimeoutSeconds = 20,
    [string]$ServerExePath = (Join-Path $PSScriptRoot "..\build\bin\Release\ai_platform_server.exe"),
    [switch]$StartServer
)

$ErrorActionPreference = "Stop"

function Test-PlatformHealth {
    param(
        [string]$Url
    )

    try {
        $response = Invoke-WebRequest -UseBasicParsing -Method GET -Uri "$Url/api/v1/health"
        if (-not $response.Content) {
            return $false
        }
        $body = $response.Content | ConvertFrom-Json
        return $body.code -eq 0
    } catch {
        return $false
    }
}

function Wait-PlatformHealth {
    param(
        [string]$Url,
        [int]$TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-PlatformHealth -Url $Url) {
            return
        }
        Start-Sleep -Milliseconds 500
    }

    throw ("platform health check did not become ready within {0} seconds: {1}/api/v1/health" -f $TimeoutSeconds, $Url)
}

function Invoke-SmokeIteration {
    param(
        [string]$ResolvedServerExePath,
        [string]$SmokeScriptPath,
        [string]$Url,
        [string]$CurrentMode,
        [string]$CurrentAdminToken,
        [int]$CurrentAutoReloadWaitSeconds,
        [int]$CurrentHealthTimeoutSeconds,
        [bool]$ShouldStartServer
    )

    $iterationProcess = $null
    try {
        if (-not (Test-PlatformHealth -Url $Url)) {
            if (-not $ShouldStartServer) {
                throw ("platform service is unreachable: {0}`nstart ai_platform_server manually, or rerun with -StartServer" -f $Url)
            }

            if (-not (Test-Path $ResolvedServerExePath)) {
                throw ("server executable not found: {0}" -f $ResolvedServerExePath)
            }

            Write-Host ("[run_platform_smoke] starting server: {0}" -f $ResolvedServerExePath)
            try {
                $iterationProcess = Start-Process -FilePath $ResolvedServerExePath -WorkingDirectory ([System.IO.Path]::GetDirectoryName($ResolvedServerExePath)) -PassThru
            } catch {
                throw ("failed to start server: {0}`noriginal error: {1}" -f $ResolvedServerExePath, $_.Exception.Message)
            }

            Wait-PlatformHealth -Url $Url -TimeoutSeconds $CurrentHealthTimeoutSeconds
        } else {
            Write-Host ("[run_platform_smoke] using existing reachable service: {0}" -f $Url)
        }

        $command = @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", $SmokeScriptPath,
            "-BaseUrl", $Url,
            "-Mode", $CurrentMode,
            "-AdminToken", $CurrentAdminToken,
            "-AutoReloadWaitSeconds", $CurrentAutoReloadWaitSeconds,
            "-RepeatCount", 1
        )

        & powershell @command
        if ($LASTEXITCODE -ne 0) {
            throw ("api smoke test failed with exit code: {0}" -f $LASTEXITCODE)
        }
    } finally {
        if ($null -ne $iterationProcess) {
            try {
                if (-not $iterationProcess.HasExited) {
                    Stop-Process -Id $iterationProcess.Id -Force
                }
            } catch {
            }
        }
    }
}

$startedProcess = $null
$resolvedServerExePath = [System.IO.Path]::GetFullPath($ServerExePath)
$smokeScriptPath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "api_smoke_test.ps1"))

if ($StartServer -and $RepeatCount -gt 1) {
    for ($iteration = 1; $iteration -le $RepeatCount; $iteration++) {
        Write-Host ("[run_platform_smoke] isolated iteration {0}/{1}" -f $iteration, $RepeatCount)
        Invoke-SmokeIteration -ResolvedServerExePath $resolvedServerExePath -SmokeScriptPath $smokeScriptPath -Url $BaseUrl -CurrentMode $Mode -CurrentAdminToken $AdminToken -CurrentAutoReloadWaitSeconds $AutoReloadWaitSeconds -CurrentHealthTimeoutSeconds $HealthTimeoutSeconds -ShouldStartServer $true
    }
    return
}

try {
    Invoke-SmokeIteration -ResolvedServerExePath $resolvedServerExePath -SmokeScriptPath $smokeScriptPath -Url $BaseUrl -CurrentMode $Mode -CurrentAdminToken $AdminToken -CurrentAutoReloadWaitSeconds $AutoReloadWaitSeconds -CurrentHealthTimeoutSeconds $HealthTimeoutSeconds -ShouldStartServer ([bool]$StartServer)
} finally {
    if ($null -ne $startedProcess) {
        try {
            if (-not $startedProcess.HasExited) {
                Stop-Process -Id $startedProcess.Id -Force
            }
        } catch {
        }
    }
}
