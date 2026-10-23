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
# Entry in the publication list: title and first-release year
# from the Crossref record of the CRAN DOI, authors from the credit line below.
pub_entry:
  title: "DHARMa: Residual Diagnostics for Hierarchical (Multi-Level / Mixed) Regression Models"
  year: "2016"
  doi: "10.32614/CRAN.package.DHARMa"
  authors:
    - "Florian Hartig"
---

**DHARMa** (**D**iagnostics for **H**ier**A**rchical **R**egression **M**odels)
checks whether a fitted regression model is consistent with the data it was
fitted to. For generalized linear and mixed models, raw residuals are hard to
interpret. DHARMa instead simulates new data from the fitted model and uses
them to compute scaled (quantile) residuals. These are standardised to values
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

Questions, bug reports and feature requests: see the
[CRAN page](https://cran.r-project.org/package=DHARMa) and use the
issue tracker linked there under "BugReports".

**Authors:** Florian Hartig (maintainer). **Contributors:** Lukas Lohse,
Melina de Souza Leite, Cosmina Werneke.
