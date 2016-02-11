#!/usr/bin/env bash
sudo rm -rf build dist
cd dioptas
pyinstaller --distpath ../dist --workpath ../build Dioptas.spec
cd ..
