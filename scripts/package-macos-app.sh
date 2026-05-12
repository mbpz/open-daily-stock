#!/bin/bash
set -e

# 默认版本从 git tag 获取
VERSION=${1:-$(git describe --tags 2>/dev/null | sed 's/^v//')}
if [ -z "$VERSION" ]; then
    VERSION="0.0.0"
fi

echo "Packaging open-daily-stock GUI v$VERSION for macOS"

# 清理旧的 dist
rm -rf dist

# 1. PyInstaller 打包 (在 gui 目录下)
cd gui
pyinstaller open-daily-stock.spec --distpath ../dist
cd ..

# 2. 创建 .app Bundle 结构
APPNAME="open-daily-stock-gui.app"
BUNDLE_PATH="dist/$APPNAME"
CONTENTS="$BUNDLE_PATH/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"

mkdir -p "$MACOS"
mkdir -p "$RESOURCES"

# 复制可执行文件
cp "dist/open-daily-stock-gui" "$MACOS/"

# 创建 Info.plist
cat > "$CONTENTS/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>open-daily-stock-gui</string>
    <key>CFBundleDisplayName</key>
    <string>Open Daily Stock</string>
    <key>CFBundleIdentifier</key>
    <string>com.opendailystock.app</string>
    <key>CFBundleVersion</key>
    <string>__VERSION__</string>
    <key>CFBundleShortVersionString</key>
    <string>__VERSION__</string>
    <key>CFBundleExecutable</key>
    <string>open-daily-stock-gui</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.15</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
</dict>
</plist>
EOF

# 替换版本号
sed -i '' "s/__VERSION__/$VERSION/g" "$CONTENTS/Info.plist"

# 3. Ad-hoc 签名（满足 ARM 运行要求）
echo "==> Applying ad-hoc code signature..."
codesign --force --deep --sign - "$BUNDLE_PATH"

# 验证签名
echo "==> Verifying signature..."
codesign --verify --verbose "$BUNDLE_PATH"

# 4. 创建 DMG
DMG_NAME="dist/open-daily-stock-gui-${VERSION}-macos.dmg"
SPARSE="dist/rw.temp.dmg"

if ! command -v create-dmg &> /dev/null; then
    echo "create-dmg not found, installing via brew..."
    brew install create-dmg
fi

# 使用 hdiutil 创建 DMG
hdiutil create "$SPARSE" \
    -volname "Open Daily Stock" \
    -fs HFS+ \
    -size 200m \
    -layout NONE

hdiutil attach "$SPARSE" -mountpoint /Volumes/temp_dmg -nobrowse

# 复制 .app 到 DMG
cp -R "$BUNDLE_PATH" "/Volumes/temp_dmg/"

hdiutil detach /Volumes/temp_dmg

# 转换为最终 DMG（压缩）
hdiutil convert "$SPARSE" -format UDZO -o "$DMG_NAME"
rm -f "$SPARSE"

# 5. 清除 quarantine xattr（绕过 Gatekeeper 安装弹窗）
echo "==> Clearing quarantine xattr..."
xattr -rc "$DMG_NAME"

# 6. 计算 SHA256（用于 Homebrew Cask）
echo "==> Computing SHA256..."
ARM_DMG="dist/open-daily-stock-gui-${VERSION}-macos-arm64.dmg"
INTEL_DMG="dist/open-daily-stock-gui-${VERSION}-macos.dmg"

if [ -f "$ARM_DMG" ]; then
    ARM_SHA=$(shasum -a 256 "$ARM_DMG" | awk '{print $1}')
    echo "ARM64 SHA256: $ARM_SHA"
fi

INTEL_SHA=$(shasum -a 256 "$INTEL_DMG" | awk '{print $1}')
echo "Intel SHA256: $INTEL_SHA"

echo ""
echo "Done! DMG created: $DMG_NAME"
echo "Replace in Cask:"
echo "  arm:   \"$ARM_SHA\","
echo "  intel: \"$INTEL_SHA\","
