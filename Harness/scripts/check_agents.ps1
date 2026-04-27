param(
    [switch]$IncludeAuth,
    [switch]$IncludeOptional,
    [int]$CommandTimeoutSeconds = 60
)

$ErrorActionPreference = "Stop"

function Get-ProjectDir {
    return (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

function Read-AgentConfig {
    $projectDir = Get-ProjectDir
    $configPath = Join-Path $projectDir "Harness\config\agents.json"
    if (-not (Test-Path $configPath)) {
        throw "Missing Harness agent config: $configPath"
    }

    return Get-Content $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Convert-ToStringArray($Value) {
    if ($null -eq $Value) {
        return @()
    }

    if ($Value -is [System.Array]) {
        return @($Value | ForEach-Object { [string]$_ })
    }

    return @([string]$Value)
}

function Invoke-CheckCommand($AgentName, $CheckName, $CommandValue, $ExpectedContains, $TimeoutSeconds) {
    $command = Convert-ToStringArray $CommandValue
    if ($command.Count -eq 0) {
        Write-Host "SKIP $AgentName $CheckName"
        return $true
    }

    $exe = $command[0]
    $args = @()
    if ($command.Count -gt 1) {
        $args = $command[1..($command.Count - 1)]
    }

    Write-Host "RUN  $AgentName ${CheckName}: $($command -join ' ')"
    $stdoutPath = [System.IO.Path]::GetTempFileName()
    $stderrPath = [System.IO.Path]::GetTempFileName()

    try {
        $process = Start-Process `
            -FilePath $exe `
            -ArgumentList $args `
            -NoNewWindow `
            -PassThru `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath

        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            $output = @("Timed out after $TimeoutSeconds seconds.")
            $exitCode = 124
        } else {
            $exitCode = $process.ExitCode
            if ($null -eq $exitCode -or "$exitCode" -eq "") {
                $exitCode = 0
            }
            $output = @()
            if (Test-Path $stdoutPath) {
                $output += Get-Content $stdoutPath -Encoding UTF8 -ErrorAction SilentlyContinue
            }
            if (Test-Path $stderrPath) {
                $output += Get-Content $stderrPath -Encoding UTF8 -ErrorAction SilentlyContinue
            }
        }
    } catch {
        $output = @($_.Exception.Message)
        $exitCode = 1
    } finally {
        Remove-Item -LiteralPath $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }

    if ($exitCode -ne 0) {
        Write-Host "FAIL $AgentName $CheckName exit=$exitCode"
        $output | ForEach-Object { Write-Host $_ }
        return $false
    }

    $text = ($output | Out-String)
    if ($ExpectedContains -and ($text -notlike "*$ExpectedContains*")) {
        Write-Host "FAIL $AgentName $CheckName expected '$ExpectedContains'"
        $output | ForEach-Object { Write-Host $_ }
        return $false
    }

    Write-Host "OK   $AgentName $CheckName"
    return $true
}

$config = Read-AgentConfig
$allPassed = $true

foreach ($agentProperty in $config.agents.PSObject.Properties) {
    $agentName = $agentProperty.Name
    $agent = $agentProperty.Value

    if ($agent.optional -and -not $IncludeOptional) {
        Write-Host "SKIP $agentName optional"
        continue
    }

    $healthPassed = Invoke-CheckCommand `
        -AgentName $agentName `
        -CheckName "health_check" `
        -CommandValue $agent.health_check `
        -ExpectedContains $null `
        -TimeoutSeconds $CommandTimeoutSeconds
    $allPassed = $allPassed -and $healthPassed

    if ($IncludeAuth -and $agent.auth_check -and $healthPassed) {
        $authPassed = Invoke-CheckCommand `
            -AgentName $agentName `
            -CheckName "auth_check" `
            -CommandValue $agent.auth_check.command `
            -ExpectedContains $agent.auth_check.expected_contains `
            -TimeoutSeconds $CommandTimeoutSeconds
        $allPassed = $allPassed -and $authPassed
    } elseif ($IncludeAuth -and $agent.auth_check -and -not $healthPassed) {
        Write-Host "SKIP $agentName auth_check because health_check failed"
    }
}

if (-not $allPassed) {
    exit 1
}

Write-Host "Harness agent checks passed."
