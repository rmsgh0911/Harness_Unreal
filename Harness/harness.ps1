[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$HarnessArgs
)

$ErrorActionPreference = "Stop"
$bridgedArgCount = [Environment]::GetEnvironmentVariable("HARNESS_INTERNAL_ARG_COUNT", "Process")
if ($null -ne $bridgedArgCount) {
    $parsedArgCount = 0
    if (-not [int]::TryParse($bridgedArgCount, [ref]$parsedArgCount) -or $parsedArgCount -lt 0 -or $parsedArgCount -gt 4096) {
        [Console]::Error.WriteLine("Harness launcher received an invalid internal argument count.")
        exit 2
    }
    $HarnessArgs = @(
        for ($index = 1; $index -le $parsedArgCount; $index++) {
            [Environment]::GetEnvironmentVariable("HARNESS_INTERNAL_ARG_$index", "Process")
        }
    )
}
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$bootstrapPath = Join-Path $scriptRoot "bootstrap.ps1"
if ($HarnessArgs.Count -gt 0 -and $HarnessArgs[0].Equals("bootstrap", [System.StringComparison]::OrdinalIgnoreCase)) {
    if (-not (Test-Path -LiteralPath $bootstrapPath -PathType Leaf)) {
        [Console]::Error.WriteLine("Harness bootstrap implementation is missing: $bootstrapPath")
        exit 2
    }
    $bootstrapArgs = if ($HarnessArgs.Count -gt 1) { $HarnessArgs[1..($HarnessArgs.Count - 1)] } else { @() }
    & $bootstrapPath -BootstrapArgs $bootstrapArgs
    exit $LASTEXITCODE
}

# The current Python Install Manager may install a runtime automatically when
# py/python is probed with no runtime present. Normal Harness commands are
# intentionally discovery-only; bootstrap is the sole networked install path.
$env:PYTHON_MANAGER_AUTOMATIC_INSTALL = "0"

$cliPath = Join-Path $scriptRoot "scripts\tools\harness_cli.py"
$versionProbe = "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 3)"

function Invoke-HarnessPython {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Executable,
        [string[]]$PrefixArgs = @()
    )

    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        & $Executable @PrefixArgs -c $versionProbe 2>$null
        $probeExitCode = $LASTEXITCODE
    }
    catch {
        $probeExitCode = -1
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($probeExitCode -ne 0) {
        return $false
    }
    $bridgeNames = [System.Collections.Generic.List[string]]::new()
    try {
        $bridgeCountName = "HARNESS_INTERNAL_PY_ARG_COUNT"
        [Environment]::SetEnvironmentVariable($bridgeCountName, [string]$HarnessArgs.Count, "Process")
        $bridgeNames.Add($bridgeCountName)
        for ($index = 0; $index -lt $HarnessArgs.Count; $index++) {
            $name = "HARNESS_INTERNAL_PY_ARG_$($index + 1)"
            # Keep even an empty argument non-empty in the process environment.
            # On Windows, assigning an empty environment value removes the variable.
            $encoded = "b64:" + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes([string]$HarnessArgs[$index]))
            [Environment]::SetEnvironmentVariable($name, $encoded, "Process")
            $bridgeNames.Add($name)
        }
        $ErrorActionPreference = "Continue"
        & $Executable @PrefixArgs -X utf8 -B $cliPath
        $toolExitCode = $LASTEXITCODE
    }
    finally {
        foreach ($name in $bridgeNames) {
            [Environment]::SetEnvironmentVariable($name, $null, "Process")
        }
        $ErrorActionPreference = $previousErrorActionPreference
    }
    exit $toolExitCode
}

function Test-HarnessReparsePoint {
    param([Parameter(Mandatory = $true)][string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    $attributes = [System.IO.File]::GetAttributes($Path)
    return ($attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0
}

function Test-HarnessManagedPath {
    param(
        [Parameter(Mandatory = $true)][string]$Candidate,
        [Parameter(Mandatory = $true)][string]$RuntimeRoot
    )

    $runtimeFull = [System.IO.Path]::GetFullPath($RuntimeRoot).TrimEnd('\', '/')
    $runtimePrefix = $runtimeFull + [System.IO.Path]::DirectorySeparatorChar
    $candidateFull = [System.IO.Path]::GetFullPath($Candidate)
    if (-not $candidateFull.StartsWith($runtimePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $false
    }
    if (Test-HarnessReparsePoint -Path $runtimeFull) {
        return $false
    }
    $segments = [System.Collections.Generic.List[string]]::new()
    foreach ($segment in ($candidateFull.Substring($runtimePrefix.Length) -split '[\\/]')) {
        if ($segment) {
            $segments.Add($segment)
        }
    }
    $current = $runtimeFull
    $reparseHops = 0
    while ($segments.Count -gt 0) {
        $segment = $segments[0]
        $segments.RemoveAt(0)
        $current = Join-Path $current $segment
        if (Test-HarnessReparsePoint -Path $current) {
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
                -not $targetFull.Equals($runtimeFull, [System.StringComparison]::OrdinalIgnoreCase) -and
                -not $targetFull.StartsWith($runtimePrefix, [System.StringComparison]::OrdinalIgnoreCase)
            ) {
                return $false
            }
            $remaining = [System.Collections.Generic.List[string]]::new()
            if ($targetFull.StartsWith($runtimePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                foreach ($targetSegment in ($targetFull.Substring($runtimePrefix.Length) -split '[\\/]')) {
                    if ($targetSegment) {
                        $remaining.Add($targetSegment)
                    }
                }
            }
            foreach ($queuedSegment in $segments) {
                $remaining.Add($queuedSegment)
            }
            $segments = $remaining
            $current = $runtimeFull
            $reparseHops += 1
            if ($reparseHops -gt 32) {
                return $false
            }
        }
    }
    return $true
}

if ($env:HARNESS_PYTHON) {
    $configured = Get-Command $env:HARNESS_PYTHON -ErrorAction SilentlyContinue
    if (-not $configured -and -not (Test-Path -LiteralPath $env:HARNESS_PYTHON -PathType Leaf)) {
        [Console]::Error.WriteLine("HARNESS_PYTHON does not resolve to an executable. Set it to a Python 3.10+ executable path.")
        exit 2
    }
    if (-not (Invoke-HarnessPython -Executable $env:HARNESS_PYTHON)) {
        [Console]::Error.WriteLine("HARNESS_PYTHON is not Python 3.10+ or could not be started. No fallback was attempted.")
        exit 2
    }
}

$runtimeRoot = if ($env:HARNESS_RUNTIME_ROOT) {
    if ([System.IO.Path]::IsPathRooted($env:HARNESS_RUNTIME_ROOT)) {
        [System.IO.Path]::GetFullPath($env:HARNESS_RUNTIME_ROOT)
    } else {
        [System.IO.Path]::GetFullPath((Join-Path $scriptRoot $env:HARNESS_RUNTIME_ROOT))
    }
} else {
    $processorArchitecture = if ($env:PROCESSOR_ARCHITECTURE) { $env:PROCESSOR_ARCHITECTURE } else { "unknown" }
    $architecture = switch ($processorArchitecture.ToUpperInvariant()) {
        "AMD64" { "x86_64" }
        "ARM64" { "aarch64" }
        "X86" { "x86" }
        default { $processorArchitecture.ToLowerInvariant() }
    }
    [System.IO.Path]::GetFullPath((Join-Path $scriptRoot ".runtime\windows-$architecture"))
}
$runtimeVolumeRoot = [System.IO.Path]::GetPathRoot($runtimeRoot)
if ($runtimeRoot.TrimEnd('\', '/') -eq $runtimeVolumeRoot.TrimEnd('\', '/')) {
    [Console]::Error.WriteLine("HARNESS_RUNTIME_ROOT cannot be a filesystem root.")
    exit 2
}
if (Test-HarnessReparsePoint -Path $runtimeRoot) {
    [Console]::Error.WriteLine("HARNESS_RUNTIME_ROOT cannot be a junction, symlink, or other reparse point.")
    exit 2
}
$managedMarker = Join-Path $runtimeRoot "python.path"
if ((Test-Path -LiteralPath $managedMarker -PathType Leaf) -and -not (Test-HarnessReparsePoint -Path $managedMarker)) {
    $managedPython = [System.IO.File]::ReadAllText($managedMarker).Trim()
    try {
        $managedFull = if ($managedPython) { [System.IO.Path]::GetFullPath($managedPython) } else { "" }
    } catch {
        $managedFull = ""
    }
    if ($managedFull -and (Test-HarnessManagedPath -Candidate $managedFull -RuntimeRoot $runtimeRoot) -and (Test-Path -LiteralPath $managedFull -PathType Leaf)) {
        if (-not (Invoke-HarnessPython -Executable $managedFull)) {
            $failed = @("managed runtime")
        }
    }
}

$candidates = @(
    @{ Executable = "py"; PrefixArgs = @("-3") },
    @{ Executable = "python3"; PrefixArgs = @() },
    @{ Executable = "python"; PrefixArgs = @() }
)
$failed = @($failed)
foreach ($candidate in $candidates) {
    $executable = [string]$candidate.Executable
    $prefixArgs = [string[]]$candidate.PrefixArgs
    if (-not (Get-Command $executable -ErrorAction SilentlyContinue)) {
        continue
    }
    if (-not (Invoke-HarnessPython -Executable $executable -PrefixArgs $prefixArgs)) {
        $failed += $executable
    }
}

$failedText = if ($failed.Count) { " Candidates below 3.10 or unavailable: $($failed -join ', ')." } else { "" }
[Console]::Error.WriteLine("Python 3.10+ was not found. Run '& Harness\harness.ps1 bootstrap', install Python, or set HARNESS_PYTHON to its executable path.$failedText")
exit 2
