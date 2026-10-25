#!/usr/bin/env bash
# macOS 打包（必须在 macOS 上跑）：生成 .app + .dmg
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
PKG="NardoFoxWriteDesk"
VER="2.9"

python3 -m PyInstaller --noconfirm --windowed --name "$PKG" \
  --add-data "fonts:fonts" \
  --add-data "app/assets:app/assets" \
  --add-data "LICENSE:." \
  --add-data "THIRD-PARTY-NOTICES.md:." \
  main.py

APP="dist/${PKG}.app"

# 图标：用仓里的 iconset（由 app.ico 派生，不含原稿）直接转 icns
mkdir -p build
iconutil -c icns "packaging/mac/icon.iconset" -o "build/${PKG}.icns"
cp "build/${PKG}.icns" "$APP/Contents/Resources/${PKG}.icns"
/usr/libexec/PlistBuddy -c "Set :CFBundleIconFile ${PKG}" "$APP/Contents/Info.plist" || true

STAGE="build/dmg"
rm -rf "$STAGE"; mkdir -p "$STAGE"
cp -r "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
mkdir -p dist
hdiutil create -volname "纳多狐狐的写作台" -srcfolder "$STAGE" -ov -format UDZO "dist/${PKG}-${VER}.dmg"
echo "完成：dist/${PKG}-${VER}.dmg"
