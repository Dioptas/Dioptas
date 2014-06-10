'''
Created on 12.08.2013

@author: Clemens
'''
import os


def convert_ui_files(folder='/'):
    old_path = os.getcwd()
    new_path = os.getcwd() + folder
    os.chdir(new_path)
    os.system('echo $PATH')
    for file in os.listdir('.'):
        if file.endswith(".ui"):
            file_name = str(file).split('.')[0]
            command = 'pyside-uic-2.7'
            pyqt_command = 'pyuic4'
            cmd = command + ' ' + file + ' > ' + file_name + 'UI.py'  # PyQT Version
            print cmd
            os.system(cmd)
    os.chdir(old_path)


if __name__ == "__main__":
    convert_ui_files()
