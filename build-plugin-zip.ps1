param(
    [string]$PluginRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path),
    [string]$OutputDir = "dist"
)

$ErrorActionPreference = "Stop"

function Get-MetadataValue {
    param(
        [string]$MetadataFile,
        [string]$Key
    )

    if (-not (Test-Path $MetadataFile)) {
        return $null
    }

    $pattern = "^\s*" + [regex]::Escape($Key) + "\s*=\s*(.+)$"
    foreach ($line in Get-Content -Path $MetadataFile) {
        if ($line -match $pattern) {
            return $Matches[1].Trim()
        }
    }

    return $null
}

$PluginRoot = (Resolve-Path $PluginRoot).Path
$PluginFolderName = Split-Path -Path $PluginRoot -Leaf
$MetadataFile = Join-Path $PluginRoot "metadata.txt"
$Version = Get-MetadataValue -MetadataFile $MetadataFile -Key "version"

if ([string]::IsNullOrWhiteSpace($Version)) {
    $Version = "dev"
}

$OutputPath = Join-Path $PluginRoot $OutputDir
$TempRoot = Join-Path $PluginRoot ".build_tmp"
$StageRoot = Join-Path $TempRoot $PluginFolderName
$ZipName = "$PluginFolderName-$Version.zip"
$ZipPath = Join-Path $OutputPath $ZipName

$excludePatterns = @(
    ".git*",
    ".vscode",
    ".idea",
    ".build_tmp",
    "dist",
    "__pycache__",
    "*.pyc",
    "*.pyo",
    "*.zip"
)

if (Test-Path $TempRoot) {
    Remove-Item -Path $TempRoot -Recurse -Force
}
if (-not (Test-Path $OutputPath)) {
    New-Item -Path $OutputPath -ItemType Directory | Out-Null
}

New-Item -Path $StageRoot -ItemType Directory -Force | Out-Null

Get-ChildItem -Path $PluginRoot -Force | Where-Object {
    $name = $_.Name
    foreach ($pattern in $excludePatterns) {
        if ($name -like $pattern) {
            return $false
        }
    }
    return $true
} | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination $StageRoot -Recurse -Force
}

$StageLicense = Join-Path $StageRoot "LICENSE"
$StageLicenseTxt = Join-Path $StageRoot "LICENSE.txt"
if (-not (Test-Path $StageLicense) -and (Test-Path $StageLicenseTxt)) {
    Copy-Item -Path $StageLicenseTxt -Destination $StageLicense -Force
}

if (Test-Path $ZipPath) {
    Remove-Item -Path $ZipPath -Force
}

Compress-Archive -Path (Join-Path $TempRoot $PluginFolderName) -DestinationPath $ZipPath -CompressionLevel Optimal

Remove-Item -Path $TempRoot -Recurse -Force

Write-Host "ZIP generated: $ZipPath"
