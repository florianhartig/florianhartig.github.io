---
title: "r3PG"
weight: 65
category: "Contributions to other projects"
summary: "An R/Fortran implementation of the 3-PG process-based forest growth model."
paper: "trotsiuk2020r3pg"
links:
  - name: "GitHub"
    url: "https://github.com/trotsiuk/r3PG"
  - name: "CRAN"
    url: "https://cran.r-project.org/package=r3PG"
---

An R package wrapping a **Fortran implementation of 3-PG** (Physiological
Processes Predicting Growth), one of the most widely used process-based
forest growth models worldwide. It can simulate monospecific stands as well
as mixtures of evergreen and deciduous tree species, even-aged or uneven-aged.

As with [rLPJGUESS](/software/rlpjguess/), the point of keeping the model fast
in Fortran while driving it from R is inference: it makes the repeated
evaluation needed for sensitivity analysis and Bayesian calibration practical.
It's a separate codebase from [threePGN](/software/threepgn/) below — that one
wraps the related but distinct 3PGN model variant.

Developed by Volodymyr Trotsiuk, with David I. Forrester and Florian Hartig,
and described in [Trotsiuk et al. (2020)](/publications/trotsiuk2020r3pg/) in
*Methods in Ecology and Evolution*.
