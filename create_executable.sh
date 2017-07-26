#!/usr/bin/env bash
sudo rm -rf build
pyinstaller Dioptas.spec -y
