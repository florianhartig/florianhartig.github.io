---
title: "cito"
weight: 40
category: "Further packages from the group"
summary: "Deep neural networks in R with ordinary formula syntax, plus the explainable-AI tools to interpret them."
paper: "amesoder2024cito"
cran: "cito"
links:
  - name: "GitHub"
    url: "https://github.com/citoverse/cito"
  - name: "CRAN"
    url: "https://cran.r-project.org/web/packages/cito/index.html"
---

**cito** fits and interprets deep neural networks in R. A network is
specified with the same formula syntax as `lm` or `glm`, hyperparameters can
be tuned by cross-validation in the same call, and the package helps to detect
and handle convergence problems.

Predictions alone are rarely enough in ecology, so cito also provides the
tools to look inside a fitted network: variable importance, partial
dependence and accumulated local effect plots, and effect estimates, each
optionally with confidence intervals and p-values. It is built on the R
package torch, needs no Python installation, and runs on CPUs, GPUs and Mac
GPUs.

**Authors:** Christian Amesöder, Maximilian Pichler (maintainer).
**Contributors:** Florian Hartig, Armin Schenk.
