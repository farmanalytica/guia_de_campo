param(
    [string]$PluginRoot = (Split-Path -Parent $MyInvocation.MyCommand.Path),
    [string]$OutputDir = "dist"
)

$ErrorActionPreference = "Stop"

$PluginRoot = (Resolve-Path $PluginRoot).Path
$PluginFolderName = Split-Path -Path $PluginRoot -Leaf
$OutputPath = Join-Path $PluginRoot $OutputDir
$TempRoot = Join-Path $PluginRoot ".build_tmp"
$StageRoot = Join-Path $TempRoot $PluginFolderName
$ZipName = "$PluginFolderName.zip"
$ZipPath = Join-Path $OutputPath $ZipName

$runtimeItems = @(
    "__init__.py",
    "guia_de_campo.py",
    "guia_de_campo_dialog.py",
    "guia_de_campo_service.py",
    "metadata.txt",
    "resources.py",
    "icon.png",
    "farm_icon.png",
    "modules"
)

if (Test-Path $TempRoot) {
    Remove-Item -Path $TempRoot -Recurse -Force
}
if (-not (Test-Path $OutputPath)) {
    New-Item -Path $OutputPath -ItemType Directory | Out-Null
}

New-Item -Path $StageRoot -ItemType Directory -Force | Out-Null

foreach ($item in $runtimeItems) {
    $sourcePath = Join-Path $PluginRoot $item
    if (Test-Path $sourcePath) {
        Copy-Item -Path $sourcePath -Destination $StageRoot -Recurse -Force
    }
}

# Include translations when present so localized UI keeps working.
$i18nPath = Join-Path $PluginRoot "i18n"
if (Test-Path $i18nPath) {
    Copy-Item -Path $i18nPath -Destination $StageRoot -Recurse -Force
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
