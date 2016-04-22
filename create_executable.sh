#!/usr/bin/env bash
sudo rm -rf build
cd dioptas
pyinstaller --distpath ../dist --workpath ../build Dioptas.spec -y
cd ..
