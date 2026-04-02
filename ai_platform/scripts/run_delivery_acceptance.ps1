param(
    [string]$DeliveryRoot = (Join-Path $PSScriptRoot "..\deploy\host_template"),
    [string]$BuildBinDir = (Join-Path $PSScriptRoot "..\build\bin\Release"),
    [string]$BaseUrl = "http://127.0.0.1:26000",
    [string]$AdminToken = "demo-admin-token",
    [string]$ScenarioName = "default",
    [string]$Mode = "normal",
    [int]$RepeatCount = 1,
    [int]$HealthTimeoutSeconds = 20,
    [string]$PlatformConfigPath = "",
    [string]$RegistryPath = "",
    [string]$LicensePath = "",
    [string]$AcceptanceArtifactsRoot = "",
    [switch]$PrepareDeliveryRoot,
    [switch]$CleanDeliveryRoot,
    [switch]$RequireModels,
    [switch]$AllowMissingLicensePath,
    [switch]$CaptureDiagnostics
)

$ErrorActionPreference = "Stop"
$currentStepName = "initialize"

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Action
    )

    $script:currentStepName = $Name
    Write-Host ("[run_delivery_acceptance] step={0} begin" -f $Name)
    & $Action
    Write-Host ("[run_delivery_acceptance] step={0} ok" -f $Name)
}

function Invoke-JsonGet {
    param([string]$Url)

    $response = Invoke-WebRequest -UseBasicParsing -Method GET -Uri $Url
    if (-not $response.Content) {
        throw ("empty response: {0}" -f $Url)
    }
    return $response.Content | ConvertFrom-Json
}

function Wait-PlatformHealth {
    param(
        [string]$Url,
        [int]$TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $health = Invoke-JsonGet -Url "$Url/api/v1/health"
            if ($health.code -eq 0) {
                return
            }
        } catch {
        }
        Start-Sleep -Milliseconds 500
    }

    throw ("platform health check did not become ready within {0} seconds: {1}/api/v1/health" -f $TimeoutSeconds, $Url)
}

function Assert-PathExists {
    param(
        [string]$Path,
        [string]$Message
    )

    if (-not (Test-Path $Path)) {
        throw $Message
    }
}

function Resolve-FailureCategory {
    param(
        [string]$Message,
        [string]$CurrentMode,
        [string]$CurrentStepName,
        [bool]$CurrentAllowMissingLicensePath
    )

    $category = Get-FailureCategory -Message $Message
    if (($CurrentStepName -eq "run_smoke") -and ($CurrentMode -eq "license_invalid") -and $CurrentAllowMissingLicensePath) {
        if ($Message -match "run_platform_smoke failed with exit code") {
            return "license_invalid"
        }
        if ($Message -match "platform health check did not become ready") {
            return "license_invalid"
        }
    }

    return $category
}

function Get-ManifestValue {
    param(
        [string]$ManifestPath,
        [string]$Key
    )

    foreach ($rawLine in (Get-Content -Path $ManifestPath)) {
        $line = $rawLine.Trim()
        if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) {
            continue
        }

        $delimiterIndex = $line.IndexOf(':')
        if ($delimiterIndex -lt 1) {
            continue
        }

        $currentKey = $line.Substring(0, $delimiterIndex).Trim()
        if ($currentKey -ne $Key) {
            continue
        }

        $value = $line.Substring($delimiterIndex + 1).Trim()
        if ($value.Length -ge 2) {
            if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
                return $value.Substring(1, $value.Length - 2)
            }
        }

        return $value
    }

    return ""
}

function Assert-MinimalModelPackage {
    param(
        [string]$CapabilityId,
        [string]$ModelDirectory
    )

    Assert-PathExists -Path $ModelDirectory -Message ("required model directory not found: {0}" -f $ModelDirectory)

    $manifestPath = Join-Path $ModelDirectory "manifest.yaml"
    $checksumPath = Join-Path $ModelDirectory "checksum.sha256"
    Assert-PathExists -Path $manifestPath -Message ("required model package manifest missing: {0}" -f $manifestPath)
    Assert-PathExists -Path $checksumPath -Message ("required model package checksum missing: {0}" -f $checksumPath)

    $manifestCapabilityId = Get-ManifestValue -ManifestPath $manifestPath -Key "capability_id"
    if ([string]::IsNullOrWhiteSpace($manifestCapabilityId)) {
        throw ("required model package capability_id missing: {0}" -f $manifestPath)
    }
    if ($manifestCapabilityId -ne $CapabilityId) {
        throw ("required model package capability_id mismatch for {0}: {1}" -f $CapabilityId, $manifestCapabilityId)
    }

    $modelFile = Get-ManifestValue -ManifestPath $manifestPath -Key "model_file"
    if ([string]::IsNullOrWhiteSpace($modelFile)) {
        throw ("required model package model_file missing: {0}" -f $manifestPath)
    }

    $modelFilePath = Join-Path $ModelDirectory $modelFile
    Assert-PathExists -Path $modelFilePath -Message ("required model package model file missing: {0}" -f $modelFilePath)
}

function Resolve-OptionalPath {
    param(
        [string]$Path,
        [string]$BaseDirectory
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return ""
    }

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }

    return [System.IO.Path]::GetFullPath((Join-Path $BaseDirectory $Path))
}

function Convert-ToSafePathSegment {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return "default"
    }

    $invalidChars = [System.IO.Path]::GetInvalidFileNameChars()
    $builder = New-Object System.Text.StringBuilder
    foreach ($char in $Value.ToCharArray()) {
        if ($invalidChars -contains $char) {
            [void]$builder.Append('_')
        } elseif ([char]::IsWhiteSpace($char)) {
            [void]$builder.Append('_')
        } else {
            [void]$builder.Append($char)
        }
    }

    return $builder.ToString()
}

function Get-FailureCategory {
    param([string]$Message)

    if ($Message -match "delivery server executable not found") {
        return "delivery_artifact_missing"
    }
    if ($Message -match "delivery registry not found" -or $Message -match "validate_plugins_registry failed") {
        return "registry_invalid"
    }
    if ($Message -match "delivery platform config not found") {
        return "platform_config_missing"
    }
    if ($Message -match "delivery license file not found" -or $Message -match "license invalid") {
        return "license_invalid"
    }
    if ($Message -match "required model directory not found" -or $Message -match "required model package" -or $Message -match "manifest.yaml missing" -or $Message -match "checksum.sha256 missing") {
        return "model_missing"
    }
    if ($Message -match "platform health check did not become ready" -or $Message -match "failed to start server" -or $Message -match "failed to start delivery server") {
        return "server_startup_failed"
    }
    if ($Message -match "run_platform_smoke failed" -or $Message -match "api smoke test failed") {
        return "smoke_failed"
    }
    if ($Message -match "empty response:" -or $Message -match "request failed:") {
        return "diagnostics_capture_failed"
    }
    return "unknown_failure"
}

function Get-FailureSuggestion {
    param(
        [string]$Category,
        [string]$Message
    )

    switch ($Category) {
        "delivery_artifact_missing" { return "Check build/bin/Release artifacts and rerun prepare_delivery_host_template.ps1." }
        "registry_invalid" { return "Check config/plugins_registry.txt format and paths, then rerun validate_plugins_registry.ps1." }
        "platform_config_missing" { return "Check config/platform.yaml and verify AI_PLATFORM_CONFIG_PATH points to the intended file." }
        "license_invalid" { return "Check license/license.dat for the current scenario, or use AllowMissingLicensePath for invalid-license scenarios." }
        "model_missing" { return "Check models/<capability_id>/ directories or disable RequireModels for baseline validation without model completeness checks." }
        "server_startup_failed" { return "Check ai_platform_server startup output, runtime_audit.log, audit.log, and runtime diagnostics if available." }
        "smoke_failed" { return "Check run_platform_smoke and api_smoke_test output together with acceptance_summary.json and evidence JSON files." }
        "diagnostics_capture_failed" { return "Check service reachability, BaseUrl, port, license status, and runtime/diagnostics endpoint availability." }
        default { return "Check the error message, acceptance_failure_summary.json, runtime_audit.log, and audit.log, then rerun after fixing the failing step." }
    }
}

$resolvedDeliveryRoot = [System.IO.Path]::GetFullPath($DeliveryRoot)
$resolvedBuildBinDir = [System.IO.Path]::GetFullPath($BuildBinDir)
$prepareScriptPath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "prepare_delivery_host_template.ps1"))
$validateRegistryScriptPath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "validate_plugins_registry.ps1"))
$runSmokeScriptPath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "run_platform_smoke.ps1"))
$serverExePath = Join-Path $resolvedDeliveryRoot "ai_platform_server.exe"
$registryPath = Resolve-OptionalPath -Path $RegistryPath -BaseDirectory $resolvedDeliveryRoot
if ([string]::IsNullOrWhiteSpace($registryPath)) {
    $registryPath = Join-Path $resolvedDeliveryRoot "config\plugins_registry.txt"
}
$platformConfigPath = Resolve-OptionalPath -Path $PlatformConfigPath -BaseDirectory $resolvedDeliveryRoot
if ([string]::IsNullOrWhiteSpace($platformConfigPath)) {
    $platformConfigPath = Join-Path $resolvedDeliveryRoot "config\platform.yaml"
}
$licensePath = Resolve-OptionalPath -Path $LicensePath -BaseDirectory $resolvedDeliveryRoot
if ([string]::IsNullOrWhiteSpace($licensePath)) {
    $licensePath = Join-Path $resolvedDeliveryRoot "license\license.dat"
}
$evidenceRoot = Resolve-OptionalPath -Path $AcceptanceArtifactsRoot -BaseDirectory $resolvedDeliveryRoot
if ([string]::IsNullOrWhiteSpace($evidenceRoot)) {
    $evidenceRoot = Join-Path $resolvedDeliveryRoot "logs\acceptance"
}
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$scenarioPathSegment = Convert-ToSafePathSegment -Value $ScenarioName
$runEvidenceRoot = Join-Path $evidenceRoot ("{0}_{1}" -f $scenarioPathSegment, $timestamp)
$startedProcess = $null
$previousLicensePath = $env:AI_PLATFORM_LICENSE_PATH
$previousRegistryPath = $env:AI_PLATFORM_PLUGINS_REGISTRY_PATH
$previousConfigPath = $env:AI_PLATFORM_CONFIG_PATH
$previousRuntimeAuditLogPath = $env:AI_PLATFORM_RUNTIME_AUDIT_LOG_PATH
$previousLicenseAuditLogPath = $env:AI_PLATFORM_LICENSE_AUDIT_LOG_PATH
$acceptanceSummaryPath = Join-Path $runEvidenceRoot "acceptance_summary.json"
$failureSummaryPath = Join-Path $runEvidenceRoot "acceptance_failure_summary.json"

try {
    if ($PrepareDeliveryRoot) {
        Invoke-Step -Name "prepare_delivery_root" -Action {
            $arguments = @(
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File", $prepareScriptPath,
                "-BuildBinDir", $resolvedBuildBinDir,
                "-TargetRoot", $resolvedDeliveryRoot
            )
            if ($CleanDeliveryRoot) {
                $arguments += "-CleanTarget"
            }
            & powershell @arguments
            if ($LASTEXITCODE -ne 0) {
                throw ("prepare_delivery_host_template failed with exit code: {0}" -f $LASTEXITCODE)
            }
        }
    }

    Invoke-Step -Name "check_delivery_files" -Action {
        Assert-PathExists -Path $serverExePath -Message ("delivery server executable not found: {0}" -f $serverExePath)
        Assert-PathExists -Path $registryPath -Message ("delivery registry not found: {0}" -f $registryPath)
        Assert-PathExists -Path $platformConfigPath -Message ("delivery platform config not found: {0}" -f $platformConfigPath)
        if ((-not $AllowMissingLicensePath) -or (Test-Path $licensePath)) {
            Assert-PathExists -Path $licensePath -Message ("delivery license file not found: {0}`nprepare a valid license or rerun after prepare_delivery_host_template copies demo license" -f $licensePath)
        }
        if ($RequireModels) {
            $modelRoot = Join-Path $resolvedDeliveryRoot "models"
            $modelDirectories = @("face_detect", "liveness_action", "idcard_detect", "doc_classify", "seal_detect")
            foreach ($modelDirectory in $modelDirectories) {
                $modelPath = Join-Path $modelRoot $modelDirectory
                Assert-MinimalModelPackage -CapabilityId $modelDirectory -ModelDirectory $modelPath
            }
        }
        New-Item -ItemType Directory -Path $runEvidenceRoot -Force | Out-Null
    }

    Invoke-Step -Name "validate_registry" -Action {
        $arguments = @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", $validateRegistryScriptPath,
            "-RegistryPath", $registryPath,
            "-DeliveryRoot", $resolvedDeliveryRoot
        )
        if ($RequireModels) {
            $arguments += "-RequireFilesExist"
        }
        & powershell @arguments
        if ($LASTEXITCODE -ne 0) {
            throw ("validate_plugins_registry failed with exit code: {0}" -f $LASTEXITCODE)
        }
    }

    $env:AI_PLATFORM_CONFIG_PATH = $platformConfigPath
    $env:AI_PLATFORM_LICENSE_PATH = $licensePath
    $env:AI_PLATFORM_PLUGINS_REGISTRY_PATH = $registryPath
    $env:AI_PLATFORM_RUNTIME_AUDIT_LOG_PATH = (Join-Path $resolvedDeliveryRoot "logs\runtime_audit.log")
    $env:AI_PLATFORM_LICENSE_AUDIT_LOG_PATH = (Join-Path $resolvedDeliveryRoot "logs\audit.log")

    Invoke-Step -Name "run_smoke" -Action {
        $arguments = @(
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", $runSmokeScriptPath,
            "-BaseUrl", $BaseUrl,
            "-Mode", $Mode,
            "-AdminToken", $AdminToken,
            "-RepeatCount", $RepeatCount,
            "-HealthTimeoutSeconds", $HealthTimeoutSeconds,
            "-ServerExePath", $serverExePath,
            "-StartServer"
        )
        & powershell @arguments
        if ($LASTEXITCODE -ne 0) {
            throw ("run_platform_smoke failed with exit code: {0}" -f $LASTEXITCODE)
        }
    }

    if ($CaptureDiagnostics) {
        Invoke-Step -Name "capture_diagnostics" -Action {
            $script:startedProcess = $null
            try {
                $script:startedProcess = Start-Process -FilePath $serverExePath -WorkingDirectory $resolvedDeliveryRoot -PassThru
            } catch {
                throw ("failed to start delivery server for diagnostics capture: {0}" -f $_.Exception.Message)
            }

            Wait-PlatformHealth -Url $BaseUrl -TimeoutSeconds $HealthTimeoutSeconds

            $health = Invoke-JsonGet -Url "$BaseUrl/api/v1/health"
            $licenseStatus = Invoke-JsonGet -Url "$BaseUrl/api/v1/license/status"
            $runtimeStatus = Invoke-JsonGet -Url "$BaseUrl/api/v1/runtime/status"
            $runtimeDiagnostics = Invoke-JsonGet -Url "$BaseUrl/api/v1/runtime/diagnostics"

            $health | ConvertTo-Json -Depth 20 | Set-Content -Path (Join-Path $runEvidenceRoot "health.json") -Encoding UTF8
            $licenseStatus | ConvertTo-Json -Depth 20 | Set-Content -Path (Join-Path $runEvidenceRoot "license_status.json") -Encoding UTF8
            $runtimeStatus | ConvertTo-Json -Depth 20 | Set-Content -Path (Join-Path $runEvidenceRoot "runtime_status.json") -Encoding UTF8
            $runtimeDiagnostics | ConvertTo-Json -Depth 20 | Set-Content -Path (Join-Path $runEvidenceRoot "runtime_diagnostics.json") -Encoding UTF8

            $summary = [ordered]@{
                scenario_name = $ScenarioName
                accepted_at = (Get-Date).ToString("s")
                base_url = $BaseUrl
                mode = $Mode
                repeat_count = $RepeatCount
                delivery_root = $resolvedDeliveryRoot
                registry_path = $registryPath
                license_path = $licensePath
                capability_count = $runtimeDiagnostics.data.runtime.capability_count
                plugin_registry_opened = $runtimeDiagnostics.data.runtime.plugin_load.registry_opened
                plugin_loaded_count = $runtimeDiagnostics.data.runtime.plugin_load.loaded_count
                plugin_failure_count = $runtimeDiagnostics.data.runtime.plugin_load.failures.Count
                license_valid = $runtimeDiagnostics.data.license.valid
                health_status = $health.message
            }
            $summary | ConvertTo-Json -Depth 10 | Set-Content -Path (Join-Path $runEvidenceRoot "acceptance_summary.json") -Encoding UTF8
        }
    }

    Write-Host ("[run_delivery_acceptance] scenario={0} acceptance ok: {1}" -f $ScenarioName, $resolvedDeliveryRoot)
    if ($CaptureDiagnostics) {
        Write-Host ("[run_delivery_acceptance] evidence_root={0}" -f $runEvidenceRoot)
    }
} catch {
    New-Item -ItemType Directory -Path $runEvidenceRoot -Force | Out-Null
    $failureMessage = $_.Exception.Message
    $failureCategory = Resolve-FailureCategory -Message $failureMessage -CurrentMode $Mode -CurrentStepName $currentStepName -CurrentAllowMissingLicensePath ([bool]$AllowMissingLicensePath)
    $failureSuggestion = Get-FailureSuggestion -Category $failureCategory -Message $failureMessage
    $failureSummary = [ordered]@{
        scenario_name = $ScenarioName
        failed_at = (Get-Date).ToString("s")
        step = $currentStepName
        failure_category = $failureCategory
        message = $failureMessage
        suggestion = $failureSuggestion
        evidence_root = $runEvidenceRoot
        acceptance_summary_path = $acceptanceSummaryPath
        runtime_audit_log_path = (Join-Path $resolvedDeliveryRoot "logs\runtime_audit.log")
        license_audit_log_path = (Join-Path $resolvedDeliveryRoot "logs\audit.log")
        base_url = $BaseUrl
        mode = $Mode
        repeat_count = $RepeatCount
    }
    $failureSummary | ConvertTo-Json -Depth 10 | Set-Content -Path $failureSummaryPath -Encoding UTF8
    Write-Host ("[run_delivery_acceptance] scenario={0} failed at step={1} category={2}" -f $ScenarioName, $currentStepName, $failureCategory)
    Write-Host ("[run_delivery_acceptance] failure_summary={0}" -f $failureSummaryPath)
    Write-Host ("[run_delivery_acceptance] suggestion={0}" -f $failureSuggestion)
    throw
} finally {
    if ($null -ne $startedProcess) {
        try {
            if (-not $startedProcess.HasExited) {
                Stop-Process -Id $startedProcess.Id -Force
            }
        } catch {
        }
    }

    $env:AI_PLATFORM_LICENSE_PATH = $previousLicensePath
    $env:AI_PLATFORM_PLUGINS_REGISTRY_PATH = $previousRegistryPath
    $env:AI_PLATFORM_CONFIG_PATH = $previousConfigPath
    $env:AI_PLATFORM_RUNTIME_AUDIT_LOG_PATH = $previousRuntimeAuditLogPath
    $env:AI_PLATFORM_LICENSE_AUDIT_LOG_PATH = $previousLicenseAuditLogPath
}
