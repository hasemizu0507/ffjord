import numpy as np
import scipy as sp
import torch
import torch.nn as nn
import scipy.linalg
import torch.nn.functional as F

from .modules import Actnorm
from .coupling import AffineCoupling


class InvertibleConv1x1(nn.Module):
    """ invertible 1x1 convolution used in Glow """

    def __init__(self, in_out_channels):
        super(InvertibleConv1x1, self).__init__()

        W = torch.zeros((in_out_channels, in_out_channels), dtype=torch.float32)
        nn.init.orthogonal_(W)
        LU, pivots = torch.lu(W)

        P, L, U = torch.lu_unpack(LU, pivots)
        self.P = nn.Parameter(P, requires_grad=False)
        self.L = nn.Parameter(L, requires_grad=True)
        self.U = nn.Parameter(U, requires_grad=True)
        self.I = nn.Parameter(torch.eye(in_out_channels), requires_grad=False)
        self.pivots = nn.Parameter(pivots, requires_grad=False)

        L_mask = np.tril(np.ones((in_out_channels, in_out_channels), dtype='float32'), k=-1)
        U_mask = L_mask.T.copy()
        self.L_mask = nn.Parameter(torch.from_numpy(L_mask), requires_grad=False)
        self.U_mask = nn.Parameter(torch.from_numpy(U_mask), requires_grad=False)

        s = torch.diag(U)
        sign_s = torch.sign(s)
        log_s = torch.log(torch.abs(s))
        self.log_s = nn.Parameter(log_s, requires_grad=True)
        self.sign_s = nn.Parameter(sign_s, requires_grad=False)

    def forward(self, z, log_det_jacobians):
        L = self.L * self.L_mask + self.I
        U = self.U * self.U_mask + torch.diag(self.sign_s * torch.exp(self.log_s))
        W = self.P @ L @ U

        B = z.size(0)
        C = z.size(1)
        z = torch.matmul(W, z.view(B, C, -1)).view(z.size())
        log_det_jacobians += torch.sum(self.log_s, dim=0)

        return z, log_det_jacobians

    def backward(self, y, log_det_jacobians):
        with torch.no_grad():
            LU = self.L * self.L_mask + self.U * self.U_mask + torch.diag(
                self.sign_s * torch.exp(self.log_s))
            y = torch.lu_solve(y.unsqueeze(-1), LU.unsqueeze(0),
                               self.pivots.unsqueeze(0)).squeeze(-1)
            log_det_jacobians -= torch.sum(self.log_s, dim=0)

        return y, log_det_jacobians


class Glow(nn.Module):

    def __init__(self, dims, n_layers=8):
        super(Glow, self).__init__()

        self.dims = dims
        self.n_layers = n_layers

        actnorms = []
        linears = []
        couplings = []
        for i in range(self.n_layers):
            actnorms.append(Actnorm(dims))
            linears.append(InvertibleConv1x1(dims[0]))
            couplings.append(AffineCoupling(dims, odd=i % 2 != 0))

        self.actnorms = nn.ModuleList(actnorms)
        self.linears = nn.ModuleList(linears)
        self.couplings = nn.ModuleList(couplings)

    def forward(self, y):
        z = y
        log_det_jacobians = torch.zeros(z.size(0), dtype=torch.float32, device=z.device)
        for i in range(self.n_layers):
            # actnorm
            z, log_det_jacobians = self.actnorms[i](z, log_det_jacobians)

            # invertible linear
            z, log_det_jacobians = self.linears[i](z, log_det_jacobians)

            # bijective coupling
            z, log_det_jacobians = self.couplings[i](z, log_det_jacobians)

        return z, log_det_jacobians

    def backward(self, z):
        y = z
        log_det_jacobians = torch.zeros(y.size(0), dtype=torch.float32, device=y.device)
        for i in reversed(range(self.n_layers)):
            # bijective coupling
            y, log_det_jacobians = self.couplings[i].backward(y, log_det_jacobians)

            # invertible linear
            y, log_det_jacobians = self.linears[i].backward(y, log_det_jacobians)

            # actnorm
            y, log_det_jacobians = self.actnorms[i].backward(y, log_det_jacobians)

        return y, log_det_jacobians