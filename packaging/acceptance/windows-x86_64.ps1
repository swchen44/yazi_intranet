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
    $layout = if ([string]::IsNullOrWhiteSpace($manifest.layout)) { "standard" } else { $manifest.layout }
    if ($layout -notin @("standard", "flat-bin")) {
        throw "unexpected package layout: $layout"
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

    $flat = $layout -eq "flat-bin"
    $commandRoot = if ($flat) { $packageRoot.FullName } else { Join-Path $packageRoot.FullName "bin" }
    $fileRoot = if ($flat) { $packageRoot.FullName } else { Join-Path $packageRoot.FullName "runtime\bin" }
    $magicPath = if ($flat) { Join-Path $packageRoot.FullName "data\file\magic.mgc" } else { Join-Path $packageRoot.FullName "runtime\share\misc\magic.mgc" }
    $imageDataRoot = if ($flat) { Join-Path $packageRoot.FullName "data\imagemagick" } else { Join-Path $packageRoot.FullName "runtime\imagemagick" }

    $required = @(
        (Join-Path $commandRoot "yazi.real.exe"), (Join-Path $commandRoot "ya.real.exe"),
        (Join-Path $commandRoot "yazi.cmd"), (Join-Path $commandRoot "ya.cmd"),
        $magicPath, (Join-Path $packageRoot.FullName "config\yazi.toml"),
        (Join-Path $packageRoot.FullName "config\README.md"),
        (Join-Path $packageRoot.FullName "README.md"),
        (Join-Path $packageRoot.FullName "manifest.json")
    )
    foreach ($relative in @($manifest.yazi.files)) {
        $required += Join-Path $packageRoot.FullName ($relative.Replace("/", [IO.Path]::DirectorySeparatorChar))
    }
    foreach ($helperProperty in $manifest.helpers.PSObject.Properties) {
        if ($helperProperty.Value.status -ne "included") { continue }
        foreach ($relative in @($helperProperty.Value.files)) {
            $required += Join-Path $packageRoot.FullName ($relative.Replace("/", [IO.Path]::DirectorySeparatorChar))
        }
    }
    $required = $required | Sort-Object -Unique
    foreach ($relative in $required) {
        if (-not (Test-Path -LiteralPath $relative)) {
            throw "missing package file: $relative"
        }
    }
    if ($flat) {
        if (Test-Path -LiteralPath (Join-Path $packageRoot.FullName "bin")) {
            throw "flat package must not contain bin directory"
        }
        foreach ($path in Get-ChildItem -LiteralPath $packageRoot.FullName -Recurse -File) {
            $relative = $path.FullName.Substring($packageRoot.FullName.Length + 1)
            if ($relative -match '^(data|config|completions|licenses)\\' -and
                $path.Extension.ToLowerInvariant() -in @(".exe", ".cmd", ".bat", ".dll")) {
                throw "flat package executable or DLL is below a data directory: $relative"
            }
        }
    }

    $configText = Get-Content -Raw -LiteralPath (Join-Path $packageRoot.FullName "config\yazi.toml")
    if ($configText -notmatch "\[preview\]" -or $configText -notmatch 'wrap = "yes"') {
        throw "package config preview defaults are missing"
    }
    if ($configText -notmatch "md-bat" -or $configText -notmatch "md-glow") {
        throw "package config Markdown openers are missing"
    }

    $pathEntries = if ($flat) {
        @($packageRoot.FullName)
    } else {
        @(
            (Join-Path $packageRoot.FullName "bin"),
            (Join-Path $packageRoot.FullName "runtime\bin"),
            (Join-Path $packageRoot.FullName "runtime\imagemagick")
        )
    }
    $env:PATH = ($pathEntries + @($env:PATH)) -join ";"
    $env:YAZI_FILE_ONE = Join-Path $fileRoot "file.exe"
    $env:MAGIC = $magicPath
    $env:MAGICK_CONFIGURE_PATH = $imageDataRoot
    & (Join-Path $commandRoot "yazi.real.exe") --version
    & (Join-Path $commandRoot "ya.real.exe") --version
    $magickPath = if ($flat) { Join-Path $commandRoot "magick.exe" } else { Join-Path $imageDataRoot "magick.exe" }
    $commands = @(
        @{ Path = (Join-Path $commandRoot "glow.exe"); Arguments = @("--version") },
        @{ Path = (Join-Path $commandRoot "bat.exe"); Arguments = @("--version") },
        @{ Path = (Join-Path $commandRoot "7zz.exe"); Arguments = @("i") },
        @{ Path = (Join-Path $commandRoot "ffmpeg.exe"); Arguments = @("-version") },
        @{ Path = (Join-Path $commandRoot "ffprobe.exe"); Arguments = @("-version") },
        @{ Path = (Join-Path $commandRoot "jq.exe"); Arguments = @("--version") },
        @{ Path = (Join-Path $commandRoot "pdftoppm.exe"); Arguments = @("-h") },
        @{ Path = (Join-Path $commandRoot "chafa.exe"); Arguments = @("--version") },
        @{ Path = (Join-Path $commandRoot "rg.exe"); Arguments = @("--version") },
        @{ Path = (Join-Path $commandRoot "fd.exe"); Arguments = @("--version") },
        @{ Path = (Join-Path $commandRoot "fzf.exe"); Arguments = @("--version") },
        @{ Path = (Join-Path $commandRoot "zoxide.exe"); Arguments = @("--version") },
        @{ Path = (Join-Path $fileRoot "file.exe"); Arguments = @("--version") },
        @{ Path = $magickPath; Arguments = @("--version") }
    )
    foreach ($command in $commands) {
        $path = $command.Path
        if (Test-Path -LiteralPath $path) {
            & $path @($command.Arguments)
        }
    }
    Write-Output "Windows archive/hash/helper acceptance passed."
    Write-Output "Run the separate Windows Terminal/Zellij/image protocol matrix before release."
}
finally {
    if ($ownedWorkDirectory -and (Test-Path -LiteralPath $WorkDirectory)) {
        Remove-Item -Recurse -Force -LiteralPath $WorkDirectory
    }
}
