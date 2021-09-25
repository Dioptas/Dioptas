from pyqtgraph.Qt import QtGui
import pyqtgraph.opengl as gl
import OpenGL.GL as ogl
import numpy as np


class CustomTextItem(gl.GLGraphicsItem.GLGraphicsItem):
    def __init__(self, X=None, Y=None, Z=None, text=None, color=(255, 255, 255, 255), size=16):
        gl.GLGraphicsItem.GLGraphicsItem.__init__(self)

        self.text = text
        self.X = X
        self.Y = Y
        self.Z = Z
        self.color = color
        self.size = size
        if self.size > 64:
            raise ValueError("Value of the variable 'size' cannot be greater than 64!")

    def setGLViewWidget(self, GLViewWidget):
        self.GLViewWidget = GLViewWidget

    def setText(self, text):
        self.text = text
        self.update()

    def setX(self, X):
        self.X = X
        self.update()

    def setY(self, Y):
        self.Y = Y
        self.update()

    def setZ(self, Z):
        self.Z = Z
        self.update()

    def paint(self):
        fontObject = QtGui.QFont()  # "Helvetica")
        fontObject.setPixelSize(self.size)

        self.GLViewWidget.qglColor(QtGui.QColor(*self.color))
        self.GLViewWidget.renderText(float(self.X), float(self.Y), float(self.Z), self.text)  # , fontObject)


class CustomAxis(gl.GLGraphicsItem.GLGraphicsItem):
    def __init__(self, parent, x=1, y=0, z=0, color=(0.9, 0.9, 0.9, .6)):
        gl.GLGraphicsItem.GLGraphicsItem.__init__(self)
        self.parent = parent
        self.x = x
        self.y = y
        self.z = z

        self.xLabel = CustomTextItem(x, y, z, "Hallo")
        self.xLabel.setGLViewWidget(self.parent)
        self.parent.addItem(self.xLabel)
        self.update()

    # def transform(self, x, y, z):
    #     self.resetTransform()
    #     self.transform(x, y, z)

    def setSize(self, x=None, y=None, z=None, size=None):
        """
        Set the size of the axes (in its local coordinate system; this does not affect the transform)
        Arguments can be x,y,z or size=QVector3D().
        """
        if size is not None:
            x = size.x()
            y = size.y()
            z = size.z()
        self.__size = [x, y, z]
        self.update()


class Custom3DAxis(gl.GLAxisItem):
    """Class defined to extend 'gl.GLAxisItem'."""

    def __init__(self, parent, color=(0, 0, 0, .6), axis=[True, True, True]):
        gl.GLAxisItem.__init__(self)
        self.parent = parent
        self.color = color
        self.ticks = []
        self._axisStat = axis
        self.diff = [0, 0, 0]

    def add_labels(self, x_label=None, y_label=None, z_label=None):
        """Adds axes labels."""
        x, y, z = self.size()
        dx, dy, dz = self.diff

        if x_label is not None:
            self.xLabel = CustomTextItem(X=x / 2, Y=-y / 20, Z=-z / 20, text=x_label)
            self.xLabel.setGLViewWidget(self.parent)
            self.parent.addItem(self.xLabel)
        if y_label is not None:
            self.yLabel = CustomTextItem(X=-x / 20 + dx, Y=y / 2 + dy, Z=-z / 20, text=y_label)
            self.yLabel.setGLViewWidget(self.parent)
            self.parent.addItem(self.yLabel)
        if z_label is not None:
            self.zLabel = CustomTextItem(X=-x / 20, Y=-y / 20, Z=z / 2, text=z_label)
            self.zLabel.setGLViewWidget(self.parent)
            self.parent.addItem(self.zLabel)

    def set_tick_values(self, xticks=[], yticks=[], zticks=[]):
        """Adds ticks values."""

        self.clean_ticks()
        x, y, z = self.size()
        dx, dy, dz = self.diff

        xtpos = np.linspace(0, x, len(xticks))
        ytpos = np.linspace(0, y, len(yticks))
        ztpos = np.linspace(0, z, len(zticks))
        for i, xt in enumerate(xticks):
            val = CustomTextItem(X=xtpos[i], Y=-y / 20, Z=-z / 20, text=str(xt))
            val.setGLViewWidget(self.parent)
            self.ticks.append(val)
            self.parent.addItem(val)
        for i, yt in enumerate(yticks):
            val = CustomTextItem(X=-x / 20 + dx, Y=ytpos[i], Z=-z / 20, text=str(yt))
            val.setGLViewWidget(self.parent)
            self.ticks.append(val)
            self.parent.addItem(val)
        for i, zt in enumerate(zticks):
            val = CustomTextItem(X=-x / 20, Y=-y / 20, Z=ztpos[i], text=str(zt))
            val.setGLViewWidget(self.parent)
            self.parent.addItem(val)

        self.update()

    def clean_ticks(self):
        for tick in self.ticks:
            self.parent.removeItem(tick)
        self.ticks = []

    def paint(self):
        self.setupGLState()
        if self.antialias:
            ogl.glEnable(ogl.GL_LINE_SMOOTH)
            ogl.glHint(ogl.GL_LINE_SMOOTH_HINT, ogl.GL_NICEST)
        ogl.glBegin(ogl.GL_LINES)

        x, y, z = self.size()
        paint_x, paint_y, paint_z = self._axisStat
        if paint_z:
            ogl.glColor4f(*self.color)
            ogl.glVertex3f(0, 0, 0)
            ogl.glVertex3f(0, 0, z)
        if paint_y:
            ogl.glColor4f(*self.color)
            ogl.glVertex3f(0, 0, 0)
            ogl.glVertex3f(0, y, 0)
        if paint_x:
            ogl.glColor4f(*self.color)
            ogl.glVertex3f(0, 0, 0)
            ogl.glVertex3f(x, 0, 0)
            ogl.glEnd()
