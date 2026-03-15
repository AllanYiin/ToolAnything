param(
    [string]$WikiRepoPath = ".wiki-publish",
    [string]$SourceDir = "wiki",
    [string]$RemoteUrl = "https://github.com/AllanYiin/ToolAnything.wiki.git",
    [switch]$InitClone,
    [switch]$Commit,
    [string]$Message = "docs: sync wiki content",
    [switch]$Push
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Resolve-AbsolutePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    $candidate = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $PathValue))
    return $candidate
}

function Require-GitRepository {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    if (-not (Test-Path -LiteralPath (Join-Path $PathValue ".git"))) {
        throw "Git repository not found: $PathValue"
    }
}

function Remove-NonGitItems {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    Get-ChildItem -LiteralPath $PathValue -Force | Where-Object { $_.Name -ne ".git" } | Remove-Item -Recurse -Force
}

function Copy-WikiContent {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourcePath,
        [Parameter(Mandatory = $true)]
        [string]$TargetPath
    )

    Get-ChildItem -LiteralPath $SourcePath -Force | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $TargetPath -Recurse -Force
    }
}

$sourcePath = Resolve-AbsolutePath -PathValue $SourceDir
if (-not (Test-Path -LiteralPath $sourcePath)) {
    throw "Wiki source directory not found: $sourcePath"
}

$wikiRepoPath = Resolve-AbsolutePath -PathValue $WikiRepoPath

if ($InitClone) {
    if (Test-Path -LiteralPath $wikiRepoPath) {
        throw "Target directory already exists, cannot init clone: $wikiRepoPath"
    }
    git clone $RemoteUrl $wikiRepoPath
}

if (-not (Test-Path -LiteralPath $wikiRepoPath)) {
    throw "Wiki repository directory not found: $wikiRepoPath. Use -InitClone to clone automatically."
}

Require-GitRepository -PathValue $wikiRepoPath

Write-Host "Syncing wiki content to $wikiRepoPath"
Remove-NonGitItems -PathValue $wikiRepoPath
Copy-WikiContent -SourcePath $sourcePath -TargetPath $wikiRepoPath

Push-Location $wikiRepoPath
try {
    $status = git status --short
    if (-not $status) {
        Write-Host "No wiki changes to sync."
        exit 0
    }

    Write-Host "Wiki sync complete. Current changes:"
    git status --short

    if ($Commit) {
        git add --all
        git commit -m $Message
        if ($Push) {
            git push
        }
    }
    elseif ($Push) {
        throw "Cannot use -Push without -Commit."
    }
}
finally {
    Pop-Location
}
