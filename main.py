import os
import shutil
import argparse

import numpy as np
import scipy as sp
import torch
from tqdm import tqdm
from torch.distributions.multivariate_normal import MultivariateNormal

from flows import Glow, Flowxx, RealNVP
from flows.utils import sample, save_plot

networks = {'realnvp': RealNVP, 'glow': Glow, 'flow++': Flowxx}


class Model(object):
    def __init__(self, net='realnvp', n_dims=2, n_layers=4):
        if torch.cuda.is_available():
            self.device = torch.device('cuda', 0)
        else:
            self.device = torch.device('cpu')

        mu = torch.zeros(n_dims, dtype=torch.float32, device=self.device)
        covar = torch.eye(n_dims, dtype=torch.float32, device=self.device)
        self.normal = MultivariateNormal(mu, covar)

        self.net = networks[net](n_dims=n_dims, n_layers=n_layers)
        self.net.to(self.device)
        self.optim = torch.optim.Adam(self.net.parameters(), lr=1.0e-4)

    def train_on_batch(self, y):
        y = y.to(self.device)
        self.net.train()

        z, log_det_jacobian = self.net(y)
        loss = -1.0 * torch.mean(self.normal.log_prob(z) + torch.sum(log_det_jacobian, dim=1))

        self.optim.zero_grad()
        loss.backward()
        self.optim.step()

        return z, loss

    def eval_on_batch(self, z):
        z = z.to(self.device)
        self.net.eval()

        y, log_det_jacobian = self.net.backward(z)
        jacobian = torch.exp(torch.sum(log_det_jacobian, dim=1))

        return y, jacobian


def main():
    torch.backends.cudnn.benchmark = True

    # command line arguments
    parser = argparse.ArgumentParser(description='Flow-based generative models')
    parser.add_argument('-n', '--network', type=str, required=True, choices=networks.keys(), help='name of network')
    parser.add_argument('-E', '--epochs', type=int, default=20, help='training epochs')
    parser.add_argument('-B', '--batchsize', type=int, default=1024, help='minibatch size')
    parser.add_argument('-N', '--n_samples', type=int, default=1024, help='#samples to be drawn')
    parser.add_argument('--dist_name', default='moons', choices=['moons'], help='name of target distribution')
    parser.add_argument('--output', type=str, default='outputs', help='output directory')
    args = parser.parse_args()

    # setup output directory
    out_dir = os.path.join(args.output, args.network)
    os.makedirs(out_dir, exist_ok=True)

    # setup train/eval model
    model = Model()

    normal = sp.stats.multivariate_normal(np.zeros(2), np.eye(2))

    for epoch in range(args.epochs):
        # training
        pbar = tqdm(range(100))
        for i in pbar:
            y = sample(args.n_samples, name=args.dist_name)
            y = torch.tensor(y, dtype=torch.float32, requires_grad=True)
            z, loss = model.train_on_batch(y)
            pbar.set_description('epoch #{:d}: loss={:.5f}'.format(epoch + 1, loss.item()))

        # testing
        z = np.random.multivariate_normal(np.zeros(2), np.eye(2), size=(args.n_samples))
        z = torch.tensor(z, dtype=torch.float32)
        y, jacobian = model.eval_on_batch(z)

        y = y.detach().cpu().numpy()
        jacobian = jacobian.detach().cpu().numpy()
        pdf = normal.pdf(z) / jacobian
        xs = y[:, 0]
        ys = y[:, 1]

        out_file = os.path.join(out_dir, 'y_sample_{:06d}.jpg'.format(epoch + 1))
        save_plot(out_file, xs, ys, pdf)
        latest_file = os.path.join(out_dir, 'y_sample_latest.jpg'.format(epoch + 1))
        shutil.copyfile(out_file, latest_file)


if __name__ == '__main__':
    main()
