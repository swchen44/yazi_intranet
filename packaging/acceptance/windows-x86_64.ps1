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
    foreach ($pluginProperty in $manifest.plugins.PSObject.Properties) {
        foreach ($relative in @($pluginProperty.Value.files)) {
            $required += Join-Path $packageRoot.FullName ($relative.Replace("/", [IO.Path]::DirectorySeparatorChar))
        }
    }
    $required = $required | Sort-Object -Unique
    foreach ($relative in $required) {
        if (-not (Test-Path -LiteralPath $relative)) {
            throw "missing package file: $relative"
        }
    }
    foreach ($name in @("ffmpeg.exe", "ffprobe.exe")) {
        if (Test-Path -LiteralPath (Join-Path $commandRoot $name)) {
            throw "Windows package unexpectedly contains $name"
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
    if ($configText -notmatch "MediaInfo.exe" -or $configText -match "ffprobe") {
        throw "package config media metadata opener is incorrect"
    }
    if ($manifest.plugins.PSObject.Properties.Count -gt 0) {
        foreach ($relative in @("config\keymap.toml", "config\init.lua", "config\package.toml")) {
            if (-not (Test-Path -LiteralPath (Join-Path $packageRoot.FullName $relative))) {
                throw "missing plugin config: $relative"
            }
        }
        if ($configText -notmatch "piper -- chafa" -or $configText -notmatch 'run = "duckdb"') {
            throw "plugin preview rules are missing"
        }
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
        @{ Path = (Join-Path $commandRoot "MediaInfo.exe"); Arguments = @("--Version") },
        @{ Path = (Join-Path $commandRoot "jq.exe"); Arguments = @("--version") },
        @{ Path = (Join-Path $commandRoot "pdftoppm.exe"); Arguments = @("-h") },
        @{ Path = (Join-Path $commandRoot "chafa.exe"); Arguments = @("--version") },
        @{ Path = (Join-Path $commandRoot "rg.exe"); Arguments = @("--version") },
        @{ Path = (Join-Path $commandRoot "fd.exe"); Arguments = @("--version") },
        @{ Path = (Join-Path $commandRoot "fzf.exe"); Arguments = @("--version") },
        @{ Path = (Join-Path $commandRoot "zoxide.exe"); Arguments = @("--version") },
        @{ Path = (Join-Path $commandRoot "duckdb.exe"); Arguments = @("--version") },
        @{ Path = (Join-Path $commandRoot "lazygit.exe"); Arguments = @("--version") },
        @{ Path = (Join-Path $fileRoot "sh.exe"); Arguments = @("--version") },
        @{ Path = (Join-Path $fileRoot "tar.exe"); Arguments = @("--version") },
        @{ Path = (Join-Path $fileRoot "file.exe"); Arguments = @("--version") },
        @{ Path = $magickPath; Arguments = @("--version") }
    )
    foreach ($command in $commands) {
        $path = $command.Path
        if (Test-Path -LiteralPath $path) {
            & $path @($command.Arguments)
            if ($path -match '(duckdb|lazygit|sh|tar|MediaInfo)\.exe$' -and $LASTEXITCODE -ne 0) {
                throw "helper command failed ($LASTEXITCODE): $path"
            }
        }
    }
    if ($manifest.helpers.tree.status -eq "included") {
        $portableTools = @("ls", "cat", "less", "head", "tail", "wc", "du", "stat", "grep", "sed", "awk", "cut", "tr", "uniq", "xargs", "diff", "cygpath", "realpath", "sha256sum", "find", "sort", "tree")
        foreach ($name in $portableTools) {
            $expected = Join-Path $commandRoot "$name.exe"
            if (-not (Test-Path -LiteralPath $expected)) { throw "missing bundled command: $expected" }
            $resolved = (Get-Command "$name.exe" -CommandType Application -ErrorAction Stop).Source
            if ($resolved -ne $expected) { throw "PATH selects $resolved instead of $expected" }
            & $expected --version | Out-Null
            if ($LASTEXITCODE -ne 0) { throw "bundled command failed ($LASTEXITCODE): $expected" }
        }
        $fixtureDirectory = Join-Path $WorkDirectory "tree 測試 folder"
        $childDirectory = Join-Path $fixtureDirectory "nested"
        New-Item -ItemType Directory -Force -Path $childDirectory | Out-Null
        Set-Content -LiteralPath (Join-Path $childDirectory "note.txt") -Value "fixture" -Encoding utf8
        $tree = Join-Path $commandRoot "tree.exe"
        $find = Join-Path $commandRoot "find.exe"
        $sort = Join-Path $commandRoot "sort.exe"
        $cygpath = Join-Path $commandRoot "cygpath.exe"
        $treeOutput = & $tree -a -L 2 $fixtureDirectory
        if ($LASTEXITCODE -ne 0 -or ($treeOutput -join "`n") -notmatch "note\.txt") { throw "tree.exe failed on Windows path with spaces and Unicode" }
        $posixPath = & $cygpath -u $fixtureDirectory
        if ($LASTEXITCODE -ne 0) { throw "cygpath.exe failed" }
        & $tree -a -L 2 $posixPath | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "tree.exe failed on MSYS path" }
        $found = & $find $fixtureDirectory -type f -name note.txt
        if ($LASTEXITCODE -ne 0 -or ($found -join "`n") -notmatch "note\.txt") { throw "find.exe failed on Windows path" }
        $sorted = @("zebra", "alpha") | & $sort
        if ($LASTEXITCODE -ne 0 -or ($sorted -join ",") -ne "alpha,zebra") { throw "sort.exe did not use GNU sort behavior" }
    }
    if ($manifest.plugins.PSObject.Properties.Count -gt 0) {
        $sh = Join-Path $fileRoot "sh.exe"
        $tar = Join-Path $fileRoot "tar.exe"
        $duckdb = Join-Path $commandRoot "duckdb.exe"
        foreach ($path in @($sh, $tar, $duckdb)) {
            if (-not (Test-Path -LiteralPath $path)) { throw "missing plugin helper: $path" }
        }
        $fixture = Join-Path $WorkDirectory "plugin-fixture.csv"
        Set-Content -LiteralPath $fixture -Value @("name,value", "test,42") -Encoding utf8
        & $sh -c 'test -f "$1"' sh $fixture
        if ($LASTEXITCODE -ne 0) { throw "bundled sh.exe failed" }
        & $tar --version | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "bundled tar.exe failed" }
        & $duckdb -c "SELECT count(*) FROM read_csv_auto('$($fixture.Replace("'", "''"))')" | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "bundled duckdb.exe failed" }
    }
    Write-Output "Windows archive/hash/helper acceptance passed."
    Write-Output "Run the separate Windows Terminal/Zellij/image protocol matrix before release."
}
finally {
    if ($ownedWorkDirectory -and (Test-Path -LiteralPath $WorkDirectory)) {
        Remove-Item -Recurse -Force -LiteralPath $WorkDirectory
    }
}
