param([Parameter(Mandatory=$true)][string]$Directory, [Parameter(Mandatory=$true)][string]$Version, [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9 ._-]+$')][string]$UserDataName)
$ErrorActionPreference = "Stop"
if ($env:GITHUB_ACTIONS -ne "true") { throw "Use only a disposable Windows CI runner" }
$command = Get-Command winget -ErrorAction SilentlyContinue
if (-not $command) {
    Install-Module Microsoft.WinGet.Client -Force -Repository PSGallery -Scope CurrentUser
    Import-Module Microsoft.WinGet.Client
    $repairArguments = @{}
    $repair = Get-Command Repair-WinGetPackageManager
    if ($repair.Parameters.ContainsKey("Latest")) { $repairArguments.Latest = $true }
    if ($repair.Parameters.ContainsKey("Force")) { $repairArguments.Force = $true }
    Repair-WinGetPackageManager @repairArguments
    $command = Get-Command winget -ErrorAction SilentlyContinue
}
if ($command) { $script:winget = $command.Source }
else {
    $package = Get-AppxPackage Microsoft.DesktopAppInstaller | Sort-Object Version -Descending | Select-Object -First 1
    $script:winget = Join-Path $package.InstallLocation "winget.exe"
}
function Invoke-WinGet([string[]]$Arguments) {
    & $script:winget @Arguments
    if ($LASTEXITCODE -ne 0) { throw "WinGet failed: $Arguments ($LASTEXITCODE)" }
}
function Find-Portable([string]$Identifier, [string]$Executable) {
    $root = Join-Path $env:LOCALAPPDATA "Microsoft/WinGet/Packages"
    $folders = @(Get-ChildItem $root -Directory | Where-Object Name -Like "$Identifier*")
    if ($folders.Count -ne 1) { throw "Ambiguous portable installation: $Identifier" }
    $path = Join-Path $folders[0].FullName $Executable
    if (-not (Test-Path $path)) { throw "Portable entry point missing: $path" }
    return $path
}
$identifiers = @("Cavazquez.PyAOServer", "Cavazquez.PyAOClient")
$packageNames = @{ "Cavazquez.PyAOServer" = "PyAO Server"; "Cavazquez.PyAOClient" = "PyAO Client" }
$env:PYAO_STATE_DIR = Join-Path $Directory "state"
$marker = Join-Path $env:APPDATA "Godot/app_userdata/$UserDataName/options.cfg"
New-Item -ItemType Directory -Force (Split-Path $marker) | Out-Null
$installed = @()
$primaryFailure = $null
$cleanupFailures = @()
try {
    Invoke-WinGet -Arguments @("settings", "--enable", "LocalManifestFiles")
    foreach ($identifier in $identifiers) {
        $baseline = Join-Path $Directory "baseline/$identifier"
        $current = Join-Path $Directory "current/$identifier"
        Invoke-WinGet -Arguments @("validate", "--manifest", $current)
        Invoke-WinGet -Arguments @("install", "--manifest", $baseline, "--scope", "user", "--silent", "--disable-interactivity", "--accept-package-agreements", "--accept-source-agreements")
        $installed += $identifier
    }
    $server = Find-Portable "Cavazquez.PyAOServer" "pyao-server.exe"
    & $server --check-resources
    if ($LASTEXITCODE -ne 0) { throw "Server resource check failed after installation" }
    $configuration = Join-Path $env:PYAO_STATE_DIR "config/server.toml"
    New-Item -ItemType Directory -Force (Split-Path $configuration) | Out-Null
    Set-Content -Path $configuration -Value '[server]
host = "127.0.0.1"

# preserve WinGet update' -Encoding utf8
    $configurationHash = (Get-FileHash $configuration -Algorithm SHA256).Hash
    Set-Content $marker "[channel_validation]`nkeep=`"PYAO_CHANNEL_UPGRADE_SENTINEL`"" -Encoding utf8
    foreach ($identifier in $identifiers) {
        Invoke-WinGet -Arguments @("upgrade", "--manifest", (Join-Path $Directory "current/$identifier"), "--silent", "--disable-interactivity", "--accept-package-agreements", "--accept-source-agreements")
    }
    $server = Find-Portable "Cavazquez.PyAOServer" "pyao-server.exe"
    $executedVersion = (& $server --version | Out-String).Trim()
    if (-not $executedVersion.EndsWith($Version)) { throw "Installed server version differs from the pair" }
    & $server --check-resources
    if ($LASTEXITCODE -ne 0) { throw "Server resource check failed after upgrade" }
    if ((Get-FileHash $configuration -Algorithm SHA256).Hash -ne $configurationHash) { throw "Upgrade changed configuration" }
    $client = Find-Portable "Cavazquez.PyAOClient" "pyao-client.exe"
    $process = Start-Process -FilePath $client -ArgumentList @("--audio-driver", "Dummy", "--rendering-method", "gl_compatibility", "--quit-after", "45") -PassThru -RedirectStandardOutput (Join-Path $Directory "client.log") -RedirectStandardError (Join-Path $Directory "client-error.log")
    if (-not $process.WaitForExit(90000)) {
        Stop-Process -Id $process.Id -Force
        throw "The installed client did not terminate"
    }
    if ($process.ExitCode -ne 0) { throw "The installed client failed" }
    foreach ($log in @("client.log", "client-error.log")) {
        $content = Get-Content (Join-Path $Directory $log) -Raw
        if ($content -match "SCRIPT ERROR:|ERROR:") { throw "Installed client logged an error: $log" }
    }
} catch {
    $primaryFailure = $_
} finally {
    foreach ($identifier in $installed) {
        try {
            # Local manifests have no public catalog identity yet. Match the
            # exact project display name in this disposable runner's registry.
            Invoke-WinGet -Arguments @("uninstall", "--name", $packageNames[$identifier], "--exact", "--silent", "--disable-interactivity", "--accept-source-agreements")
        } catch {
            $cleanupFailures += $_.Exception.Message
        }
    }
}
if ($null -ne $primaryFailure) { throw $primaryFailure }
if ($cleanupFailures.Count -gt 0) { throw ($cleanupFailures -join "`n") }
if ((Get-FileHash $configuration -Algorithm SHA256).Hash -ne $configurationHash) { throw "Uninstall changed configuration" }
if ((Get-Content $marker -Raw) -notmatch "PYAO_CHANNEL_UPGRADE_SENTINEL") { throw "Uninstall removed user preferences" }
$proof = @{passed=$true; installed=$true; upgraded=$true; removed=$true; configuration_preserved=$true; preferences_preserved=$true; user_data_preserved=$true; redis_installed_or_started=$false; version=$Version; local_manifest_fixture=$true}
$proof | ConvertTo-Json | Set-Content (Join-Path $Directory "winget-proof.json") -Encoding utf8
