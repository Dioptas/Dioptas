import mod
import matplotlib.pyplot as plt
import numpy as np
from PySide import QtGui


size = 300
mask_data = np.zeros((size, size))
my_object = QtGui.QGraphicsEllipseItem(size / 2, size / 2, size / 4., size / 4, )
mask_data = mod.test_qt_graphics_object4(mask_data, my_object)

plt.imshow(mask_data)
plt.show()


