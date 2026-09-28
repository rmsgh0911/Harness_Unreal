[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$BootstrapArgs
)

$ErrorActionPreference = "Stop"
$UvVersion = "0.12.18"
$PythonRequest = "3.12"
$UvInstallerUrl = "https://releases.astral.sh/github/uv/releases/download/$UvVersion/uv-installer.ps1"
$UvInstallerSha256 = "452b97dba048fd153b697a4d612bacdb6f1a29085f9691fd2bf869aeb9cca9eb"
$VersionProbe = "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 3)"

function Show-HarnessBootstrapUsage {
    @"
Harness Python Bootstrap
Usage: & Harness\harness.ps1 bootstrap [--status]

Without --status, this explicitly downloads a pinned, checksum-verified uv
installer when uv is unavailable, then installs a project-local managed
Python $PythonRequest runtime. It does not modify PATH, shell profiles, or the
Windows Python registry.

Environment overrides:
  HARNESS_UV            Existing uv 0.12.18 executable for offline/mirrored setup.
  HARNESS_RUNTIME_ROOT  Platform-specific managed-runtime directory.
  HARNESS_UV_CACHE_DIR  Optional preseeded uv cache directory.

Normal Harness commands never trigger this network bootstrap implicitly.
"@
}

function Get-HarnessRuntimeRoot {
    if ($env:HARNESS_RUNTIME_ROOT) {
        $candidate = $env:HARNESS_RUNTIME_ROOT
        if (-not [System.IO.Path]::IsPathRooted($candidate)) {
            $candidate = Join-Path $PSScriptRoot $candidate
        }
        return [System.IO.Path]::GetFullPath($candidate)
    }

    $processorArchitecture = if ($env:PROCESSOR_ARCHITECTURE) { $env:PROCESSOR_ARCHITECTURE } else { "unknown" }
    $architecture = switch ($processorArchitecture.ToUpperInvariant()) {
        "AMD64" { "x86_64" }
        "ARM64" { "aarch64" }
        "X86" { "x86" }
        default { $processorArchitecture.ToLowerInvariant() }
    }
    return [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".runtime\windows-$architecture"))
}

function Test-HarnessPathWithin {
    param(
        [Parameter(Mandatory = $true)][string]$Candidate,
        [Parameter(Mandatory = $true)][string]$Parent
    )

    $parentFull = [System.IO.Path]::GetFullPath($Parent).TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    $candidateFull = [System.IO.Path]::GetFullPath($Candidate)
    if (-not $candidateFull.StartsWith($parentFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $false
    }
    $parentWithoutSeparator = $parentFull.TrimEnd('\', '/')
    if (Test-Path -LiteralPath $parentWithoutSeparator) {
        try {
            $parentAttributes = [System.IO.File]::GetAttributes($parentWithoutSeparator)
        }
        catch {
            return $false
        }
        if (($parentAttributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            return $false
        }
    }
    $segments = [System.Collections.Generic.List[string]]::new()
    foreach ($segment in ($candidateFull.Substring($parentFull.Length) -split '[\\/]')) {
        if ($segment) {
            $segments.Add($segment)
        }
    }
    $current = $parentWithoutSeparator
    $reparseHops = 0
    while ($segments.Count -gt 0) {
        $segment = $segments[0]
        $segments.RemoveAt(0)
        $current = Join-Path $current $segment
        if (Test-Path -LiteralPath $current) {
            try {
                $attributes = [System.IO.File]::GetAttributes($current)
            }
            catch {
                return $false
            }
            if (($attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                $item = Get-Item -Force -LiteralPath $current
                $targets = @($item.Target)
                if ($targets.Count -eq 0 -or -not $targets[0]) {
                    return $false
                }
                $target = [string]$targets[0]
                $targetFull = if ([System.IO.Path]::IsPathRooted($target)) {
                    [System.IO.Path]::GetFullPath($target)
                } else {
                    [System.IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $current) $target))
                }
                if (
                    -not $targetFull.Equals($parentWithoutSeparator, [System.StringComparison]::OrdinalIgnoreCase) -and
                    -not $targetFull.StartsWith($parentFull, [System.StringComparison]::OrdinalIgnoreCase)
                ) {
                    return $false
                }
                $remaining = [System.Collections.Generic.List[string]]::new()
                if ($targetFull.StartsWith($parentFull, [System.StringComparison]::OrdinalIgnoreCase)) {
                    foreach ($targetSegment in ($targetFull.Substring($parentFull.Length) -split '[\\/]')) {
                        if ($targetSegment) {
                            $remaining.Add($targetSegment)
                        }
                    }
                }
                foreach ($queuedSegment in $segments) {
                    $remaining.Add($queuedSegment)
                }
                $segments = $remaining
                $current = $parentWithoutSeparator
                $reparseHops += 1
                if ($reparseHops -gt 32) {
                    return $false
                }
            }
        }
    }
    return $true
}

function Test-HarnessPython {
    param([Parameter(Mandatory = $true)][string]$Executable)

    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        return $false
    }
    & $Executable -c $VersionProbe 1>$null 2>$null
    return $LASTEXITCODE -eq 0
}

function Test-HarnessReparsePoint {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    $attributes = [System.IO.File]::GetAttributes($Path)
    return ($attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0
}

function Get-HarnessManagedPython {
    param(
        [Parameter(Mandatory = $true)][string]$RuntimeRoot,
        [Parameter(Mandatory = $true)][string]$MarkerPath
    )

    if (-not (Test-Path -LiteralPath $MarkerPath -PathType Leaf)) {
        return $null
    }
    $candidate = [System.IO.File]::ReadAllText($MarkerPath).Trim()
    if (-not $candidate -or -not (Test-HarnessPathWithin -Candidate $candidate -Parent $RuntimeRoot)) {
        return $null
    }
    if (-not (Test-HarnessPython -Executable $candidate)) {
        return $null
    }
    return [System.IO.Path]::GetFullPath($candidate)
}

function Resolve-HarnessCommand {
    param([Parameter(Mandatory = $true)][string]$Candidate)

    if (
        [System.IO.Path]::IsPathRooted($Candidate) -or
        $Candidate.Contains([System.IO.Path]::DirectorySeparatorChar) -or
        $Candidate.Contains([System.IO.Path]::AltDirectorySeparatorChar)
    ) {
        if (Test-Path -LiteralPath $Candidate -PathType Leaf) {
            return [System.IO.Path]::GetFullPath($Candidate)
        }
        return $null
    }
    $command = Get-Command $Candidate -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    return $null
}

function Test-HarnessUvVersion {
    param([Parameter(Mandatory = $true)][string]$Executable)

    if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) {
        return $false
    }
    $output = @(& $Executable --version 2>$null)
    if ($LASTEXITCODE -ne 0 -or $output.Count -eq 0) {
        return $false
    }
    $versionText = ([string]$output[-1]).Trim()
    return $versionText -eq "uv $UvVersion" -or $versionText.StartsWith("uv $UvVersion ", [System.StringComparison]::Ordinal)
}

function Get-HarnessFileSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)

    $stream = [System.IO.File]::OpenRead($Path)
    try {
        $sha256 = [System.Security.Cryptography.SHA256]::Create()
        try {
            $digest = $sha256.ComputeHash($stream)
        }
        finally {
            $sha256.Dispose()
        }
    }
    finally {
        $stream.Dispose()
    }
    return ([System.BitConverter]::ToString($digest)).Replace("-", "").ToLowerInvariant()
}

function Install-HarnessUv {
    param(
        [Parameter(Mandatory = $true)][string]$RuntimeRoot,
        [Parameter(Mandatory = $true)][string]$BinDirectory
    )

    New-Item -ItemType Directory -Path $RuntimeRoot -Force | Out-Null
    New-Item -ItemType Directory -Path $BinDirectory -Force | Out-Null
    $installerPath = Join-Path $RuntimeRoot ".uv-installer-$PID.ps1"
    try {
        [System.Net.ServicePointManager]::SecurityProtocol = (
            [System.Net.ServicePointManager]::SecurityProtocol -bor [System.Net.SecurityProtocolType]::Tls12
        )
        Invoke-WebRequest -Uri $UvInstallerUrl -OutFile $installerPath -UseBasicParsing
        $actualHash = Get-HarnessFileSha256 -Path $installerPath
        if ($actualHash -ne $UvInstallerSha256) {
            throw "uv installer checksum mismatch; expected $UvInstallerSha256 but received $actualHash"
        }

        $windowsModulePath = Join-Path $env:WINDIR "System32\WindowsPowerShell\v1.0\Modules"
        if ($PSVersionTable.PSEdition -eq "Desktop" -and (Test-Path -LiteralPath $windowsModulePath -PathType Container)) {
            $env:PSModulePath = if ($env:PSModulePath) {
                "$windowsModulePath$([System.IO.Path]::PathSeparator)$($env:PSModulePath)"
            } else {
                $windowsModulePath
            }
        }
        $env:UV_UNMANAGED_INSTALL = $BinDirectory
        $env:UV_NO_MODIFY_PATH = "1"
        & $installerPath 2>&1 | ForEach-Object { Write-Host $_ }
    }
    finally {
        if (Test-Path -LiteralPath $installerPath -PathType Leaf) {
            [System.IO.File]::Delete($installerPath)
        }
    }

    $installed = Join-Path $BinDirectory "uv.exe"
    if (-not (Test-Path -LiteralPath $installed -PathType Leaf)) {
        throw "uv installer completed without creating $installed"
    }
    if (-not (Test-HarnessUvVersion -Executable $installed)) {
        throw "the installed uv is not the pinned $UvVersion release"
    }
    return $installed
}

function Get-HarnessUv {
    param(
        [Parameter(Mandatory = $true)][string]$RuntimeRoot,
        [Parameter(Mandatory = $true)][string]$BinDirectory
    )

    if ($env:HARNESS_UV) {
        $explicit = Resolve-HarnessCommand -Candidate $env:HARNESS_UV
        if (-not $explicit) {
            throw "HARNESS_UV does not resolve to an executable; no network fallback was attempted"
        }
        if (-not (Test-HarnessUvVersion -Executable $explicit)) {
            throw "HARNESS_UV must provide the pinned uv $UvVersion release; no network fallback was attempted"
        }
        return $explicit
    }

    $localUv = Join-Path $BinDirectory "uv.exe"
    if (Test-HarnessUvVersion -Executable $localUv) {
        return $localUv
    }
    return Install-HarnessUv -RuntimeRoot $RuntimeRoot -BinDirectory $BinDirectory
}

try {
    $mode = "install"
    foreach ($argument in $BootstrapArgs) {
        switch ($argument) {
            "--status" { $mode = "status" }
            "--help" { Show-HarnessBootstrapUsage; exit 0 }
            "-h" { Show-HarnessBootstrapUsage; exit 0 }
            default { throw "unknown bootstrap option: $argument" }
        }
    }

    $runtimeRoot = Get-HarnessRuntimeRoot
    $volumeRoot = [System.IO.Path]::GetPathRoot($runtimeRoot)
    if ($runtimeRoot.TrimEnd('\', '/') -eq $volumeRoot.TrimEnd('\', '/')) {
        throw "HARNESS_RUNTIME_ROOT cannot be a filesystem root"
    }
    if (Test-HarnessReparsePoint -Path $runtimeRoot) {
        throw "HARNESS_RUNTIME_ROOT cannot be a junction, symlink, or other reparse point"
    }
    $markerPath = Join-Path $runtimeRoot "python.path"
    $managedPython = Get-HarnessManagedPython -RuntimeRoot $runtimeRoot -MarkerPath $markerPath
    if ($mode -eq "status") {
        if (-not $managedPython) {
            Write-Output "Harness managed Python is not ready. Run: & Harness\harness.ps1 bootstrap"
            exit 1
        }
        Write-Output "Harness managed Python is ready."
        Write-Output "- Runtime root: $runtimeRoot"
        Write-Output "- Python: $managedPython"
        & $managedPython --version
        exit $LASTEXITCODE
    }
    if ($managedPython) {
        Write-Output "Harness managed Python is already ready."
        Write-Output "- Runtime root: $runtimeRoot"
        Write-Output "- Python: $managedPython"
        & $managedPython --version
        exit $LASTEXITCODE
    }

    $binDirectory = Join-Path $runtimeRoot "bin"
    $pythonDirectory = Join-Path $runtimeRoot "python"
    $cacheDirectory = if ($env:HARNESS_UV_CACHE_DIR) {
        [System.IO.Path]::GetFullPath($env:HARNESS_UV_CACHE_DIR)
    } elseif ($env:UV_CACHE_DIR) {
        [System.IO.Path]::GetFullPath($env:UV_CACHE_DIR)
    } else {
        Join-Path $runtimeRoot "cache"
    }
    foreach ($managedDirectory in @($binDirectory, $pythonDirectory)) {
        if (Test-HarnessReparsePoint -Path $managedDirectory) {
            throw "managed runtime directories cannot be junctions, symlinks, or other reparse points: $managedDirectory"
        }
    }
    New-Item -ItemType Directory -Path $binDirectory, $pythonDirectory, $cacheDirectory -Force | Out-Null

    $uvPath = Get-HarnessUv -RuntimeRoot $runtimeRoot -BinDirectory $binDirectory
    $env:UV_PYTHON_INSTALL_DIR = $pythonDirectory
    $env:UV_CACHE_DIR = $cacheDirectory
    $env:UV_PYTHON_INSTALL_BIN = "0"
    $env:UV_PYTHON_INSTALL_REGISTRY = "0"
    $env:UV_NO_CONFIG = "1"
    $env:UV_NO_PROJECT = "1"
    $env:UV_MANAGED_PYTHON = "1"
    $env:UV_NO_PROGRESS = "1"

    & $uvPath python install $PythonRequest
    if ($LASTEXITCODE -ne 0) {
        throw "uv could not install managed Python $PythonRequest (exit $LASTEXITCODE)"
    }
    $pythonOutput = @(& $uvPath python find $PythonRequest 2>$null)
    if ($LASTEXITCODE -ne 0 -or $pythonOutput.Count -eq 0) {
        throw "uv installed Python but could not locate its executable"
    }
    $managedPython = [string]$pythonOutput[-1]
    $managedPython = $managedPython.Trim()
    if (-not (Test-HarnessPathWithin -Candidate $managedPython -Parent $pythonDirectory)) {
        throw "uv returned a Python executable outside the managed runtime: $managedPython"
    }
    if (-not (Test-HarnessPython -Executable $managedPython)) {
        throw "the managed Python executable is missing, older than 3.10, or could not start"
    }

    $markerTemporary = "$markerPath.tmp.$PID"
    try {
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($markerTemporary, "$managedPython$([Environment]::NewLine)", $utf8NoBom)
        Move-Item -LiteralPath $markerTemporary -Destination $markerPath -Force
    }
    finally {
        if (Test-Path -LiteralPath $markerTemporary -PathType Leaf) {
            [System.IO.File]::Delete($markerTemporary)
        }
    }

    Write-Output "Harness managed Python is ready."
    Write-Output "- Runtime root: $runtimeRoot"
    Write-Output "- Python: $managedPython"
    Write-Output "- uv: $uvPath"
    & $managedPython --version
    exit $LASTEXITCODE
}
catch {
    [Console]::Error.WriteLine("Harness bootstrap failed: $($_.Exception.Message)")
    exit 2
}
