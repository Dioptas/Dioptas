# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'

import glob
from subprocess import call
import sys
import os
import time

folders = ['', 'functional_tests/']
test_files = []

for folder in folders:
    base_str = os.path.join(folder, 'test')
    test_files += glob.glob("{}_*.py".format(base_str))

exit_codes = []
for test_file in test_files:
    print("##############################")
    print("##############################")
    print("Running: " + "python {}".format(test_file))
    print("##############################")
    exit_code = call("python {}".format(test_file), shell=True)
    exit_codes.append(exit_code)
    time.sleep(2)


script_exit_code = 0
for ind, exit_code in enumerate(exit_codes):
    if exit_code:
        print("{} has failed!".format(test_files[ind]))
        script_exit_code = 1


if script_exit_code is 0:
    print("All Tests Passed!")

sys.exit(script_exit_code)
