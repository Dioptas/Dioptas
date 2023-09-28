#!/usr/bin/env python
import sys
import os

from dropbox import Dropbox

if len(sys.argv) != 3:
    print('Please provide file to upload and destination folder!')
    exit(-1)

if os.getenv('DROPBOX_TOKEN') == None:
    print('Please set the Dropbox api Access token as environment variable DROPBOX_TOKEN')
    exit(-1)

db = Dropbox(os.getenv('DROPBOX_TOKEN'))
# delete file if it already exists in dropbox
try:
    db.files_delete(sys.argv[2] + '/' + sys.argv[1])
except:
    pass
db.files_upload(open(sys.argv[1], 'rb').read(), sys.argv[2])
print('{} successfully uploaded to dropbox folder {}'.format(sys.argv[1], sys.argv[2]))
