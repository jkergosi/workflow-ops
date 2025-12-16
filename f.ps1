<#
=====================================================
Worktree Menu Script (Interactive + Headless)

INTERACTIVE MODE
----------------
Run with no parameters:
  .\worktree_menu.ps1

HEADLESS MODE (no prompts, automation-safe)
-------------------------------------------
Required:
  -Feature  M | 1 | 2 | 3 | 4
  -Action   S | F | D

Action-specific parameters:

Start:
  .\worktree_menu.ps1 -Feature 2 -Action S

Finish:
  .\worktree_menu.ps1 -Feature 3 -Action F -Message "Commit message"

  Optional:
    -AllowEmpty   Allow commit when no changes exist

Destroy:
  .\worktree_menu.ps1 -Feature 4 -Action D -Yes

HELP
----
  .\worktree_menu.ps1 -Help

Exit codes:
  0 = success
  1 = invalid usage or failure
=====================================================
#>

param (
    [ValidateSet("M","1","2","3","4")]
    [string]$Feature,

    [ValidateSet("S","F","D")]
    [string]$Action,

    [string]$Message,

    [switch]$Yes,
    [switch]$AllowEmpty,
    [switch]$Help
)

# ---------- CONFIG ----------
$WorktreeRoot = "F:\web\AllThings\_projects\n8n-ops-trees"
$FeatureOrder = @("M", "1", "2", "3", "4")

$Features = @{
    "M" = "main"
    "1" = "f1"
    "2" = "f2"
    "3" = "f3"
    "4" = "f4"
}

# ---------- HELP ----------
if ($Help) {
    Get-Help $MyInvocation.MyCommand.Path -Detailed
    exit 0
}

# ---------- HELPERS ----------
function Get-WorktreePath($name) {
    Join-Path $WorktreeRoot $name
}

function Test-WorktreeExists($name) {
    Test-Path (Get-WorktreePath $name)
}

function Invoke-Git {
    param (
        [string]$Path,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$GitArgs
    )
    & git -C $Path @GitArgs
}

function Get-GitDirty($path) {
    $out = Invoke-Git $path status --porcelain
    return -not [string]::IsNullOrWhiteSpace($out)
}

# ---------- HEADLESS MODE ----------
if ($Feature -or $Action) {

    if (-not ($Feature -and $Action)) {
        Write-Error "Both -Feature and -Action are required for headless mode."
        exit 1
    }

    $name = $Features[$Feature]
    $path = Get-WorktreePath $name

    switch ($Action) {

        "S" {
            if (-not (Test-WorktreeExists $name)) {
                Push-Location $WorktreeRoot
                git worktree add $name
                Pop-Location
            }
            exit 0
        }

        "F" {
            if (-not $Message) {
                Write-Error "-Message is required for Finish."
                exit 1
            }

            if (-not (Test-WorktreeExists $name)) {
                Write-Error "Worktree does not exist."
                exit 1
            }

            if (-not (Get-GitDirty $path) -and -not $AllowEmpty) {
                Write-Error "No changes to commit."
                exit 1
            }

            Invoke-Git $path add -A
            Invoke-Git $path commit -m $Message
            exit 0
        }

        "D" {
            if (-not $Yes) {
                Write-Error "-Yes is required to destroy a worktree."
                exit 1
            }

            if (-not (Test-WorktreeExists $name)) {
                Write-Error "Worktree does not exist."
                exit 1
            }

            Push-Location $WorktreeRoot
            git worktree remove $name
            Pop-Location
            exit 0
        }
    }
}

# ---------- INTERACTIVE MODE ----------
function Show-FeatureMenu {
    Clear-Host
    Write-Host "Select FEATURE:`n"
    Write-Host "  Key  Feature  Exists"
    Write-Host "  ---  -------  ------"

    foreach ($key in $FeatureOrder) {
        $name   = $Features[$key]
        $exists = if (Test-WorktreeExists $name) { "Yes" } else { "No" }
        Write-Host ("   {0,-2}  {1,-7} {2}" -f $key, $name, $exists)
    }

    Write-Host ""
    Write-Host "   L   List"
    Write-Host "   Q   Quit`n"
}

function Show-ActionMenu($name) {
    $exists = Test-WorktreeExists $name
    $dirty  = if ($exists) { Get-GitDirty (Get-WorktreePath $name) } else { $false }

    Clear-Host
    Write-Host "Feature: $name   Exists: $(if ($exists) { 'Yes' } else { 'No' })`n"
    Write-Host "Select ACTION:"
    Write-Host "  S  Start"

    if ($exists -and $dirty) {
        Write-Host "  F  Finish"
    }

    if ($exists) {
        Write-Host "  D  Destroy"
    }

    Write-Host "  B  Back"
    Write-Host "  Q  Quit`n"
}

function Start-Feature($name) {
    if (-not (Test-WorktreeExists $name)) {
        Push-Location $WorktreeRoot
        git worktree add $name
        Pop-Location
    }
    Read-Host "Started. Press ENTER"
}

function Finish-Feature($name) {
    $path = Get-WorktreePath $name

    if (-not (Get-GitDirty $path)) {
        Write-Host "No changes to commit."
        Read-Host "Press ENTER"
        return
    }

    Clear-Host
    Invoke-Git $path status
    Write-Host ""
    Invoke-Git $path diff --stat

    do {
        $msg = Read-Host "Commit message"
    } while ([string]::IsNullOrWhiteSpace($msg))

    Invoke-Git $path add -A
    Invoke-Git $path commit -m $msg

    Invoke-Git $path log -1 --oneline
    Read-Host "Press ENTER"
}

function Destroy-Feature($name) {
    $confirm = Read-Host "Type YES to destroy"
    if ($confirm -ne "YES") { return }

    Push-Location $WorktreeRoot
    git worktree remove $name
    Pop-Location
    Read-Host "Destroyed. Press ENTER"
}

function List-Worktrees {
    Clear-Host
    foreach ($key in $FeatureOrder) {
        $name   = $Features[$key]
        $exists = if (Test-WorktreeExists $name) { "Yes" } else { "No" }
        Write-Host ("  {0,-2} {1,-7} Exists: {2}" -f $key, $name, $exists)
    }
    Read-Host "Press ENTER"
}

# ---------- INTERACTIVE LOOP ----------
while ($true) {
    Show-FeatureMenu
    $key = (Read-Host ">").Trim().ToUpper()

    if ($key -eq "Q") { break }
    if ($key -eq "L") { List-Worktrees; continue }
    if (-not $Features.ContainsKey($key)) { continue }

    $name = $Features[$key]
    Show-ActionMenu $name
    $action = (Read-Host ">").Trim().ToUpper()

    switch ($action) {
        "S" { Start-Feature  $name }
        "F" { Finish-Feature $name }
        "D" { Destroy-Feature $name }
        "B" { continue }
        "Q" { exit }
    }
}
