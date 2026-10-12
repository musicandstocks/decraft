@echo off
setlocal
title Decraft - Legacy client installer
set "DECRAFT_LAUNCH_ROOT=%~dp0"
cd /d "%DECRAFT_LAUNCH_ROOT%"
echo Preparing the native Legacy Console client...
echo The first install downloads a local Python runtime for verified archive assembly.
echo No administrator access or Java installation is required.
powershell.exe -NoLogo -NoProfile -Command ^
  "$ErrorActionPreference='Stop'; try {" ^
  "$root=$env:DECRAFT_LAUNCH_ROOT; $dir=Join-Path $root '.decraft-windows\python'; $python=Join-Path $dir 'tools\python.exe';" ^
  "if (-not (Test-Path -LiteralPath $python)) {" ^
  "if (Test-Path -LiteralPath $dir) { throw 'Existing incomplete Python runtime is preserved. Rename .decraft-windows\python and try again.' };" ^
  "$cache=Join-Path $root '.decraft-windows'; [IO.Directory]::CreateDirectory($cache) | Out-Null;" ^
  "$tmp=Join-Path $cache ([guid]::NewGuid().ToString()); [IO.Directory]::CreateDirectory($tmp) | Out-Null;" ^
  "try { $zip=Join-Path $tmp 'python.zip'; [Net.ServicePointManager]::SecurityProtocol=[Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12;" ^
  "Write-Host 'Downloading verified Windows Python (17 MB)...';" ^
  "Invoke-WebRequest -UseBasicParsing -Uri 'https://api.nuget.org/v3-flatcontainer/python/3.11.9/python.3.11.9.nupkg' -OutFile $zip;" ^
  "if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash -ne '9283876d58c017e0e846f95b490da3bca0fc0a6ee1134b2870677cfb7eec3c67') { throw 'Python download failed SHA-256 verification' };" ^
  "$expanded=Join-Path $tmp 'expanded'; Add-Type -AssemblyName System.IO.Compression.FileSystem; [IO.Compression.ZipFile]::ExtractToDirectory($zip,$expanded);" ^
  "Move-Item -LiteralPath $expanded -Destination $dir;" ^
  "} finally { if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Recurse -Force } } };" ^
  "if ((Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash -ne '5f7b89a612c9b8af1d6456cdfcd1dbe5ca630849e79aebced9bee9a6694952ec') { throw 'Local Python executable differs from the verified runtime. Existing files are preserved.' };" ^
  "& $python (Join-Path $root 'tools\install_legacy.py'); exit $LASTEXITCODE" ^
  "} catch { Write-Host ('LEGACY INSTALL ERROR: ' + $_.Exception.Message); exit 1 }"
set "DECRAFT_LAUNCH_EXIT=%ERRORLEVEL%"
echo.
if not "%DECRAFT_LAUNCH_EXIT%"=="0" echo Launch failed. The error is above; game logs are under Decraft-Legacy\runtime\legacy\legacy-logs.
echo Press any key to close this launcher window.
pause >nul
exit /b %DECRAFT_LAUNCH_EXIT%
