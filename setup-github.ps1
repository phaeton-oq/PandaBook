#Requires -Version 5.1
<#
.SYNOPSIS
  One-time setup: configure git user, remote, and initial push.

.PARAMETER Token
  GitHub PAT. If omitted, reads $env:GITHUB_TOKEN or .github-token file.
#>
param(
    [string]$Token
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

function Get-GitHubToken {
    param([string]$Token)
    if ($Token) { return $Token.Trim() }
    if ($env:GITHUB_TOKEN) { return $env:GITHUB_TOKEN.Trim() }
    $tokenFile = Join-Path $PSScriptRoot ".github-token"
    if (Test-Path $tokenFile) { return (Get-Content $tokenFile -Raw).Trim() }
    throw "GitHub token not found. Pass -Token, set `$env:GITHUB_TOKEN, or create .github-token"
}

$token = Get-GitHubToken -Token $Token
$headers = @{
    Authorization = "Bearer $token"
    Accept        = "application/vnd.github+json"
}

Write-Host "Checking GitHub access..." -ForegroundColor Cyan
$user = Invoke-RestMethod -Uri "https://api.github.com/user" -Headers $headers
Write-Host "Authenticated as: $($user.login)" -ForegroundColor Green

try {
    $repo = Invoke-RestMethod -Uri "https://api.github.com/repos/$RepoOwner/$RepoName" -Headers $headers
    Write-Host "Target repo: $($repo.html_url)" -ForegroundColor Green
}
catch {
    throw "Cannot access https://github.com/$RepoOwner/$RepoName. Check collaborator access and token."
}

if (-not (Test-Path (Join-Path $PSScriptRoot ".git"))) {
    Write-Host "Initializing git repository..." -ForegroundColor Cyan
    $initResult = Invoke-Git init
    if ($initResult.ExitCode -ne 0) {
        throw "git init failed: $($initResult.Output)"
    }
}

Write-Host "Configuring git user..." -ForegroundColor Cyan
Invoke-Git config user.name $GitUserName | Out-Null
Invoke-Git config user.email $GitUserEmail | Out-Null

$remoteResult = Invoke-Git remote get-url origin
if ($remoteResult.ExitCode -ne 0) {
    Write-Host "Adding remote 'origin'..." -ForegroundColor Cyan
    Invoke-Git remote add origin $RemoteUrl | Out-Null
}
else {
    Write-Host "Updating remote 'origin'..." -ForegroundColor Cyan
    Invoke-Git remote set-url origin $RemoteUrl | Out-Null
}

$hasCommit = (Invoke-Git log -1 --oneline).ExitCode -eq 0
if (-not $hasCommit) {
    Write-Host "Creating initial commit..." -ForegroundColor Cyan
    Invoke-Git add -A | Out-Null
    $commitResult = Invoke-Git commit -m "Initial commit"
    if ($commitResult.ExitCode -ne 0) {
        throw "Initial commit failed: $($commitResult.Output)"
    }
}

$branchResult = Invoke-Git branch --show-current
$branch = if ($branchResult.ExitCode -eq 0) {
    ($branchResult.Output | Select-Object -First 1).ToString().Trim()
} else {
    ""
}
if (-not $branch) { $branch = "master" }

Write-Host "Pushing to $RemoteUrl ($branch)..." -ForegroundColor Cyan
$pushResult = Invoke-Git push origin "HEAD:refs/heads/$branch"
if ($pushResult.ExitCode -ne 0) {
    throw "Push failed: $($pushResult.Output)"
}

Invoke-Git branch --set-upstream-to=origin/$branch $branch | Out-Null

Write-Host "Done! Remote: $RemoteUrl" -ForegroundColor Green
Write-Host "Use .\push.ps1 for auto-commit and push." -ForegroundColor Cyan
