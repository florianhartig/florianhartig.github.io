---
title: "sjSDM"
weight: 30
category: "Further packages from the group"
summary: "Scalable joint species distribution modelling, estimating the full species covariance matrix rather than approximating it."
paper: "pichler2021new"
links:
  - name: "GitHub"
    url: "https://github.com/TheoreticalEcology/s-jSDM"
  - name: "CRAN"
    url: "https://cran.r-project.org/web/packages/sjSDM/index.html"
---

An R package for fast and accurate **joint species distribution models**
(jSDMs) — multivariate generalized linear mixed models that describe how a
whole community of species responds to environmental predictors, to space, and
to each other.

The difficult part of a jSDM is the species–species covariance. Most
implementations approximate it with latent variables to keep the computation
tractable. sjSDM instead estimates the **full covariance matrix**, using
numerical simulation and a PyTorch backend so that it stays fast enough for
large community datasets. Alongside the model fitting it provides the tools
needed to interpret the result: ANOVA and variation partitioning,
metacommunity-structure analysis, and plotting.

Developed by Maximilian Pichler, with Florian Hartig. The method is described
in [Pichler & Hartig (2021)](/publications/pichler2021new/) in *Methods in
Ecology and Evolution*.
