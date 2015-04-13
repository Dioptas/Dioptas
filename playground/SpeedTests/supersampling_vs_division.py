def supersample_data(img_data, factor):
    """
    Creates a supersampled array from img_data.
    :param img_data: image array
    :param factor: int - supersampling factor
    :return:
    """
    if factor > 1:
        img_data_supersampled = np.zeros((img_data.shape[0] * factor,
                                          img_data.shape[1] * factor))
        for row in range(factor):
            for col in range(factor):
                img_data_supersampled[row::factor, col::factor] = img_data

        return img_data_supersampled
    else:
        return img_data



import numpy as np
import time

array1 = np.ones((2048, 2048)).astype(float)
array2 = np.ones((2048, 2048)).astype(float)*0.3

factor = 3.2
offset = 100

supersampling = 4

t1 = time.time()

for dummy_ind in range(10):
    test = array1 - factor*array1-offset

print('Normal arithmethic takes {}'.format(time.time()-t1))

array1_supersampled = supersample_data(array1, supersampling)
array2_supersampled = supersample_data(array2, supersampling)

t1 = time.time()

for dummy_ind in range(10):
    test = array1_supersampled - factor*array2_supersampled-offset

print('Supersampled 2 arithmethic takes {}'. format(time.time()-t1))


t1 = time.time()

for dummy_ind in range(10):
    test = supersample_data(array1, supersampling)

print('Supersampling to 2 takes {}'.format(time.time()-t1))
