__author__ = 'Clemens Prescher'

from pyFAI.blob_detection import BlobDetection
from Data.ImgData import ImgData
import numpy as np
import pylab

img_data = ImgData()
# img_data.load('/Users/Doomgoroth/Programming/Large Projects/Py2DeX/Testing/pyFAITest/17_LaB6_dc300-00000.tif')
img_data.load('/Users/Doomgoroth/Programming/Large Projects/Py2DeX/Testing/pyFAITest/LaB6_WOS_30keV_005.tif')
bd = BlobDetection(np.log1p(img_data.get_img_data()))

bd.process()

x = []
y = []
int = []
sigma = []

print bd.keypoints.__len__()
for j in range(bd.keypoints.__len__()):
    k = bd.keypoints[j]
    int.append(k[2])
    sigma.append(k[3])
    if sigma[-1] > 0.25:
        x.append(k[0])
        y.append(k[1])

pylab.hist(int)
pylab.figure(2)
pylab.hist(sigma)

pylab.figure(3)
pylab.imshow(img_data.get_img_data(), cmap='hot')
pylab.plot(x, y, '.g')
pylab.show()

# sigma = numpy.asarray(sigma)
# pylab.figure(2)
# pylab.clf()
# pylab.hist(sigma, bins=500)
# pylab.show()

