# Download one SRTMGL1 v3 tile and its SRTMGL1N (NUM) file from NASA LP DAAC.
#
# Asks for your NASA Earthdata Login in this terminal. The password is not echoed,
# not written to the project, and the temporary credentials file is deleted at the end.
#
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\get_srtm_tile.ps1 [-Tile N38W111]

param([string]$Tile = "N38W111")

$ErrorActionPreference = "Stop"
if ($Tile -notmatch '^[NS]\d{2}[EW]\d{3}$') { throw "Tile must look like N38W111" }

$root = Split-Path -Parent $PSScriptRoot
$dest = Join-Path $root "data\raw\srtm"
New-Item -ItemType Directory -Force $dest | Out-Null

$base = "https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected"
$files = [ordered]@{
    "$Tile.SRTMGL1.hgt.zip"  = "$base/SRTMGL1.003/$Tile.SRTMGL1.hgt/$Tile.SRTMGL1.hgt.zip"
    "$Tile.SRTMGL1N.num.zip" = "$base/SRTMGL1N.003/$Tile.SRTMGL1N.num/$Tile.SRTMGL1N.num.zip"
}

$user = Read-Host "NASA Earthdata username"
$secure = Read-Host "NASA Earthdata password (not shown)" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
$netrc = Join-Path $env:TEMP ("edl_" + [guid]::NewGuid().ToString("N") + ".netrc")
$jar = Join-Path $env:TEMP ("edl_" + [guid]::NewGuid().ToString("N") + ".cookies")
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    [IO.File]::WriteAllText($netrc, "machine urs.earthdata.nasa.gov login $user password $plain`n")
    $plain = $null
    foreach ($name in $files.Keys) {
        $out = Join-Path $dest $name
        if (Test-Path $out) { Write-Host "$name already present - skipped (originals are never overwritten)"; continue }
        Write-Host "Downloading $name ..."
        $code = & curl.exe -sS -f -L --netrc-file $netrc -c $jar -b $jar --retry 3 -o "$out.part" -w "%{http_code}" $files[$name]
        if ($LASTEXITCODE -ne 0) {
            Remove-Item -ErrorAction SilentlyContinue "$out.part"
            throw "Download of $name failed (curl exit $LASTEXITCODE, HTTP $code). Check username/password, and that you can sign in at urs.earthdata.nasa.gov."
        }
        Move-Item "$out.part" $out
        Write-Host ("  OK: {0:N0} bytes" -f (Get-Item $out).Length)
    }
    Write-Host "Done. Files are in $dest"
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    Remove-Item -Force -ErrorAction SilentlyContinue $netrc, $jar
}
