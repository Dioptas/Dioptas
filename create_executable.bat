rmdir /s /q dist
rmdir /s /q build
pyinstaller Dioptas.spec
cd dist/dioptas*
dioptas