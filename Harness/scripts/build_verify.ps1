param(
    [ValidateSet("Editor", "Game", "ProjectFiles")]
    [string]$Mode = "Editor"
)

$ErrorActionPreference = "Stop"

function Fail($Message) {
    throw $Message
}

function Get-ProjectDir {
    return (Resolve-Path (Join-Path $PSScriptRoot "..\\..")).Path
}

function Read-ProjectConfig {
    $projectDir = Get-ProjectDir
    $configPath = Join-Path $projectDir "Harness\\config\\project.json"
    if (-not (Test-Path $configPath)) {
        Fail "Missing Harness config: $configPath"
    }

    return Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Resolve-UprojectPath($ProjectDir, $Config) {
    if ($Config.uproject_file) {
        $uprojectPath = Join-Path $ProjectDir $Config.uproject_file
        if (-not (Test-Path $uprojectPath)) {
            Fail "Missing uproject file: $uprojectPath"
        }
        return (Resolve-Path $uprojectPath).Path
    }

    $candidates = Get-ChildItem -Path $ProjectDir -Filter *.uproject -File
    if ($candidates.Count -ne 1) {
        Fail "Set uproject_file in Harness/config/project.json"
    }

    return $candidates[0].FullName
}

function Resolve-EngineRoot($Config) {
    $engineRoot = ""
    if ($Config.build -and $Config.build.engine_root) {
        $engineRoot = $Config.build.engine_root
    } elseif ($env:UE_ENGINE_ROOT) {
        $engineRoot = $env:UE_ENGINE_ROOT
    }

    if (-not $engineRoot) {
        Fail "Set build.engine_root in Harness/config/project.json or UE_ENGINE_ROOT in the environment."
    }

    if (-not (Test-Path $engineRoot)) {
        Fail "Engine root does not exist: $engineRoot"
    }

    return (Resolve-Path $engineRoot).Path
}

function Resolve-UbtPath($EngineRoot) {
    $candidates = @(
        (Join-Path $EngineRoot "Engine\\Binaries\\DotNET\\UnrealBuildTool\\UnrealBuildTool.exe"),
        (Join-Path $EngineRoot "Engine\\Binaries\\DotNET\\UnrealBuildTool.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return (Resolve-Path $candidate).Path
        }
    }

    Fail "Could not find UnrealBuildTool.exe under engine root: $EngineRoot"
}

function Resolve-TargetName($Mode, $Config, $UprojectPath) {
    $uprojectStem = [System.IO.Path]::GetFileNameWithoutExtension($UprojectPath)

    if ($Mode -eq "Editor") {
        if ($Config.build -and $Config.build.editor_target_name) {
            return $Config.build.editor_target_name
        }
        return "$uprojectStem" + "Editor"
    }

    if ($Mode -eq "Game") {
        if ($Config.build -and $Config.build.game_target_name) {
            return $Config.build.game_target_name
        }
        return $uprojectStem
    }

    return ""
}

$projectDir = Get-ProjectDir
$config = Read-ProjectConfig
$uprojectPath = Resolve-UprojectPath -ProjectDir $projectDir -Config $config
$engineRoot = Resolve-EngineRoot -Config $config
$ubtPath = Resolve-UbtPath -EngineRoot $engineRoot
$platform = if ($config.build -and $config.build.platform) { $config.build.platform } else { "Win64" }
$configuration = if ($config.build -and $config.build.configuration) { $config.build.configuration } else { "Development" }

if ($Mode -eq "ProjectFiles") {
    & $ubtPath -ProjectFiles "-Project=$uprojectPath" -Game -Engine
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }

    Write-Host "Project files regenerated successfully."
    exit 0
}

$targetName = Resolve-TargetName -Mode $Mode -Config $config -UprojectPath $uprojectPath
& $ubtPath $targetName $platform $configuration "-Project=$uprojectPath" -NoHotReload -WaitMutex
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "$Mode build verification passed for target $targetName."
