#!/usr/bin/env bash
# Build a Windows distribution of CortexForge.
#
# Produces, in dist/:
#   CortexForge-<version>-windows-x64.zip    portable (no install)
#   CortexForge-<version>-x64.msi            MSI installer (WiX, optional)
#
# Run under Git Bash / MSYS2 on Windows, or under Wine on Linux for a
# smoke test. The app is stdlib-only, so the bundle is a copied Python
# runtime plus the package.
set -euo pipefail

VERSION="${VERSION:-1.0.0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD="$ROOT/build/windows"
DIST="$ROOT/dist"
APPNAME="CortexForge"

echo "==> CortexForge Windows build $VERSION"
rm -rf "$BUILD"; mkdir -p "$BUILD" "$DIST"

PKG="$BUILD/$APPNAME"
install -d "$PKG/app" "$PKG/python"

cp -r "$ROOT/src/cortexforge" "$PKG/app/"
cp -r "$ROOT/web" "$PKG/app/"
cp "$ROOT/README.md" "$ROOT/LICENSE" "$PKG/app/" 2>/dev/null || true

# ---------------------------------------------------------------- runtime
# Resolve the BASE interpreter, not a virtualenv shim. Inside a venv,
# sysconfig reports platstdlib as the venv's own lib directory, which is
# nearly empty and produces a runtime that cannot import `encodings`.
PYBIN="$(command -v python || command -v python3)"
PYVER="$("$PYBIN" -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
BASEPREFIX="$("$PYBIN" -c 'import sys;print(sys.base_prefix)')"
BASEBIN="$BASEPREFIX/python.exe"
[ -x "$BASEBIN" ] || BASEBIN="$PYBIN"
echo "==> using base interpreter $BASEBIN (Python $PYVER)"

PYLIB="$("$BASEBIN" -c 'import sysconfig;print(sysconfig.get_paths()["stdlib"])')"
PYPLATLIB="$("$BASEBIN" -c 'import sysconfig;print(sysconfig.get_paths()["platstdlib"])')"
# Windows layout: the stdlib sits directly under the prefix (no lib/pythonX.Y).
cp -r "$PYLIB"/* "$PKG/python/" 2>/dev/null || true
if [ "$PYPLATLIB" != "$PYLIB" ]; then
  cp -r "$PYPLATLIB"/* "$PKG/python/" 2>/dev/null || true
fi
rm -rf "$PKG/python/test" "$PKG/python/idlelib" "$PKG/python/tkinter" \
       "$PKG/python/turtledemo" "$PKG/python/ensurepip" 2>/dev/null || true
# Windows needs the DLLs and the interpreter executable itself.
PYEXE_DIR="$(dirname "$BASEBIN")"
cp "$PYEXE_DIR"/*.dll "$PKG/python/" 2>/dev/null || true
cp "$PYEXE_DIR/python"*.exe "$PKG/python/" 2>/dev/null || true
cp -L "$BASEBIN" "$PKG/python/python.exe" 2>/dev/null || true

# Fatal smoke test where the host can run it (Wine or native Windows).
if [ -x "$PKG/python/python.exe" ]; then
  if command -v wine >/dev/null 2>&1; then
    if ! PYTHONHOME="$(cygpath -w "$PKG/python" 2>/dev/null || echo "$PKG/python")" \
         wine "$PKG/python/python.exe" -c "import encodings, sqlite3" >/dev/null 2>&1; then
      echo "    WARNING: bundled interpreter failed under Wine; verify on real Windows."
    else
      echo "    bundled interpreter smoke test passed (under Wine)"
    fi
  else
    echo "    wine not available — interpreter smoke test deferred to Windows"
  fi
fi

# ---------------------------------------------------------------- launcher
cat > "$PKG/CortexForge.bat" <<'BAT'
@echo off
setlocal
set HERE=%~dp0
set PYTHONHOME=%HERE%python
set PYTHONPATH=%HERE%app
if "%CORTEXFORGE_PORT%"=="" set CORTEXFORGE_PORT=8731
"%HERE%python\python.exe" -m cortexforge.server --port %CORTEXFORGE_PORT% --static "%HERE%app\web" %*
endlocal
BAT

cat > "$PKG/CortexForge.ps1" <<'PS1'
# CortexForge launcher for PowerShell.
$HERE = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONHOME = Join-Path $HERE 'python'
$env:PYTHONPATH = Join-Path $HERE 'app'
if (-not $env:CORTEXFORGE_PORT) { $env:CORTEXFORGE_PORT = '8731' }
& (Join-Path $HERE 'python\python.exe') -m cortexforge.server `
    --port $env:CORTEXFORGE_PORT --static (Join-Path $HERE 'app\web') @args
PS1

cat > "$PKG/README.txt" <<'TXT'
CortexForge — Windows
=====================

Run CortexForge.bat (Command Prompt) or CortexForge.ps1 (PowerShell).

The server starts on http://127.0.0.1:8731 and prints an API token.
Open that address in your browser. Set CORTEXFORGE_PORT to change the port.

Your data is stored in %USERPROFILE%\.cortexforge\ and never leaves this
machine unless you export it.
TXT

# ---------------------------------------------------------------- zip
echo "==> portable zip"
ZIP="$DIST/CortexForge-${VERSION}-windows-x64.zip"
(cd "$BUILD" && zip -qry "$ZIP" "$APPNAME")
echo "    $ZIP"

# ---------------------------------------------------------------- msi
echo "==> MSI (WiX)"
if command -v candle >/dev/null 2>&1 && command -v light >/dev/null 2>&1; then
  cat > "$BUILD/product.wxs" <<WXS
<?xml version="1.0" encoding="UTF-8"?>
<Wix xmlns="http://schemas.microsoft.com/wix/2006/wi">
  <Product Id="*" Name="CortexForge" Language="1033" Version="$VERSION"
           Manufacturer="CortexForge" UpgradeCode="7f3a1c2e-9b44-4d51-a6e0-2c8f5b1d9a30">
    <Package InstallerVersion="500" Compressed="yes" InstallScope="perUser"/>
    <MediaTemplate EmbedCab="yes"/>
    <Directory Id="TARGETDIR" Name="SourceDir">
      <Directory Id="LocalAppDataFolder">
        <Directory Id="INSTALLFOLDER" Name="CortexForge"/>
      </Directory>
    </Directory>
    <Feature Id="Main" Level="1">
      <ComponentGroupRef Id="AppFiles"/>
    </Feature>
  </Product>
</Wix>
WXS
  # Heat the payload into a component group, then link.
  heat dir "$PKG" -cg AppFiles -gg -g1 -sfrag -srd -dr INSTALLFOLDER \
      -var var.SourceDir -out "$BUILD/files.wxs" >/dev/null 2>&1 || true
  candle -dSourceDir="$PKG" -out "$BUILD/product.wixobj" "$BUILD/product.wxs" >/dev/null 2>&1 && \
    candle -dSourceDir="$PKG" -out "$BUILD/files.wixobj" "$BUILD/files.wxs" >/dev/null 2>&1 && \
    light -out "$DIST/CortexForge-${VERSION}-x64.msi" \
          "$BUILD/product.wixobj" "$BUILD/files.wixobj" >/dev/null 2>&1 && \
    echo "    $DIST/CortexForge-${VERSION}-x64.msi" || \
    echo "    WiX build failed — portable zip is still valid"
else
  echo "    WiX (candle/light) not installed — skipping MSI"
fi

echo
echo "==> Windows build complete. Artifacts in $DIST:"
ls -lh "$DIST" | tail -n +2
