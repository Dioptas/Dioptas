# Setting the QT_QPA_PLATFORM_PLUGIN_PATH environment variable in case of macOS
# This is necessary when running a PyQt6 application that has been packaged with PyInstaller
# and is located inside a .app bundle. The environment variable points to the
# directory where the Qt platform plugins are located.
# The frozen attribute is used to check if the script is running inside a PyInstaller bundle.
import os
import sys

if sys.platform == "darwin" and getattr(sys, "frozen", False):
    # Inside a macOS .app bundle made by PyInstaller
    bundle_path = os.path.abspath(os.path.dirname(sys.executable))
    plugin_path = os.path.join(
        bundle_path, "..", "Resources", "PyQt6", "Qt6", "plugins", "platforms"
    )
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = os.path.normpath(plugin_path)

# Run the main function from dioptas
from dioptas import main

main()
