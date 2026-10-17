#!/usr/bin/env bash
# Build a self-contained Linux distribution of CortexForge.
#
# Produces, in dist/:
#   cortexforge-<version>-linux-x86_64.tar.gz   portable tarball
#   cortexforge-<version>-x86_64.AppImage       single-file executable
#   cortexforge_<version>_amd64.deb             Debian/Ubuntu
#   cortexforge-<version>-1.x86_64.rpm          Fedora/RHEL/SUSE
#   PKGBUILD                                    Arch (build with makepkg)
#   cortexforge-<version>.flatpak               Flatpak bundle
#
# Every artifact embeds a private Python runtime, so the target machine needs
# nothing installed — no Python, no pip, no system packages.
set -euo pipefail

VERSION="${VERSION:-1.0.0}"
ARCH="$(uname -m)"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD="$ROOT/build/linux"
DIST="$ROOT/dist"
APPNAME="cortexforge"
APPDIR="$BUILD/AppDir"

echo "==> CortexForge Linux build $VERSION ($ARCH)"
rm -rf "$BUILD"; mkdir -p "$BUILD" "$DIST"

# ---------------------------------------------------------------- runtime
# Bundle the Python standard library AND the interpreter, so the target
# machine needs no Python at all.
#
# Critical: resolve the BASE interpreter, not a virtualenv shim. Inside a
# venv, sysconfig reports platstdlib as the venv's own lib directory, which
# contains almost nothing — bundling from there yields a runtime that fails
# with "No module named 'encodings'". sys.base_prefix is the real install.
PYBIN="$(command -v python3)"
PYVER="$("$PYBIN" -c 'import sys;print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
BASEPREFIX="$("$PYBIN" -c 'import sys;print(sys.base_prefix)')"
BASEBIN="$BASEPREFIX/bin/python$PYVER"
[ -x "$BASEBIN" ] || BASEBIN="$BASEPREFIX/bin/python3"
[ -x "$BASEBIN" ] || BASEBIN="$PYBIN"
echo "==> using base interpreter $BASEBIN (Python $PYVER, prefix $BASEPREFIX)"

PYLIB="$("$BASEBIN" -c 'import sysconfig;print(sysconfig.get_paths()["stdlib"])')"
PYPLATLIB="$("$BASEBIN" -c 'import sysconfig;print(sysconfig.get_paths()["platstdlib"])')"
PYEXE="$("$BASEBIN" -c 'import sys;print(sys.executable)')"
# The stdlib must land where the interpreter looks for it:
#   <prefix>/lib/python<X.Y>/
# Copying it flat into <prefix>/ produces a runtime that cannot import
# `encodings`, because the interpreter searches <prefix>/lib/python<X.Y>.
STDLIB_DEST="$APPDIR/usr/lib/$APPNAME/python/lib/python$PYVER"
install -d "$STDLIB_DEST" "$APPDIR/usr/lib/$APPNAME/python/bin"
cp -r "$PYLIB"/* "$STDLIB_DEST/" 2>/dev/null || true
# platstdlib (lib-dynload) can live outside stdlib on some distributions.
if [ "$PYPLATLIB" != "$PYLIB" ]; then
  cp -r "$PYPLATLIB"/* "$STDLIB_DEST/" 2>/dev/null || true
fi
rm -rf "$STDLIB_DEST/test" \
       "$STDLIB_DEST/idlelib" \
       "$STDLIB_DEST/tkinter" \
       "$STDLIB_DEST/turtledemo" \
       "$STDLIB_DEST/ensurepip" 2>/dev/null || true

# The interpreter binary itself. Resolve symlinks so we copy the real file.
cp -L "$PYEXE" "$APPDIR/usr/lib/$APPNAME/python/bin/python3"
chmod 0755 "$APPDIR/usr/lib/$APPNAME/python/bin/python3"
# Shared library the interpreter links against, if it is not statically linked.
PYSO="$(ldd "$PYEXE" 2>/dev/null | awk '/libpython/ {print $3}' | head -1)"
if [ -n "$PYSO" ]; then
  cp -L "$PYSO" "$APPDIR/usr/lib/$APPNAME/python/bin/" 2>/dev/null || true
fi

# ---------------------------------------------------------------- payload
install -d "$APPDIR/usr/lib/$APPNAME" "$APPDIR/usr/bin" \
           "$APPDIR/usr/share/applications" "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp -r "$ROOT/src/cortexforge" "$APPDIR/usr/lib/$APPNAME/"
cp -r "$ROOT/web" "$APPDIR/usr/lib/$APPNAME/"
cp "$ROOT/README.md" "$ROOT/LICENSE" "$APPDIR/usr/lib/$APPNAME/" 2>/dev/null || true

# Verify the bundled interpreter actually starts. This is the check that
# decides whether the artifact is shippable at all, so it is fatal: a bundle
# whose interpreter cannot import `encodings` is not a bundle.
if ! PYTHONHOME="$APPDIR/usr/lib/$APPNAME/python" \
     "$APPDIR/usr/lib/$APPNAME/python/bin/python3" \
     -c 'import encodings, json, sqlite3, http.server' >/dev/null 2>&1; then
  echo "    ERROR: bundled interpreter cannot import its own stdlib."
  echo "           The artifact would not run. Aborting rather than shipping it."
  echo "           Check that the build used the BASE interpreter, not a venv shim."
  exit 1
fi
echo "    bundled interpreter smoke test passed"

cat > "$APPDIR/usr/bin/$APPNAME" <<'LAUNCHER'
#!/bin/sh
# CortexForge launcher: starts the local server using the bundled runtime.
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
APP="$HERE/lib/cortexforge"
export PYTHONHOME="$APP/python"
export PYTHONPATH="$APP"
PORT="${CORTEXFORGE_PORT:-8731}"
exec "$APP/python/bin/python3" -m cortexforge.server \
    --port "$PORT" --static "$APP/web" "$@"
LAUNCHER
chmod 0755 "$APPDIR/usr/bin/$APPNAME"

cat > "$APPDIR/$APPNAME.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=CortexForge
Comment=Adaptive learning system with honest feedback
Exec=$APPNAME
Terminal=true
Categories=Education;Science;
Keywords=learning;study;memory;spaced-repetition;
DESKTOP
cp "$APPDIR/$APPNAME.desktop" "$APPDIR/usr/share/applications/"

# Icon: a simple generated SVG->PNG is optional; ship the SVG as the source.
cat > "$APPDIR/usr/share/icons/hicolor/256x256/apps/$APPNAME.svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256">
  <rect width="256" height="256" rx="48" fill="#0e1116"/>
  <circle cx="128" cy="128" r="72" fill="none" stroke="#4c8dff" stroke-width="10"/>
  <path d="M128 56v72l52 30" stroke="#4c8dff" stroke-width="10"
        fill="none" stroke-linecap="round"/>
  <circle cx="128" cy="128" r="12" fill="#3fb950"/>
</svg>
SVG

# ---------------------------------------------------------------- tarball
echo "==> tarball"
TARBALL="$DIST/${APPNAME}-${VERSION}-linux-${ARCH}.tar.gz"
tar -C "$BUILD" -czf "$TARBALL" AppDir
echo "    $TARBALL"

# ---------------------------------------------------------------- appimage
echo "==> AppImage"
if command -v appimagetool >/dev/null 2>&1; then
  ARCH="$ARCH" appimagetool "$APPDIR" \
      "$DIST/${APPNAME}-${VERSION}-${ARCH}.AppImage" 2>/dev/null || \
      echo "    appimagetool failed; tarball is still valid"
else
  echo "    appimagetool not installed — skipping (install appimagetool to enable)"
fi

# ---------------------------------------------------------------- deb
echo "==> .deb"
if command -v dpkg-deb >/dev/null 2>&1; then
  DEB="$BUILD/deb"
  install -d "$DEB/DEBIAN" "$DEB/usr"
  cp -r "$APPDIR/usr/"* "$DEB/usr/"
  SIZE="$(du -sk "$DEB/usr" | cut -f1)"
  cat > "$DEB/DEBIAN/control" <<CONTROL
Package: $APPNAME
Version: $VERSION
Section: education
Priority: optional
Architecture: amd64
Installed-Size: $SIZE
Maintainer: CortexForge <noreply@example.invalid>
Description: Adaptive learning system with behavioural profiling
 Measures the learner before teaching them, generates questions in any
 style from their own source material, schedules review with FSRS, and
 reports honest behavioural observations with explicit uncertainty.
CONTROL
  dpkg-deb --build --root-owner-group "$DEB" \
      "$DIST/${APPNAME}_${VERSION}_amd64.deb" >/dev/null
  echo "    $DIST/${APPNAME}_${VERSION}_amd64.deb"
else
  echo "    dpkg-deb not installed — skipping"
fi

# ---------------------------------------------------------------- rpm
echo "==> .rpm"
if command -v rpmbuild >/dev/null 2>&1; then
  RPM="$BUILD/rpmbuild"
  install -d "$RPM"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
  tar -C "$BUILD" -czf "$RPM/SOURCES/${APPNAME}-${VERSION}.tar.gz" AppDir
  cat > "$RPM/SPECS/${APPNAME}.spec" <<SPEC
Name:           $APPNAME
Version:        $VERSION
Release:        1%{?dist}
Summary:        Adaptive learning system with behavioural profiling
License:        MIT
BuildArch:      x86_64
Source0:        %{name}-%{version}.tar.gz

%description
Measures the learner before teaching them, generates questions in any style
from their own source material, schedules review with FSRS, and reports
honest behavioural observations with explicit uncertainty.

%prep
%setup -q -c

%install
mkdir -p %{buildroot}/opt/%{name}
cp -r AppDir/usr/* %{buildroot}/opt/%{name}/
mkdir -p %{buildroot}%{_bindir}
ln -s /opt/%{name}/bin/%{name} %{buildroot}%{_bindir}/%{name}

%files
/opt/%{name}
%{_bindir}/%{name}
SPEC
  rpmbuild --define "_topdir $RPM" -bb "$RPM/SPECS/${APPNAME}.spec" >/dev/null 2>&1 && \
      find "$RPM/RPMS" -name '*.rpm' -exec cp {} "$DIST/" \; && \
      echo "    $(ls "$DIST"/*.rpm 2>/dev/null | head -1)" || \
      echo "    rpmbuild failed — skipping"
else
  echo "    rpmbuild not installed — skipping"
fi

# ---------------------------------------------------------------- arch
echo "==> PKGBUILD (Arch)"
cat > "$DIST/PKGBUILD" <<PKGBUILD
# Maintainer: CortexForge <noreply@example.invalid>
pkgname=$APPNAME
pkgver=$VERSION
pkgrel=1
pkgdesc="Adaptive learning system with behavioural profiling and honest feedback"
arch=('x86_64' 'aarch64')
url="https://github.com/ugwanjegrandson2010/cortexforge"
license=('MIT')
depends=()
options=('!strip')
source=("\$pkgname-\$pkgver.tar.gz")
sha256sums=('SKIP')

package() {
  install -d "\$pkgdir/opt/\$pkgname" "\$pkgdir/usr/bin"
  cp -r "\$srcdir/AppDir/usr/"* "\$pkgdir/opt/\$pkgname/"
  ln -s "/opt/\$pkgname/bin/\$pkgname" "\$pkgdir/usr/bin/\$pkgname"
}
PKGBUILD
echo "    $DIST/PKGBUILD"

# ---------------------------------------------------------------- flatpak
echo "==> Flatpak manifest"
cat > "$DIST/${APPNAME}.flatpak.yml" <<FLATPAK
app-id: io.github.ugwanjegrandson2010.CortexForge
runtime: org.freedesktop.Platform
runtime-version: '24.08'
sdk: org.freedesktop.Sdk
command: $APPNAME
finish-args:
  - --share=network
  - --socket=wayland
  - --socket=fallback-x11
  - --filesystem=home
modules:
  - name: $APPNAME
    buildsystem: simple
    build-commands:
      - install -d /app/lib/$APPNAME /app/bin
      - cp -r usr/lib/$APPNAME/* /app/lib/$APPNAME/
      - install -Dm755 usr/bin/$APPNAME /app/bin/$APPNAME
    sources:
      - type: dir
        path: AppDir
FLATPAK
echo "    $DIST/${APPNAME}.flatpak.yml"
echo "    build with: flatpak-builder --force-clean build-flatpak $DIST/${APPNAME}.flatpak.yml"

echo
echo "==> Linux build complete. Artifacts in $DIST:"
ls -lh "$DIST" | tail -n +2
