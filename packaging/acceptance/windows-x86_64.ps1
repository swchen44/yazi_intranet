param(
    [Parameter(Mandatory = $true)]
    [string]$Archive,
    [string]$WorkDirectory = ""
)

$ErrorActionPreference = "Stop"
$archivePath = (Resolve-Path $Archive).Path
$ownedWorkDirectory = $false
if ([string]::IsNullOrWhiteSpace($WorkDirectory)) {
    $WorkDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("yazi-acceptance-" + [guid]::NewGuid().ToString("N"))
    $ownedWorkDirectory = $true
}

try {
    New-Item -ItemType Directory -Force -Path $WorkDirectory | Out-Null
    Expand-Archive -LiteralPath $archivePath -DestinationPath $WorkDirectory -Force
    $packageRoot = Get-ChildItem -LiteralPath $WorkDirectory -Directory | Select-Object -First 1
    if ($null -eq $packageRoot) { throw "package root not found" }

    $manifestPath = Join-Path $packageRoot.FullName "manifest.json"
    $manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
    if ($manifest.target -ne "x86_64-pc-windows-msvc") {
        throw "unexpected package target: $($manifest.target)"
    }

    $sumsPath = Join-Path $packageRoot.FullName "SHA256SUMS"
    foreach ($line in Get-Content -LiteralPath $sumsPath) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $parts = $line -split "  ", 2
        if ($parts.Count -ne 2) { throw "invalid SHA256SUMS line: $line" }
        $relative = $parts[1].Replace("/", [IO.Path]::DirectorySeparatorChar)
        $path = Join-Path $packageRoot.FullName $relative
        $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant()
        if ($actual -ne $parts[0].ToLowerInvariant()) {
            throw "checksum mismatch: $relative"
        }
    }

    $required = @(
        "bin\yazi.real.exe", "bin\ya.real.exe", "bin\yazi.cmd", "bin\ya.cmd",
        "bin\glow.exe", "bin\bat.exe", "bin\7zz.exe", "bin\ffmpeg.exe",
        "bin\ffprobe.exe", "bin\jq.exe", "bin\pdftoppm.exe", "bin\rg.exe",
        "bin\fd.exe", "bin\fzf.exe", "bin\zoxide.exe", "bin\chafa.exe", "runtime\bin\file.exe",
        "runtime\share\misc\magic.mgc", "runtime\imagemagick\magick.exe",
        "README.md", "manifest.json"
    )
    foreach ($relative in $required) {
        if (-not (Test-Path -LiteralPath (Join-Path $packageRoot.FullName $relative))) {
            throw "missing package file: $relative"
        }
    }

    $env:PATH = (Join-Path $packageRoot.FullName "bin") + ";" +
        (Join-Path $packageRoot.FullName "runtime\bin") + ";" +
        (Join-Path $packageRoot.FullName "runtime\imagemagick") + ";" + $env:PATH
    & (Join-Path $packageRoot.FullName "bin\yazi.real.exe") --version
    & (Join-Path $packageRoot.FullName "bin\ya.real.exe") --version
    & (Join-Path $packageRoot.FullName "bin\glow.exe") --version
    & (Join-Path $packageRoot.FullName "bin\bat.exe") --version
    & (Join-Path $packageRoot.FullName "bin\7zz.exe") i
    & (Join-Path $packageRoot.FullName "bin\ffmpeg.exe") -version
    & (Join-Path $packageRoot.FullName "bin\ffprobe.exe") -version
    & (Join-Path $packageRoot.FullName "bin\jq.exe") --version
    & (Join-Path $packageRoot.FullName "bin\pdftoppm.exe") -h
    & (Join-Path $packageRoot.FullName "bin\chafa.exe") --version
    & (Join-Path $packageRoot.FullName "bin\rg.exe") --version
    & (Join-Path $packageRoot.FullName "bin\fd.exe") --version
    & (Join-Path $packageRoot.FullName "bin\fzf.exe") --version
    & (Join-Path $packageRoot.FullName "bin\zoxide.exe") --version
    & (Join-Path $packageRoot.FullName "runtime\bin\file.exe") --version
    & (Join-Path $packageRoot.FullName "runtime\imagemagick\magick.exe") --version
    Write-Output "Windows archive/hash/helper acceptance passed."
    Write-Output "Run the separate Windows Terminal/Zellij/image protocol matrix before release."
}
finally {
    if ($ownedWorkDirectory -and (Test-Path -LiteralPath $WorkDirectory)) {
        Remove-Item -Recurse -Force -LiteralPath $WorkDirectory
    }
}
