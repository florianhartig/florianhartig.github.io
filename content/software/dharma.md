---
title: "DHARMa"
weight: 10
category: "Main packages"
summary: "Simulation-based residual diagnostics for generalized linear mixed models and other hierarchical regression models."
scholar_match: "dharma|residual diagnostics for hierarchi"
cran: "DHARMa"
links:
  - name: "Documentation"
    url: "https://florianhartig.github.io/DHARMa/"
  - name: "GitHub"
    url: "https://github.com/florianhartig/DHARMa"
  - name: "CRAN"
    url: "https://cran.r-project.org/web/packages/DHARMa/index.html"
  - name: "r-universe"
    url: "https://florianhartig.r-universe.dev/DHARMa"
---

**DHARMa** (**D**iagnostics for **H**ier**A**rchical **R**egression **M**odels)
checks whether a fitted regression model is consistent with the data it was
fitted to. For generalized linear and mixed models, raw residuals are hard to
interpret. DHARMa instead simulates new data from the fitted model and uses
them to compute scaled (quantile) residuals. These are standardized to values
between 0 and 1 and can be read as intuitively as residuals from a linear
regression.

Building on these residuals, the package provides plots and tests for typical
misspecification problems: over- and underdispersion, zero-inflation, and
residual spatial, temporal and phylogenetic autocorrelation. Supported are
models from lme4, glmmTMB, GLMMadaptive, spaMM, mgcv (GAMs), phylolm and
simple brms models, as well as `lm` and `glm` (including negative binomial
models from MASS). Simulations created elsewhere, for example posterior
predictive simulations from JAGS, Stan or BUGS, can be processed too.

Since 2024 the package has been extended in a project funded by the DFG; see
[Projects](/projects/).

**Authors:** Florian Hartig (maintainer). **Contributors:** Lukas Lohse,
Melina de Souza Leite, Cosmina Werneke.
