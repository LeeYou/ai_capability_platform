param(
    [string]$MatrixConfigPath = (Join-Path $PSScriptRoot "..\config\delivery_acceptance_matrix.json"),
    [string]$DeliveryRoot = (Join-Path $PSScriptRoot "..\deploy\host_template"),
    [string]$BuildBinDir = (Join-Path $PSScriptRoot "..\build\bin\Release"),
    [string]$BaseUrl = "http://127.0.0.1:26000",
    [string]$AdminToken = "demo-admin-token",
    [int]$HealthTimeoutSeconds = 20,
    [string]$ArtifactsRoot = ""
)

$ErrorActionPreference = "Stop"

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

function Get-BoolValue {
    param(
        [object]$Value,
        [bool]$DefaultValue = $false
    )

    if ($null -eq $Value) {
        return $DefaultValue
    }

    return [System.Convert]::ToBoolean($Value)
}

function Get-IntValue {
    param(
        [object]$Value,
        [int]$DefaultValue
    )

    if ($null -eq $Value) {
        return $DefaultValue
    }

    return [System.Convert]::ToInt32($Value)
}

function Read-JsonFileIfExists {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return $null
    }

    return (Get-Content -Path $Path -Raw | ConvertFrom-Json)
}

function Resolve-FailureSummaryPath {
    param(
        [string]$ScenarioArtifactsRoot,
        [string]$DefaultFailureSummaryPath
    )

    if (Test-Path $DefaultFailureSummaryPath) {
        return $DefaultFailureSummaryPath
    }

    $candidate = Get-ChildItem -Path $ScenarioArtifactsRoot -Filter "acceptance_failure_summary.json" -Recurse -File -ErrorAction SilentlyContinue |
        Sort-Object -Property LastWriteTime -Descending |
        Select-Object -First 1

    if ($null -ne $candidate) {
        return $candidate.FullName
    }

    return $DefaultFailureSummaryPath
}

$resolvedMatrixConfigPath = [System.IO.Path]::GetFullPath($MatrixConfigPath)
$resolvedDeliveryRoot = [System.IO.Path]::GetFullPath($DeliveryRoot)
$resolvedBuildBinDir = [System.IO.Path]::GetFullPath($BuildBinDir)
$runAcceptanceScriptPath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "run_delivery_acceptance.ps1"))
$resolvedArtifactsRoot = Resolve-OptionalPath -Path $ArtifactsRoot -BaseDirectory $resolvedDeliveryRoot
if ([string]::IsNullOrWhiteSpace($resolvedArtifactsRoot)) {
    $resolvedArtifactsRoot = Join-Path $resolvedDeliveryRoot "logs\acceptance_matrix"
}

if (-not (Test-Path $resolvedMatrixConfigPath)) {
    throw ("matrix config not found: {0}" -f $resolvedMatrixConfigPath)
}

$matrixConfig = Get-Content -Path $resolvedMatrixConfigPath -Raw | ConvertFrom-Json
if ($null -eq $matrixConfig.scenarios -or $matrixConfig.scenarios.Count -le 0) {
    throw ("matrix config contains no scenarios: {0}" -f $resolvedMatrixConfigPath)
}

New-Item -ItemType Directory -Path $resolvedArtifactsRoot -Force | Out-Null
$matrixTimestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$matrixRunRoot = Join-Path $resolvedArtifactsRoot $matrixTimestamp
New-Item -ItemType Directory -Path $matrixRunRoot -Force | Out-Null

$results = New-Object System.Collections.ArrayList
$failedScenarios = New-Object System.Collections.Generic.List[string]

foreach ($scenario in $matrixConfig.scenarios) {
    $scenarioName = [string]$scenario.name
    if ([string]::IsNullOrWhiteSpace($scenarioName)) {
        throw "scenario.name is required in delivery acceptance matrix"
    }

    Write-Host ("[run_delivery_acceptance_matrix] scenario={0} begin" -f $scenarioName)
    $scenarioArtifactsRoot = Join-Path $matrixRunRoot $scenarioName
    New-Item -ItemType Directory -Path $scenarioArtifactsRoot -Force | Out-Null

    $arguments = @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $runAcceptanceScriptPath,
        "-ScenarioName", $scenarioName,
        "-DeliveryRoot", $resolvedDeliveryRoot,
        "-BuildBinDir", $resolvedBuildBinDir,
        "-BaseUrl", $(if ($null -ne $scenario.base_url -and -not [string]::IsNullOrWhiteSpace([string]$scenario.base_url)) { [string]$scenario.base_url } else { $BaseUrl }),
        "-AdminToken", $(if ($null -ne $scenario.admin_token -and -not [string]::IsNullOrWhiteSpace([string]$scenario.admin_token)) { [string]$scenario.admin_token } else { $AdminToken }),
        "-Mode", $(if ($null -ne $scenario.mode -and -not [string]::IsNullOrWhiteSpace([string]$scenario.mode)) { [string]$scenario.mode } else { "normal" }),
        "-RepeatCount", (Get-IntValue -Value $scenario.repeat_count -DefaultValue 1),
        "-HealthTimeoutSeconds", (Get-IntValue -Value $scenario.health_timeout_seconds -DefaultValue $HealthTimeoutSeconds),
        "-AcceptanceArtifactsRoot", $scenarioArtifactsRoot
    )

    if (Get-BoolValue -Value $scenario.prepare_delivery_root) {
        $arguments += "-PrepareDeliveryRoot"
    }
    if (Get-BoolValue -Value $scenario.clean_delivery_root) {
        $arguments += "-CleanDeliveryRoot"
    }
    if (Get-BoolValue -Value $scenario.require_models) {
        $arguments += "-RequireModels"
    }
    if (Get-BoolValue -Value $scenario.capture_diagnostics) {
        $arguments += "-CaptureDiagnostics"
    }
    if (Get-BoolValue -Value $scenario.allow_missing_license_path) {
        $arguments += "-AllowMissingLicensePath"
    }
    if ($null -ne $scenario.platform_config_path -and -not [string]::IsNullOrWhiteSpace([string]$scenario.platform_config_path)) {
        $arguments += @("-PlatformConfigPath", [string]$scenario.platform_config_path)
    }
    if ($null -ne $scenario.registry_path -and -not [string]::IsNullOrWhiteSpace([string]$scenario.registry_path)) {
        $arguments += @("-RegistryPath", [string]$scenario.registry_path)
    }
    if ($null -ne $scenario.license_path -and -not [string]::IsNullOrWhiteSpace([string]$scenario.license_path)) {
        $arguments += @("-LicensePath", [string]$scenario.license_path)
    }

    $status = "passed"
    $errorMessage = ""
    $failureCategory = ""
    $failureStep = ""
    $failureSuggestion = ""
    $expectedFailureCategory = $(if ($null -ne $scenario.expected_failure_category) { [string]$scenario.expected_failure_category } else { "" })
    $failureSummaryPath = Join-Path $scenarioArtifactsRoot "acceptance_failure_summary.json"
    try {
        & powershell @arguments
        if ($LASTEXITCODE -ne 0) {
            throw ("run_delivery_acceptance failed with exit code: {0}" -f $LASTEXITCODE)
        }
        Write-Host ("[run_delivery_acceptance_matrix] scenario={0} ok" -f $scenarioName)
    } catch {
        $status = "failed"
        $errorMessage = $_.Exception.Message
        $failureSummaryPath = Resolve-FailureSummaryPath -ScenarioArtifactsRoot $scenarioArtifactsRoot -DefaultFailureSummaryPath $failureSummaryPath
        $failureSummary = Read-JsonFileIfExists -Path $failureSummaryPath
        if ($null -ne $failureSummary) {
            $failureCategory = [string]$failureSummary.failure_category
            $failureStep = [string]$failureSummary.step
            $failureSuggestion = [string]$failureSummary.suggestion
        }

        if ((-not [string]::IsNullOrWhiteSpace($expectedFailureCategory)) -and ($failureCategory -eq $expectedFailureCategory)) {
            $status = "expected_failure"
            Write-Host ("[run_delivery_acceptance_matrix] scenario={0} expected failure category={1}" -f $scenarioName, $failureCategory)
        } else {
            $failedScenarios.Add($scenarioName) | Out-Null
            Write-Host ("[run_delivery_acceptance_matrix] scenario={0} failed step={1} category={2}: {3}" -f $scenarioName, $failureStep, $failureCategory, $errorMessage)
        }
    }

    [void]$results.Add([pscustomobject][ordered]@{
        scenario_name = $scenarioName
        status = $status
        mode = $(if ($null -ne $scenario.mode) { [string]$scenario.mode } else { "normal" })
        repeat_count = (Get-IntValue -Value $scenario.repeat_count -DefaultValue 1)
        artifacts_root = $scenarioArtifactsRoot
        failure_summary_path = $failureSummaryPath
        failure_category = $failureCategory
        failure_step = $failureStep
        failure_suggestion = $failureSuggestion
        expected_failure_category = $expectedFailureCategory
        error_message = $errorMessage
    })
}

$summary = @{
    matrix_config_path = $resolvedMatrixConfigPath
    matrix_run_root = $matrixRunRoot
    total_scenarios = $results.Count
    passed_scenarios = ($results | Where-Object { $_.status -eq "passed" }).Count
    expected_failed_scenarios = ($results | Where-Object { $_.status -eq "expected_failure" }).Count
    failed_scenarios = $failedScenarios.Count
    failed_scenario_names = @($failedScenarios)
    results = @($results)
}

$summary | ConvertTo-Json -Depth 20 | Set-Content -Path (Join-Path $matrixRunRoot "matrix_summary.json") -Encoding UTF8

if ($failedScenarios.Count -gt 0) {
    throw ("delivery acceptance matrix failed: {0}" -f ($failedScenarios -join ", "))
}

Write-Host ("[run_delivery_acceptance_matrix] matrix ok: {0}" -f $matrixRunRoot)
