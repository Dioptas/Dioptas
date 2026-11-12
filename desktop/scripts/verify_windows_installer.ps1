$ErrorActionPreference = 'Stop'
$metadataPath = Join-Path $PSScriptRoot '../artifacts/native-windows/latest.json'
$metadata = Get-Content $metadataPath -Raw | ConvertFrom-Json
$output = $metadata.output
$sourceRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$smokeScript = Join-Path $PSScriptRoot 'windows_installed_smoke.mjs'
$node = (Get-Command node).Source
$sevenZip = (Get-Command 7z).Source
$registry = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\Dioptas Desktop'
if (Test-Path $registry) { throw 'An existing Dioptas Desktop installation must not be replaced by this test' }
$temporary = Join-Path $env:RUNNER_TEMP ('Dioptas Installer Test ' + [guid]::NewGuid().ToString('N'))
$installation = Join-Path $temporary 'Installed App'
New-Item -ItemType Directory -Path $temporary | Out-Null
$originalDirectory = Get-Location
$receipts = @()
$installed = $false
try {
    Set-Location $temporary
    $installers = @()
    foreach ($build in $metadata.builds) {
        $file = Join-Path $temporary (Split-Path $build.installer -Leaf)
        Copy-Item $build.installer $file
        $hash = (Get-FileHash $file -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($hash -ne $build.sha256) { throw 'Installer checksum mismatch' }
        $signature = Get-AuthenticodeSignature $file
        if ($metadata.signing -eq 'authenticode') {
            if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Thumbprint -ne $metadata.signerThumbprint -or !$signature.TimeStamperCertificate) { throw 'Installer signing verification failed' }
        } elseif ($signature.Status -ne 'NotSigned') { throw "Unexpected test-installer signature status: $($signature.Status)" }
        $installers += @{ version = $build.version; file = $file; signing = $signature.Status.ToString() }
    }

    # Inspect the actual compressed payload, including the Microsoft-signed
    # offline runtime, rather than inferring it from the Tauri configuration.
    $extracted = Join-Path $temporary 'Extracted installer'
    & $sevenZip x $installers[0].file "-o$extracted" '-y' | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Cannot inspect NSIS payload' }
    $webviews = @(Get-ChildItem $extracted -Recurse -File | Where-Object { $_.Name -match 'WebView2.*\.exe$' -and $_.Length -gt 10MB })
    if ($webviews.Count -ne 1) { throw 'Expected one embedded offline WebView2 runtime installer' }
    $webviewSignature = Get-AuthenticodeSignature $webviews[0].FullName
    if ($webviewSignature.Status -ne 'Valid' -or $webviewSignature.SignerCertificate.Subject -notmatch 'Microsoft') { throw 'Embedded WebView2 installer is not trusted Microsoft software' }

    foreach ($build in $installers) {
        # NSIS requires the unquoted /D= destination to be the last argument.
        $process = Start-Process -FilePath $build.file -ArgumentList "/S /D=$installation" -Wait -PassThru
        if ($process.ExitCode -ne 0) { throw "Installer returned $($process.ExitCode)" }
        $installed = $true
        if (!(Test-Path (Join-Path $installation 'dioptas-desktop.exe'))) { throw 'Application was not installed' }
        $entry = Get-ItemProperty $registry
        if ($entry.DisplayVersion -ne $build.version) { throw 'Installed version registration is incorrect' }
        $links = @(Get-ChildItem ([Environment]::GetFolderPath('StartMenu')) -Filter '*.lnk' -Recurse | Where-Object { $_.BaseName -eq 'Dioptas Desktop' })
        if ($links.Count -lt 1) { throw 'Start menu shortcut is missing' }
        foreach ($name in @('dioptas-desktop.exe', 'dioptas-processor.exe')) {
            $signature = Get-AuthenticodeSignature (Join-Path $installation $name)
            if ($metadata.signing -eq 'authenticode' -and ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Thumbprint -ne $metadata.signerThumbprint -or !$signature.TimeStamperCertificate)) { throw "Application signing failed: $name" }
            if ($metadata.signing -eq 'unsigned-test' -and $signature.Status -ne 'NotSigned') { throw "Unexpected unsigned-test signature: $name" }
        }
        $report = Join-Path $temporary ("installed-$($build.version).json")
        & $node $smokeScript $installation $report
        if ($LASTEXITCODE -ne 0) { throw 'Installed processor/WebView2 checks failed' }
        $receipts += @{ version = $build.version; registration = $true; startMenuShortcut = $true; runtime = (Get-Content $report -Raw | ConvertFrom-Json) }
    }

    $settings = Join-Path ([Environment]::GetFolderPath('ApplicationData')) $metadata.identifier
    New-Item -ItemType Directory -Path $settings -Force | Out-Null
    $sentinel = Join-Path $settings 'installer-test-preserve.txt'
    Set-Content $sentinel 'preserve user settings'
    $uninstaller = Join-Path $installation 'uninstall.exe'
    $process = Start-Process -FilePath $uninstaller -ArgumentList '/S' -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw 'Uninstaller failed' }
    for ($i = 0; $i -lt 300; $i++) {
        if (!(Test-Path $registry) -and !(Test-Path (Join-Path $installation 'dioptas-desktop.exe'))) { break }
        Start-Sleep -Milliseconds 100
    }
    if ((Test-Path $registry) -or (Test-Path (Join-Path $installation 'dioptas-desktop.exe'))) { throw 'Uninstall left the application or registration behind' }
    foreach ($link in $links) { if (Test-Path $link.FullName) { throw 'Uninstall left a shortcut behind' } }
    if (!(Test-Path $sentinel)) { throw 'Silent uninstall removed user settings' }
    $installed = $false
    @{ ok = $true; published = $false; signing = $metadata.signing; offlineWebView2Payload = @{ bytes = $webviews[0].Length; signature = 'Microsoft; Valid' }; installedVersions = $receipts; upgrade = ($receipts.Count -gt 1); uninstall = $true; userSettingsPreserved = $true } |
        ConvertTo-Json -Depth 25 | Set-Content (Join-Path $output 'verification.json') -Encoding utf8
    Remove-Item $sentinel
} finally {
    if ($installed -and (Test-Path (Join-Path $installation 'uninstall.exe'))) {
        Start-Process -FilePath (Join-Path $installation 'uninstall.exe') -ArgumentList '/S' -Wait | Out-Null
    }
    Copy-Item (Join-Path $temporary '*.log') $output -ErrorAction SilentlyContinue
    Set-Location $originalDirectory
    Remove-Item $temporary -Recurse -Force -ErrorAction SilentlyContinue
}
