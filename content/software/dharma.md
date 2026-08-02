---
title: "DHARMa"
weight: 10
category: "Main packages"
summary: "An R package for residual diagnostics for hierarchical (multi-level / mixed) regression models."
links:
  - name: "Documentation"
    url: "https://florianhartig.github.io/DHARMa/"
  - name: "GitHub"
    url: "https://github.com/florianhartig/DHARMa"
  - name: "CRAN"
    url: "https://cran.r-project.org/web/packages/DHARMa/index.html"
---

**D**iagnostics for **H**ier**A**rchical **R**egression **M**odels.

DHARMa uses a simulation-based approach to create readily interpretable scaled
(quantile) residuals for fitted generalized linear (mixed) models. The
resulting residuals are standardised to values between 0 and 1 and can be
interpreted as intuitively as residuals from a linear regression — which makes
model checking for GLMMs far more tractable than it usually is.
