# -*- coding: utf8 -*-
__author__ = 'Clemens Prescher'

import numpy as np

class ImgCorrectionManager(object):
    def __init__(self, img_shape=None):
        self._corrections = {}
        self._ind = 0
        self.shape = img_shape

    def add(self, ImgCorrection, name=None):
        if self.shape is None:
            self.shape = ImgCorrection.shape()

        if self.shape == ImgCorrection.shape():
            if name is None:
                name=self._ind
                self._ind+=1
            self._corrections[name]=ImgCorrection
            return True
        return False

    def delete(self, name=None):
        if name is None:
            if self._ind == 0:
                return
            self._ind-=1
            name = self._ind
        del self._corrections[name]

    def get_data(self):
        if len(self._corrections)==0:
            return None

        res = np.ones(self.shape)
        for key, correction in self._corrections.iteritems():
            res *= correction.get_data()
        return res




class ImgCorrectionInterface(object):
    def get_data(self):
        raise NotImplementedError

    def shape(self):
        raise NotImplementedError