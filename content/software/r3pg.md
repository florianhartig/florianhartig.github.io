---
title: "r3PG"
weight: 65
category: "Contributions to other projects"
summary: "A fast R interface to the 3-PG forest growth model, for pure and mixed stands."
paper: "trotsiuk2020r3pg"
scholar_match: "^Package.{1,3}r3PG"
cran: "r3PG"
aliases: ["/software/threepgn/"]
links:
  - name: "GitHub"
    url: "https://github.com/trotsiuk/r3PG"
  - name: "CRAN"
    url: "https://cran.r-project.org/package=r3PG"
---

**r3PG** wraps a Fortran implementation of 3-PG (Physiological Processes
Predicting Growth), one of the most widely used forest growth simulators
worldwide, in an R package. It covers both model versions: 3-PGpjs for
even-aged, monospecific, evergreen stands, and 3-PGmix for deciduous,
uneven-aged or mixed-species stands.

Compiled code makes the model fast enough for sensitivity analysis and full
Bayesian calibration, which both require running it many times.

r3PG succeeds **threePGN**, an earlier R package by Francesco Minunno,
Florian Hartig and Volodymyr Trotsiuk that wrapped a Fortran implementation
of 3PGN, a variant of the 3-PG model. threePGN is no longer maintained; its
code remains available on
[GitHub](https://github.com/ForModLabUHel/threePGN-package).

**Authors:** Volodymyr Trotsiuk (maintainer), Florian Hartig,
David Forrester, Ramiro Silveyra Gonzalez.
