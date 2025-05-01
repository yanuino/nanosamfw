#!/bin/bash
# macOS Apple Silicon build script for GetNewSamsungFirmware

set -e

echo "Building GetNewSamsungFirmware macOS binaries..."
echo "================================================"

ARCH=$(uname -m)
if [ "$ARCH" != "arm64" ]; then
    echo "Warning: This script is intended for Apple Silicon (arm64), but current architecture is $ARCH."
    read -p "Do you want to continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Build canceled."
        exit 1
    fi
    echo "Continuing build on $ARCH architecture..."
else
    echo "Detected Apple Silicon (arm64) architecture."
fi

BUILD_DIR=$(pwd)

cd ..
VENV_NAME=".venv_macos_arm_build"
PIP="${VENV_NAME}/bin/pip"
PYINSTALLER="${VENV_NAME}/bin/pyinstaller"

echo "Creating Python virtual environment..."
if [ -d "$VENV_NAME" ]; then
    rm -rf "$VENV_NAME"
fi

python3 -m venv $VENV_NAME
if [ $? -ne 0 ]; then
    echo "Error: Failed to create virtual environment."
    exit 1
fi

echo "Installing required packages..."
$PIP install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error: Failed to install requirements."
    exit 1
fi

$PIP install pyinstaller
if [ $? -ne 0 ]; then
    echo "Error: Failed to install PyInstaller."
    exit 1
fi

ICON_PATH="AppIcons/app_icon.icns"
if [ ! -f "$ICON_PATH" ]; then
    if command -v sips &> /dev/null && command -v iconutil &> /dev/null; then
        mkdir -p AppIcons/app_icon.iconset
        
        if [ -f "AppIcons/512.png" ]; then
            SOURCE_ICON="AppIcons/512.png"
            
            sips -z 16 16 "$SOURCE_ICON" --out AppIcons/app_icon.iconset/icon_16x16.png
            sips -z 32 32 "$SOURCE_ICON" --out AppIcons/app_icon.iconset/icon_16x16@2x.png
            sips -z 32 32 "$SOURCE_ICON" --out AppIcons/app_icon.iconset/icon_32x32.png
            sips -z 64 64 "$SOURCE_ICON" --out AppIcons/app_icon.iconset/icon_32x32@2x.png
            sips -z 128 128 "$SOURCE_ICON" --out AppIcons/app_icon.iconset/icon_128x128.png
            sips -z 256 256 "$SOURCE_ICON" --out AppIcons/app_icon.iconset/icon_128x128@2x.png
            sips -z 256 256 "$SOURCE_ICON" --out AppIcons/app_icon.iconset/icon_256x256.png
            sips -z 512 512 "$SOURCE_ICON" --out AppIcons/app_icon.iconset/icon_256x256@2x.png
            sips -z 512 512 "$SOURCE_ICON" --out AppIcons/app_icon.iconset/icon_512x512.png
            
            if [ -f "AppIcons/1024.png" ]; then
                cp "AppIcons/1024.png" AppIcons/app_icon.iconset/icon_512x512@2x.png
            else
                sips -z 1024 1024 "$SOURCE_ICON" --out AppIcons/app_icon.iconset/icon_512x512@2x.png
            fi
            
            iconutil -c icns AppIcons/app_icon.iconset
            if [ $? -ne 0 ]; then
                rm -rf AppIcons/app_icon.iconset
                ICON_ARG=""
            else
                rm -rf AppIcons/app_icon.iconset
                ICON_ARG="--icon=$ICON_PATH"
            fi
        else
            rm -rf AppIcons/app_icon.iconset
            ICON_ARG=""
        fi
    else
        ICON_ARG=""
    fi
else
    ICON_ARG="--icon=$ICON_PATH"
fi

echo "Building app..."
FRIENDLY_APP_NAME="GNSF GUI"
$PYINSTALLER gnsf-GUI.py --onedir --clean --windowed --noconfirm $ICON_ARG --name "$FRIENDLY_APP_NAME" --add-data "AppIcons:AppIcons"
if [ $? -ne 0 ]; then
    echo "Error: Build failed."
    cd "$BUILD_DIR"
    exit 1
fi

echo "Cleaning up..."
rm -rf build
rm -f *.spec
rm -rf $VENV_NAME

cd "$BUILD_DIR"

echo "Build complete!"

APP_NAME="$FRIENDLY_APP_NAME.app"
EXPECTED_PATH="dist/$APP_NAME/Contents/MacOS/$FRIENDLY_APP_NAME"

if [ -f "$EXPECTED_PATH" ]; then
    chmod +x "$EXPECTED_PATH"
elif [ -d "dist/$APP_NAME" ]; then
    EXEC_FILE=$(find "dist/$APP_NAME" -type f -path "*/Contents/MacOS/*" | head -1)
    if [ -n "$EXEC_FILE" ]; then
        chmod +x "$EXEC_FILE"
    fi
fi

echo "Creating DMG installer..."
DMG_NAME="GetNewSamsungFirmware-macOS-arm64.dmg"
DMG_TEMP_DIR="dmg_temp"
APP_NAME="$FRIENDLY_APP_NAME.app"

if [ -d "$DMG_TEMP_DIR" ]; then
    rm -rf "$DMG_TEMP_DIR"
fi
mkdir -p "$DMG_TEMP_DIR"

if [ -d "dist" ]; then
    APP_PATH="dist/$APP_NAME"
elif [ -d "../dist" ]; then
    APP_PATH="../dist/$APP_NAME"
else
    APP_PATH=$(find . -name "$APP_NAME" -type d | head -1)
fi

if [ ! -d "$APP_PATH" ]; then
    echo "Error: Application bundle not found"
    rm -rf "$DMG_TEMP_DIR"
    exit 1
fi

cp -r "$APP_PATH" "$DMG_TEMP_DIR/"
if [ $? -ne 0 ]; then
    echo "Error: Failed to copy application bundle."
    rm -rf "$DMG_TEMP_DIR"
    exit 1
fi

ln -s /Applications "$DMG_TEMP_DIR/Applications"

if [ ! -d "../dist" ]; then
    mkdir -p "../dist"
fi

DIST_DIR=$(cd "../dist" && pwd)
DMG_OUTPUT_PATH="${DIST_DIR}/${DMG_NAME}"
DMG_TEMP_DIR_ABS=$(cd "$DMG_TEMP_DIR" && pwd)

hdiutil create -volname "GetNewSamsungFirmware" -srcfolder "$DMG_TEMP_DIR_ABS" -ov -format UDZO "$DMG_OUTPUT_PATH"

if [ $? -ne 0 ]; then
    echo "Error: Failed to create DMG file."
else
    echo "DMG created successfully: $DMG_OUTPUT_PATH"
    
    if [ -d "../dist/macos_arm64_gnsf-GUI" ]; then
        rm -rf "../dist/macos_arm64_gnsf-GUI"
    fi
    
    if [ -d "../dist/$FRIENDLY_APP_NAME.app" ]; then
        rm -rf "../dist/$FRIENDLY_APP_NAME.app"
    fi

    if [ -d "../dist/$FRIENDLY_APP_NAME" ]; then
        rm -rf "../dist/$FRIENDLY_APP_NAME"
    fi
fi

rm -rf "$DMG_TEMP_DIR"

echo "================================================"
echo "All tasks completed!"
echo "Installer package: ../dist/$DMG_NAME"
echo "================================================"
