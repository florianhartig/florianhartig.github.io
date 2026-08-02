---
title: "cito"
weight: 40
category: "Further packages from the group"
summary: "Deep neural networks in R with ordinary formula syntax, plus the explainable-AI tools needed to interpret them."
links:
  - name: "GitHub"
    url: "https://github.com/citoverse/cito"
  - name: "CRAN"
    url: "https://cran.r-project.org/web/packages/cito/index.html"
---

An R package for building and training **deep neural networks** without
leaving the modelling idiom ecologists already use. A network is specified
with the same formula syntax as `lm` or `glm`, and hyperparameters can be
tuned under cross-validation from the same call.

Because a fitted network is only useful in ecology if you can say something
about *why* it predicts what it does, cito ships the interpretation tools
alongside: variable importance, partial dependence plots, accumulated local
effect plots, and bootstrapped confidence intervals. Everything is built on
`torch`, which is native to R — no Python installation required — and runs on
CPU or GPU.

Developed by Christian Amesöder, Maximilian Pichler, Florian Hartig and Armin
Schenk, and described in
[Amesöder et al. (2024)](/publications/amesoder2024cito/) in *Ecography*.
