#!/usr/bin/env python
import sys
import os
from datetime import datetime

from dropbox import Dropbox

if len(sys.argv) != 3:
    print('Please provide file to upload and destination folder!')
    exit(-1)

if os.getenv('DROPBOX_TOKEN') == None:
    print('Please set the Dropbox api Access token as environment variable DROPBOX_TOKEN')
    exit(-1)

target_path = sys.argv[2]
dir_name, file_name = os.path.split(target_path)
base_name = "_".join(file_name.split("_")[1:])
ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
new_path = f"{dir_name}/Dioptas_{ts}_{base_name}"
db = Dropbox(os.getenv('DROPBOX_TOKEN'))
db.files_upload(open(sys.argv[1], 'rb').read(), new_path)
print('{} successfully uploaded to dropbox folder {}'.format(sys.argv[1], new_path))
