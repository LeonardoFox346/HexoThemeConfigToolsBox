#!/usr/bin/env bash
# Linux 打包：先 PyInstaller，再拼成 .deb（按当前机器架构自动命名）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
PKG="nardofox-writedesk"
VER="2.9"
ARCH="$(dpkg --print-architecture 2>/dev/null || echo amd64)"

python3 -m PyInstaller --noconfirm packaging/app.spec

STAGE="build/deb/${PKG}"
rm -rf "$STAGE"
mkdir -p "$STAGE/opt/${PKG}" "$STAGE/DEBIAN" "$STAGE/usr/share/applications"
cp -r "dist/NardoFoxWriteDesk/." "$STAGE/opt/${PKG}/"
cp "packaging/linux/${PKG}.desktop" "$STAGE/usr/share/applications/"

for size in 16 24 32 48 64 128 256 512; do
  d="$STAGE/usr/share/icons/hicolor/${size}x${size}/apps"
  mkdir -p "$d"
  cp "packaging/linux/icons/${size}.png" "$d/${PKG}.png"
done

sed -e "s/@VERSION@/${VER}/" -e "s/@ARCH@/${ARCH}/" \
  "packaging/linux/control.in" > "$STAGE/DEBIAN/control"
mkdir -p dist
OUT="dist/${PKG}_${VER}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$STAGE" "$OUT"
echo "完成：$OUT"
