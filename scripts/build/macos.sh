#!/usr/bin/env bash
# Build a macOS distribution of CortexForge.
#
# Produces, in dist/:
#   CortexForge.app                    double-clickable app bundle
#   CortexForge-<version>.dmg          disk image
#   CortexForge-<version>-macos.zip    portable archive
#
# Run on macOS. Codesigning and notarisation are performed only when the
# relevant environment variables are present, so the script is safe to run
# unsigned for local testing.
set -euo pipefail

VERSION="${VERSION:-1.0.0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD="$ROOT/build/macos"
DIST="$ROOT/dist"
APPNAME="CortexForge"
BUNDLE="$BUILD/$APPNAME.app"

# Signing identity: set CODESIGN_IDENTITY to sign, leave unset to skip.
CODESIGN_IDENTITY="${CODESIGN_IDENTITY:-}"
# Notarisation: set APPLE_ID, APPLE_TEAM_ID, APPLE_APP_PASSWORD to notarise.
APPLE_ID="${APPLE_ID:-}"
APPLE_TEAM_ID="${APPLE_TEAM_ID:-}"
APPLE_APP_PASSWORD="${APPLE_APP_PASSWORD:-}"

echo "==> CortexForge macOS build $VERSION"
rm -rf "$BUILD"; mkdir -p "$BUILD" "$DIST"

MACOS="$BUNDLE/Contents/MacOS"
RES="$BUNDLE/Contents/Resources"
APPDIR="$RES/app"
install -d "$MACOS" "$RES" "$APPDIR"

# ---------------------------------------------------------------- payload
cp -r "$ROOT/src/cortexforge" "$APPDIR/"
cp -r "$ROOT/web" "$APPDIR/"
cp "$ROOT/README.md" "$ROOT/LICENSE" "$APPDIR/" 2>/dev/null || true

# Bundle the Python runtime. Resolve the BASE interpreter, not a virtualenv
# shim: inside a venv, sysconfig reports platstdlib as the venv's own lib
# directory, which is nearly empty and yields a runtime that cannot import
# `encodings`.
PYBIN="$(command -v python3)"
PYVER="$("$PYBIN" -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
BASEPREFIX="$("$PYBIN" -c 'import sys;print(sys.base_prefix)')"
BASEBIN="$BASEPREFIX/bin/python$PYVER"
[ -x "$BASEBIN" ] || BASEBIN="$BASEPREFIX/bin/python3"
[ -x "$BASEBIN" ] || BASEBIN="$PYBIN"
echo "==> using base interpreter $BASEBIN (Python $PYVER)"

PYLIB="$("$BASEBIN" -c 'import sysconfig;print(sysconfig.get_paths()["stdlib"])')"
PYPLATLIB="$("$BASEBIN" -c 'import sysconfig;print(sysconfig.get_paths()["platstdlib"])')"
PYEXE="$("$BASEBIN" -c 'import sys;print(sys.executable)')"
# The stdlib must land at <prefix>/lib/python<X.Y>/ where the interpreter
# looks for it; a flat copy produces "No module named 'encodings'".
STDLIB_DEST="$APPDIR/python/lib/python$PYVER"
install -d "$STDLIB_DEST" "$APPDIR/python/bin"
cp -r "$PYLIB"/* "$STDLIB_DEST/" 2>/dev/null || true
if [ "$PYPLATLIB" != "$PYLIB" ]; then
  cp -r "$PYPLATLIB"/* "$STDLIB_DEST/" 2>/dev/null || true
fi
rm -rf "$STDLIB_DEST/test" "$STDLIB_DEST/idlelib" \
       "$STDLIB_DEST/tkinter" "$STDLIB_DEST/turtledemo" \
       "$STDLIB_DEST/ensurepip" 2>/dev/null || true
cp -L "$PYEXE" "$APPDIR/python/bin/python3"
chmod 0755 "$APPDIR/python/bin/python3"

# Fatal smoke test: an artifact whose interpreter cannot start is not shippable.
if ! PYTHONHOME="$APPDIR/python" "$APPDIR/python/bin/python3" \
     -c 'import encodings, json, sqlite3, http.server' >/dev/null 2>&1; then
  echo "    ERROR: bundled interpreter cannot import its own stdlib."
  echo "           Aborting rather than shipping a bundle that will not run."
  exit 1
fi
echo "    bundled interpreter smoke test passed"

# ---------------------------------------------------------------- launcher
cat > "$MACOS/$APPNAME" <<'LAUNCHER'
#!/bin/sh
# CortexForge launcher for macOS.
set -e
HERE="$(cd "$(dirname "$0")/../Resources/app" && pwd)"
export PYTHONHOME="$HERE/python"
export PYTHONPATH="$HERE"
PORT="${CORTEXFORGE_PORT:-8731}"
exec "$HERE/python/bin/python3" -m cortexforge.server \
    --port "$PORT" --static "$HERE/web" "$@"
LAUNCHER
chmod 0755 "$MACOS/$APPNAME"

# ---------------------------------------------------------------- Info.plist
cat > "$BUNDLE/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>$APPNAME</string>
  <key>CFBundleDisplayName</key><string>CortexForge</string>
  <key>CFBundleIdentifier</key><string>io.github.ugwanjegrandson2010.cortexforge</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleExecutable</key><string>$APPNAME</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>LSApplicationCategoryType</key><string>public.app-category.education</string>
  <key>NSHumanReadableCopyright</key><string>MIT Licensed</string>
</dict>
</plist>
PLIST

# ---------------------------------------------------------------- icon
# Generate an .icns if the tooling is available; otherwise ship the SVG.
cat > "$RES/icon.svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <rect width="256" height="256" rx="48" fill="#0e1116"/>
  <circle cx="128" cy="128" r="72" fill="none" stroke="#4c8dff" stroke-width="10"/>
  <path d="M128 56v72l52 30" stroke="#4c8dff" stroke-width="10"
        fill="none" stroke-linecap="round"/>
  <circle cx="128" cy="128" r="12" fill="#3fb950"/>
</svg>
SVG
if command -v iconutil >/dev/null 2>&1 && command -v sips >/dev/null 2>&1; then
  ICONSET="$BUILD/icon.iconset"; mkdir -p "$ICONSET"
  if command -v rsvg-convert >/dev/null 2>&1; then
    rsvg-convert -w 1024 -h 1024 "$RES/icon.svg" -o "$BUILD/icon1024.png"
    for s in 16 32 64 128 256 512 1024; do
      sips -z $s $s "$BUILD/icon1024.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null
    done
    iconutil -c icns "$ICONSET" -o "$RES/icon.icns" 2>/dev/null || true
  fi
fi

# ---------------------------------------------------------------- signing
if [ -n "$CODESIGN_IDENTITY" ]; then
  echo "==> codesigning"
  codesign --force --deep --options runtime \
      --sign "$CODESIGN_IDENTITY" "$BUNDLE"
  codesign --verify --verbose=2 "$BUNDLE"
else
  echo "==> CODESIGN_IDENTITY unset — skipping codesign (local build)"
fi

# ---------------------------------------------------------------- zip
echo "==> zip"
ZIP="$DIST/CortexForge-${VERSION}-macos.zip"
(cd "$BUILD" && zip -qry "$ZIP" "$APPNAME.app")
echo "    $ZIP"

# ---------------------------------------------------------------- dmg
echo "==> dmg"
if command -v hdiutil >/dev/null 2>&1; then
  DMG="$DIST/CortexForge-${VERSION}.dmg"
  rm -f "$DMG"
  hdiutil create -volname "$APPNAME" -srcfolder "$BUNDLE" \
      -ov -format UDZO "$DMG" >/dev/null
  if [ -n "$CODESIGN_IDENTITY" ]; then
    codesign --force --sign "$CODESIGN_IDENTITY" "$DMG"
  fi
  echo "    $DMG"

  # ------------------------------------------------------------ notarise
  if [ -n "$APPLE_ID" ] && [ -n "$APPLE_TEAM_ID" ] && [ -n "$APPLE_APP_PASSWORD" ]; then
    echo "==> notarising (this takes several minutes)"
    xcrun notarytool submit "$DMG" \
        --apple-id "$APPLE_ID" \
        --team-id "$APPLE_TEAM_ID" \
        --password "$APPLE_APP_PASSWORD" \
        --wait
    xcrun stapler staple "$DMG"
    echo "    notarised and stapled"
  else
    echo "    APPLE_ID/APPLE_TEAM_ID/APPLE_APP_PASSWORD unset — skipping notarisation"
  fi
else
  echo "    hdiutil not available — skipping dmg"
fi

echo
echo "==> macOS build complete. Artifacts in $DIST:"
ls -lh "$DIST" | tail -n +2
