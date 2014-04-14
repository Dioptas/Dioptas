__author__ = 'Doomgoroth'

import matplotlib.pylab as plt
import numpy as np

cos = np.cos
sin = np.sin


def calculate_circle(radius, points=1000):
    x = np.linspace(-radius, radius, points)
    y = np.sqrt(radius - x ** 2)
    x = np.concatenate((x, -x))
    y = np.concatenate((y, -y))
    return x, y


x, y = calculate_circle(1)
z = np.array([0.2] * len(x))

circle = np.vstack((x, y, z)).T

rotation_angle_z = 30

_rotation_angle_z = rotation_angle_z / 180.0 * np.pi

rotation_matrix_z = np.array([[cos(rotation_angle_z), sin(rotation_angle_z), 0],
                              [-sin(rotation_angle_z), cos(rotation_angle_z), 0],
                              [0, 0, 1]])

rotation_angle_y = 30
_rotation_angle_y = rotation_angle_y / 180.0 * np.pi
rotation_matrix_y = np.array([[cos(_rotation_angle_y), 0, -sin(_rotation_angle_y)],
                              [0, 1, 0],
                              [sin(_rotation_angle_y), 0, cos(_rotation_angle_y)]])

rot_circle = circle.dot(rotation_matrix_y)
rot2_circle = rot_circle.dot(rotation_matrix_z)

plt.plot(circle[:, 0], circle[:, 1], 'r')
plt.plot(rot_circle[:, 0], rot_circle[:, 1], 'g')
plt.plot(rot2_circle[:, 0], rot2_circle[:, 1], 'b')
plt.xlim(-1, 1)
plt.ylim(-1, 1)
plt.show()
