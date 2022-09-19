#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
@Project ：rl-exploration-baselines
@File ：re3.py
@Author ：YUAN Mingqi
@Date ：2022/9/19 20:35
'''

from torch import nn
import torch
import numpy as np


class CNNEncoder(nn.Module):
    def __init__(self, kwargs) -> None:
        super(CNNEncoder, self).__init__()
        self.main = nn.Sequential(
            nn.Conv2d(kwargs['in_channels'], 32, (8, 8), stride=(4, 4)), nn.ReLU(),
            nn.Conv2d(32, 64, (4, 4), stride=(2, 2)), nn.ReLU(),
            nn.Conv2d(64, 32, (3, 3), stride=(1, 1)), nn.ReLU(), nn.Flatten(),
            nn.Linear(32 * 7 * 7, kwargs['embedding_size']))

    def forward(self, ob):
        x = self.main(ob)

        return x

class MLPEncoder(nn.Module):
    def __init__(self, kwargs) -> None:
        super(MLPEncoder, self).__init__()
        self.main = nn.Sequential(
            nn.Linear(kwargs['input_dim'], 64), nn.ReLU(),
            nn.Linear(64, 64), nn.ReLU(),
            nn.Linear(64, kwargs['embedding_size'])
        )

    def forward(self, ob):
        x = self.main(ob)

        return x


class RE3(object):
    def __init__(self,
                 envs,
                 device,
                 embedding_size,
                 beta,
                 kappa
                 ):
        """
        State Entropy Maximization with Random Encoders for Efficient Exploration (RE3)
        Paper: http://proceedings.mlr.press/v139/seo21a/seo21a.pdf

        :param envs: The environment to learn from.
        :param device: Device (cpu, cuda, ...) on which the code should be run.
        :param embedding_size: The dimension of encoding vectors of the observations.
        :param beta: The initial weighting coefficient of the intrinsic rewards.
        :param kappa: The decay rate.
        """

        if envs.action_space.__class__.__name__ == "Discrete":
            self.ob_shape = envs.observation_space.shape
            self.action_shape = envs.action_space.n
        elif envs.action_space.__class__.__name__ == 'Box':
            self.ob_shape = envs.observation_space.shape
            self.action_shape = envs.action_space.shape
        else:
            raise NotImplementedError
        self.device = device
        self.beta = beta
        self.kappa = kappa

        if len(self.ob_shape) == 3:
            self.encoder = CNNEncoder(
                kwargs={'in_channels': self.ob_shape[0], 'embedding_size': embedding_size})
        else:
            self.encoder = MLPEncoder(
                kwargs={'input_dim': self.ob_shape[0], 'embedding_size': embedding_size}
            )

        self.encoder.to(self.device)

        # freeze the network parameters
        for p in self.encoder.parameters():
            p.requires_grad = False

    def compute_irs(self, obs_array, time_steps, k=3):
        """
        Compute the intrinsic rewards using the collected observations.
        :param obs_array: The observations array of size ((n_steps, n_envs) + obs_shape).
        :param time_steps: The current time steps.
        :param k: The k value.
        :return: The intrinsic rewards
        """

        # compute the weighting coefficient of timestep t
        beta_t = self.beta * np.power(1. - self.kappa, time_steps)

        obs_tensor = torch.from_numpy(obs_array)
        obs_tensor = obs_tensor.to(self.device)
        size = obs_tensor.size()
        intrinsic_rewards = np.zeros(shape=(size[0], size[1]))

        for process in range(size[1]):
            encoded_obs = self.encoder(obs_tensor[:, process])
            for step in range(size[0]):
                dist = torch.norm(encoded_obs[step] - encoded_obs, p=2, dim=1)
                H_step = torch.log(torch.kthvalue(dist, k + 1).values + 1.)
                intrinsic_rewards[step, process] = H_step

        return beta_t * intrinsic_rewards