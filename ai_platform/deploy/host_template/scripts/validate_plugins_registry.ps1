param(
    [string]$RegistryPath = (Join-Path $PSScriptRoot "..\config\plugins_registry.txt"),
    [string]$DeliveryRoot = (Join-Path $PSScriptRoot ".."),
    [switch]$RequireFilesExist
)

$ErrorActionPreference = "Stop"

function Resolve-RegistryEntryPath {
    param(
        [string]$BaseDirectory,
        [string]$ConfiguredPath
    )

    if ([string]::IsNullOrWhiteSpace($ConfiguredPath)) {
        return ""
    }

    if ([System.IO.Path]::IsPathRooted($ConfiguredPath)) {
        return $ConfiguredPath
    }

    return [System.IO.Path]::GetFullPath((Join-Path $BaseDirectory $ConfiguredPath))
}

function Get-ManifestValue {
    param(
        [string]$ManifestPath,
        [string]$Key
    )

    if (-not (Test-Path $ManifestPath)) {
        return ""
    }

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

function Test-MinimalModelPackage {
    param(
        [string]$CapabilityId,
        [string]$ModelDir
    )

    if (-not (Test-Path $ModelDir)) {
        throw ("model dir not found for capability {0}: {1}" -f $CapabilityId, $ModelDir)
    }

    $manifestPath = Join-Path $ModelDir "manifest.yaml"
    $checksumPath = Join-Path $ModelDir "checksum.sha256"

    if (-not (Test-Path $manifestPath)) {
        throw ("manifest.yaml missing for capability {0}: {1}" -f $CapabilityId, $manifestPath)
    }
    if (-not (Test-Path $checksumPath)) {
        throw ("checksum.sha256 missing for capability {0}: {1}" -f $CapabilityId, $checksumPath)
    }

    $manifestCapabilityId = Get-ManifestValue -ManifestPath $manifestPath -Key "capability_id"
    if ([string]::IsNullOrWhiteSpace($manifestCapabilityId)) {
        throw ("manifest capability_id missing for capability {0}: {1}" -f $CapabilityId, $manifestPath)
    }
    if ($manifestCapabilityId -ne $CapabilityId) {
        throw ("manifest capability_id mismatch for capability {0}: {1}" -f $CapabilityId, $manifestCapabilityId)
    }

    $modelFile = Get-ManifestValue -ManifestPath $manifestPath -Key "model_file"
    if ([string]::IsNullOrWhiteSpace($modelFile)) {
        throw ("manifest model_file missing for capability {0}: {1}" -f $CapabilityId, $manifestPath)
    }

    $resolvedModelFilePath = Join-Path $ModelDir $modelFile
    if (-not (Test-Path $resolvedModelFilePath)) {
        throw ("manifest model file not found for capability {0}: {1}" -f $CapabilityId, $resolvedModelFilePath)
    }
}

$resolvedRegistryPath = [System.IO.Path]::GetFullPath($RegistryPath)
$resolvedDeliveryRoot = [System.IO.Path]::GetFullPath($DeliveryRoot)

if (-not (Test-Path $resolvedRegistryPath)) {
    throw ("registry file not found: {0}" -f $resolvedRegistryPath)
}

$lines = Get-Content -Path $resolvedRegistryPath
$entryCount = 0

foreach ($rawLine in $lines) {
    $line = $rawLine.Trim()
    if ([string]::IsNullOrWhiteSpace($line) -or $line.StartsWith("#")) {
        continue
    }

    $delimiterIndex = $line.IndexOf('=')
    if ($delimiterIndex -lt 1) {
        throw ("invalid registry line: {0}" -f $rawLine)
    }

    $capabilityId = $line.Substring(0, $delimiterIndex).Trim()
    $configValue = $line.Substring($delimiterIndex + 1).Trim()
    if ([string]::IsNullOrWhiteSpace($capabilityId)) {
        throw ("empty capability_id in registry line: {0}" -f $rawLine)
    }
    if ([string]::IsNullOrWhiteSpace($configValue)) {
        throw ("empty config value in registry line: {0}" -f $rawLine)
    }

    $parts = $configValue.Split('|') | ForEach-Object { $_.Trim() }
    if ($parts.Count -lt 4) {
        throw ("registry entry requires at least 4 fields: {0}" -f $rawLine)
    }

    $pluginPath = $parts[0]
    $modelDir = $parts[1]
    $device = $parts[2]
    $maxBatchSize = $parts[3]
    $instanceCount = if ($parts.Count -ge 5) { $parts[4] } else { "1" }

    if ([string]::IsNullOrWhiteSpace($pluginPath)) {
        throw ("empty plugin path for capability: {0}" -f $capabilityId)
    }
    if ([string]::IsNullOrWhiteSpace($modelDir)) {
        throw ("empty model dir for capability: {0}" -f $capabilityId)
    }
    if (($device -ne "cpu") -and ($device -ne "cuda")) {
        throw ("invalid device for capability {0}: {1}" -f $capabilityId, $device)
    }

    $parsedBatchSize = 0
    if (-not [int]::TryParse($maxBatchSize, [ref]$parsedBatchSize) -or $parsedBatchSize -le 0) {
        throw ("invalid max_batch_size for capability {0}: {1}" -f $capabilityId, $maxBatchSize)
    }

    $parsedInstanceCount = 0
    if (-not [int]::TryParse($instanceCount, [ref]$parsedInstanceCount) -or $parsedInstanceCount -le 0) {
        throw ("invalid instance_count for capability {0}: {1}" -f $capabilityId, $instanceCount)
    }

    $resolvedPluginPath = Resolve-RegistryEntryPath -BaseDirectory $resolvedDeliveryRoot -ConfiguredPath $pluginPath
    $resolvedModelDir = Resolve-RegistryEntryPath -BaseDirectory $resolvedDeliveryRoot -ConfiguredPath $modelDir

    if ($RequireFilesExist) {
        if (-not (Test-Path $resolvedPluginPath)) {
            throw ("plugin library not found for capability {0}: {1}" -f $capabilityId, $resolvedPluginPath)
        }
        if (-not (Test-Path $resolvedModelDir)) {
            throw ("model dir not found for capability {0}: {1}" -f $capabilityId, $resolvedModelDir)
        }
        Test-MinimalModelPackage -CapabilityId $capabilityId -ModelDir $resolvedModelDir
    }

    Write-Host ("[validate_plugins_registry] capability={0} plugin={1} model_dir={2} device={3} max_batch_size={4} instance_count={5}" -f $capabilityId, $pluginPath, $modelDir, $device, $parsedBatchSize, $parsedInstanceCount)
    $entryCount++
}

if ($entryCount -le 0) {
    throw "registry contains no valid capability entries"
}

Write-Host ("[validate_plugins_registry] registry ok: {0} entries" -f $entryCount)
