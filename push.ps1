#Requires -Version 5.1
<#
.SYNOPSIS
  Auto stage, commit, and push changes to GitHub.

.PARAMETER Message
  Commit message. Default: timestamp-based message.
#>
param(
    [string]$Message,
    [switch]$Force
)

$GitUserName  = "LucPrusPPi"
$GitUserEmail = "lakeg4merx@gmail.com"
$RepoOwner    = "phaeton-oq"
$RepoName     = "PandaBook"
$RemoteUrl    = "git@github.com:$RepoOwner/$RepoName.git"

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$GitArgs)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = & git @GitArgs 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    return @{ Output = $output; ExitCode = $code }
}

function Invoke-GitCommit {
    param([string]$Message)
    $msgFile = [System.IO.Path]::GetTempFileName()
    try {
        [System.IO.File]::WriteAllText($msgFile, $Message, [System.Text.UTF8Encoding]::new($false))
        $commitResult = Invoke-Git commit -F $msgFile
        if ($commitResult.ExitCode -ne 0) {
            throw "Commit failed: $($commitResult.Output)"
        }
    }
    finally {
        Remove-Item $msgFile -ErrorAction SilentlyContinue
    }

    $lastMsg = ((Invoke-Git log -1 --format=%B).Output | Out-String)
    if ($lastMsg -match 'Co-authored-by:\s*Cursor') {
        $clean = (($lastMsg -split "`r?`n") | Where-Object { $_ -notmatch 'Co-authored-by:\s*Cursor' }) -join "`n"
        $cleanFile = [System.IO.Path]::GetTempFileName()
        try {
            [System.IO.File]::WriteAllText($cleanFile, $clean.TrimEnd(), [System.Text.UTF8Encoding]::new($false))
            Invoke-Git commit --amend -F $cleanFile | Out-Null
            Write-Host "Removed Cursor co-author from commit." -ForegroundColor Yellow
        }
        finally {
            Remove-Item $cleanFile -ErrorAction SilentlyContinue
        }
    }
}

if (-not (Test-Path (Join-Path $PSScriptRoot ".git"))) {
    throw "Not a git repository. Run .\setup-github.ps1 first."
}

Write-Host "Configuring git user..." -ForegroundColor Cyan
Invoke-Git config user.name $GitUserName | Out-Null
Invoke-Git config user.email $GitUserEmail | Out-Null

$remoteResult = Invoke-Git remote get-url origin
if ($remoteResult.ExitCode -ne 0) {
    Write-Host "Adding remote 'origin' -> $RemoteUrl" -ForegroundColor Cyan
    Invoke-Git remote add origin $RemoteUrl | Out-Null
}
else {
    $currentRemote = ($remoteResult.Output | Select-Object -First 1).ToString().Trim()
    if ($currentRemote -ne $RemoteUrl) {
        Write-Host "Updating remote 'origin' -> $RemoteUrl" -ForegroundColor Cyan
        Invoke-Git remote set-url origin $RemoteUrl | Out-Null
    }
}

$branchResult = Invoke-Git branch --show-current
$branch = if ($branchResult.ExitCode -eq 0) {
    ($branchResult.Output | Select-Object -First 1).ToString().Trim()
} else {
    ""
}
if (-not $branch) {
    Invoke-Git checkout -b master | Out-Null
    $branch = "master"
}

$status = (Invoke-Git status --porcelain).Output
$hasChanges = [bool]$status

if ($hasChanges) {
    if (-not $Message) {
        $Message = "Auto commit $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    }

    Write-Host "Staging changes..." -ForegroundColor Cyan
    Invoke-Git add -A | Out-Null

    Write-Host "Committing: $Message" -ForegroundColor Cyan
    Invoke-GitCommit -Message $Message
}
else {
    Write-Host "No file changes." -ForegroundColor Yellow
}

$pushArgs = @("push", "origin", "HEAD:refs/heads/$branch")
if ($Force) { $pushArgs = @("push", "--force", "origin", "HEAD:refs/heads/$branch") }

Write-Host "Pushing to $RemoteUrl ($branch)..." -ForegroundColor Cyan
$pushResult = Invoke-Git @pushArgs
if ($pushResult.ExitCode -ne 0) {
    throw "Push failed: $($pushResult.Output)"
}

Invoke-Git branch --set-upstream-to=origin/$branch $branch | Out-Null
Write-Host "Pushed to $RemoteUrl" -ForegroundColor Green
