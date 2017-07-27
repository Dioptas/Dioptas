# -*- coding: utf8 -*-
# Dioptas - GUI program for fast processing of 2D X-ray data
# Copyright (C) 2017  Clemens Prescher (clemens.prescher@gmail.com)
# Institute for Geology and Mineralogy, University of Cologne
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import glob
from subprocess import call
import sys
import os
import time

folders = [x[0] for x in os.walk(os.path.dirname(os.path.abspath(__file__)))]
print(folders)
print(os.path.dirname('.'))
print(os.path.abspath(__file__))
test_files = []

for folder in folders:
    base_string = folder + '/test'
    test_files += glob.glob("{}_*.py".format(base_string))

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
