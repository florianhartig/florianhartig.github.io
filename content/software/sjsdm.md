---
title: "sjSDM"
weight: 30
category: "Further packages from the group"
summary: "Fast joint species distribution models for large community datasets, estimating the full species covariance matrix."
paper: "pichler2021new"
cran: "sjSDM"
links:
  - name: "GitHub"
    url: "https://github.com/TheoreticalEcology/s-jSDM"
  - name: "CRAN"
    url: "https://cran.r-project.org/web/packages/sjSDM/index.html"
---

**sjSDM** fits joint species distribution models (jSDMs): models of how a
whole community of species responds to the environment, to space and to each
other. The difficult part of a jSDM is the species–species covariance matrix,
which most implementations approximate with a small number of latent
variables. sjSDM estimates the full matrix instead. It remains fast enough for
large community datasets, including eDNA data, because it approximates the
joint likelihood by Monte Carlo integration, implemented in PyTorch and run
on CPUs or GPUs.

Beyond fitting, the package partitions explained variation into
environmental, spatial and biotic components and can break this down by
species and site to reveal the
[internal structure of a metacommunity](/publications/leibold2022internal/).
It offers several response distributions, including the classical
multivariate probit model, terms for spatial autocorrelation, and the option
of replacing the linear predictor with a deep neural network.

**Authors:** Maximilian Pichler (maintainer), Florian Hartig.
**Contributors:** Wang Cai.
