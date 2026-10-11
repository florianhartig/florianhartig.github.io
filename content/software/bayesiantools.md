---
title: "BayesianTools"
weight: 20
category: "Main packages"
summary: "MCMC and SMC samplers and diagnostics for Bayesian statistics, with a focus on calibrating complex process-based models."
scholar_match: "^BayesianTools"
cran: "BayesianTools"
links:
  - name: "GitHub"
    url: "https://github.com/florianhartig/BayesianTools"
  - name: "CRAN"
    url: "https://cran.r-project.org/web/packages/BayesianTools/index.html"
  - name: "r-universe"
    url: "https://florianhartig.r-universe.dev/BayesianTools"
---

**BayesianTools** provides general-purpose samplers, plots and diagnostics
for Bayesian statistics. It was written with a particular focus on calibrating
complex process-based models, where every evaluation of the likelihood means running a simulation.

The model enters as an R function that returns the log-likelihood, so any
simulation model that can be called from R can be calibrated, including those
wrapped by [rLPJGUESS](/software/rlpjguess/) and [r3PG](/software/r3pg/).
Implemented samplers include several Metropolis variants (among them adaptive
and delayed-rejection Metropolis–Hastings), the T-walk, two
differential-evolution MCMCs, two DREAM samplers and a sequential Monte Carlo
particle filter. Further functions cover convergence diagnostics, plotting and
model comparison via the marginal likelihood and WAIC.

**Authors:** Florian Hartig (maintainer), Francesco Minunno, Stefan Paul.
**Contributors:** David Cameron, Tankred Ott, Maximilian Pichler.
