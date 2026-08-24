---
title: "rLPJGUESS"
weight: 50
category: "Contributions to other projects"
summary: "An R wrapper around the LPJ-GUESS dynamic global vegetation model, with support for parallel runs."
links:
  - name: "GitHub"
    url: "https://github.com/biometry/rLPJGUESS"
---

An R package that wraps **LPJ-GUESS**, a dynamic global vegetation model, so
that it can be driven from R rather than through its own configuration files.

The practical motivation is calibration and sensitivity analysis: those
require running the model hundreds or thousands of times, which is only
feasible in parallel. rLPJGUESS handles that on a workstation via SOCK
clusters and on HPC systems via MPI, which is what makes it usable together
with samplers such as [BayesianTools](/software/bayesiantools/).

Not on CRAN — install from the GitHub releases or build from source.

Developed by Maurizio Bagnara and Ramiro Silveyra Gonzalez, with Florian
Hartig, and described in [Bagnara et al. (2019)](/publications/bagnara2019r/)
in *Environmental Modelling & Software*.
