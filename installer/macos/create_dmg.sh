#!/usr/bin/env bash
set -euo pipefail

brew install create-dmg
cd dist
shopt -s nullglob
apps=(Dioptas*.app)
if [[ ${#apps[@]} -ne 1 ]]; then
    echo "Expected exactly one Dioptas app bundle" >&2
    exit 1
fi

# create-dmg may fail to position icons on a runner without a GUI session.
# Require a complete, verifiable disk image even in that case.
create-dmg \
    --volname "Dioptas" \
    --volicon "../dioptas/resources/icons/icon.icns" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --icon-size 100 \
    --icon "${apps[0]}" 150 190 \
    --app-drop-link 450 190 \
    --no-internet-enable \
    "Dioptas_MacOS.dmg" \
    "${apps[0]}" || test -f Dioptas_MacOS.dmg
hdiutil verify Dioptas_MacOS.dmg
