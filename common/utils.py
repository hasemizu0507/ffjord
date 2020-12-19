import matplotlib
from mpl_toolkits.mplot3d import Axes3D

matplotlib.use('Agg')

import numpy as np
import torch
import torchvision
import sklearn.datasets
import matplotlib.pyplot as plt


def save_plot(filename, xs, ys, zs=None, colors=None):
    fig = plt.figure(figsize=(9, 8))
    if zs is None:
        # 2D
        ax = fig.add_subplot(111)
        scatter = ax.scatter(xs, ys, c=colors, cmap='jet')  #, vmin=0.0, vmax=5.0)
    else:
        # 3D
        ax = fig.add_subplot(111, projection='3d')
        ax.view_init(elev=10.0, azim=-80.0)
        ax.set_zlim([-1, 1])
        ax.set_zticks(np.linspace(-1, 1, 5))
        scatter = ax.scatter(xs, ys, zs, c=colors, cmap='jet')  #, vmin=0.0, vmax=5.0)

    ax.set_aspect('equal', adjustable='box')
    ax.set_xlim([-1, 1])
    ax.set_xticks(np.linspace(-1, 1, 5))
    ax.set_ylim([-1, 1])
    ax.set_yticks(np.linspace(-1, 1, 5))
    plt.colorbar(scatter)
    plt.savefig(filename)
    plt.close()


def save_image_plot(filename, image, cmap='inferno'):
    im = plt.imshow(image, cmap=cmap, extent=[-1, 1, -1, 1])  #, vmin=0.0, vmax=5.0)
    plt.colorbar(im)
    plt.savefig(filename)
    plt.close()