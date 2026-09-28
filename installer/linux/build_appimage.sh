#!/usr/bin/env bash
# Run from the repository root after PyInstaller has populated dist/.
set -euo pipefail
repo_root=$(pwd)
cd dist
bundle=$(find . -maxdepth 1 -type d -name 'Dioptas_Linux*' -print -quit)
test -n "$bundle"
wget -q https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage -O appimagetool
chmod +x appimagetool
mkdir -p Dioptas.AppDir/usr/bin Dioptas.AppDir/usr/share/icons/hicolor/256x256/apps
cp -a "$bundle"/. Dioptas.AppDir/usr/bin/
cp "$repo_root/installer/linux/Dioptas.desktop" Dioptas.AppDir/
cp "$repo_root/dioptas/resources/icons/icon.png" Dioptas.AppDir/dioptas.png
cp "$repo_root/dioptas/resources/icons/icon.png" Dioptas.AppDir/usr/share/icons/hicolor/256x256/apps/dioptas.png
cp "$repo_root/installer/linux/AppRun" Dioptas.AppDir/AppRun
chmod +x Dioptas.AppDir/AppRun
ARCH=x86_64 APPIMAGE_EXTRACT_AND_RUN=1 ./appimagetool Dioptas.AppDir Dioptas_Linux.AppImage
APPIMAGE_EXTRACT_AND_RUN=1 xvfb-run -a ./Dioptas_Linux.AppImage test
