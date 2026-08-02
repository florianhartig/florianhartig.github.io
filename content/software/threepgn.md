---
title: "threePGN"
weight: 70
category: "Contributions to other projects"
summary: "A Fortran implementation of the 3PGN forest growth model, callable from R."
links:
  - name: "GitHub"
    url: "https://github.com/checcomi/threePGN-package"
---

An R package wrapping a **Fortran implementation of 3PGN**, a
process-based forest growth model, so that it can be called from R.

As with [rLPJGUESS](/software/rlpjguess/), the reason for the wrapper is
inference: keeping the model fast in Fortran while driving it from R makes the
repeated evaluation that Bayesian calibration needs practical.

The package is marked as work in progress and is not on CRAN. Compiling on
Windows needs Rtools, because of the C++ and Fortran components.
