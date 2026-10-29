---
title: "rLPJGUESS"
weight: 50
category: "Contributions to other projects"
summary: "An R interface to the LPJ-GUESS vegetation model, with parallel runs on workstations and HPC clusters."
paper: "bagnara2019r"
links:
  - name: "GitHub"
    url: "https://github.com/biometry/rLPJGUESS"
# Entry in the publication list: title and first-release year
# from the Crossref record of the CRAN DOI ; rLPJGUESS: title from its DESCRIPTION on GitHub, year of
# the companion paper (bagnara2019r), authors from the credit line below.
pub_entry:
  title: "rLPJGUESS: A R package that wraps the LPJ-GUESS 3.1 model"
  year: "2019"
  authors:
    - "Maurizio Bagnara"
    - "Florian Hartig"
    - "Ramiro Silveyra Gonzalez"
---

**rLPJGUESS** runs LPJ-GUESS, a dynamic global vegetation model, from within
R instead of through its own configuration files. Calibration and sensitivity
analysis need hundreds to thousands of model runs, so the package runs them in
parallel: on a workstation via SOCK clusters, on HPC systems via MPI. Combined
with a sampler such as [BayesianTools](/software/bayesiantools/), this makes
Bayesian calibration of LPJ-GUESS feasible.

The package targets LPJ-GUESS 3.1. It is not on CRAN and can be installed
from GitHub.

**Authors:** Maurizio Bagnara (maintainer), Florian Hartig,
Ramiro Silveyra Gonzalez.
