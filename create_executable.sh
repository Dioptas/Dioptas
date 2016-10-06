#!/usr/bin/env bash
sudo rm -rf build
pyinstaller --distpath dist --workpath build Dioptas.spec -y
