#!/bin/bash
# Wine Windows build script for GetNewSamsungFirmware

set -e

echo "Building GetNewSamsungFirmware Windows binaries using Wine..."
echo "==========================================================="

BUILD_DIR=$(pwd)

cd ..
echo "Current working directory: $(pwd)"

export WINEDEBUG="-all"

WINE_PYTHON="wine python.exe"
VENV_NAME=".venv_windows64_build"
WINE_PIP="wine ${VENV_NAME}/Scripts/pip.exe"
WINE_PYINSTALLER="wine ${VENV_NAME}/Scripts/pyinstaller.exe"

if ! command -v wine &> /dev/null; then
    echo "Error: Wine is not installed. Please install Wine to continue."
    exit 1
fi

echo "Creating Wine Python virtual environment..."
if [ -d "$VENV_NAME" ]; then
    echo "Removing existing virtual environment..."
    rm -rf "$VENV_NAME"
fi

$WINE_PYTHON -m venv $VENV_NAME
if [ $? -ne 0 ]; then
    echo "Error: Failed to create virtual environment."
    exit 1
fi
echo "Virtual environment created successfully."

echo "Installing required packages..."
$WINE_PIP install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "Error: Failed to install requirements."
    exit 1
fi

echo "Installing PyInstaller..."
$WINE_PIP install pyinstaller
if [ $? -ne 0 ]; then
    echo "Error: Failed to install PyInstaller."
    exit 1
fi
echo "All dependencies installed successfully."

ICON_PATH="AppIcons/app_icon.ico"
if [ ! -f "$ICON_PATH" ]; then
    echo "Icon file not found. Attempting to convert..."
    if command -v magick &> /dev/null; then
        magick convert AppIcons/512.png -define icon:auto-resize="256,128,64,48,32,16" $ICON_PATH
        if [ $? -ne 0 ]; then
            echo "Warning: Icon conversion failed. Building without custom icon."
            ICON_ARG=""
        else
            echo "Icon conversion successful."
            ICON_ARG="--icon=$ICON_PATH"
        fi
    else
        echo "Warning: ImageMagick not found. Building without custom icon."
        ICON_ARG=""
    fi
else
    echo "Using existing icon: $ICON_PATH"
    ICON_ARG="--icon=$ICON_PATH"
fi

if [ ! -d "$BUILD_DIR/output" ]; then
    mkdir -p "$BUILD_DIR/output"
fi

echo "Building CLI version (with console)..."
$WINE_PYINSTALLER gnsf.py --onefile --clean -c $ICON_ARG --name windows_x64_gnsf --add-data "AppIcons;AppIcons"
if [ $? -ne 0 ]; then
    echo "Error: Failed to build CLI version."
    cd "$BUILD_DIR"
    exit 1
fi

echo "Building GUI version (no console)..."
$WINE_PYINSTALLER gnsf-GUI.py --onefile --clean -w $ICON_ARG --name windows_x64_gnsf-GUI --add-data "AppIcons;AppIcons"
if [ $? -ne 0 ]; then
    echo "Error: Failed to build GUI version."
    cd "$BUILD_DIR"
    exit 1
fi

echo "Cleaning up build files..."
rm -rf build
rm -f *.spec

echo "Removing virtual environment..."
rm -rf $VENV_NAME

cd "$BUILD_DIR"

echo
echo "Build complete!"
echo "Executables can be found in the output directory:"
echo "- output/windows_x64_gnsf.exe"
echo "- output/windows_x64_gnsf-GUI.exe"
echo "==========================================================="