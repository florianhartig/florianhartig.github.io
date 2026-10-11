---
title: "ProfoundData"
weight: 60
category: "Contributions to other projects"
summary: "An R interface to the PROFOUND database of European forest data for evaluating vegetation models."
paper: "reyer2020profound"
scholar_match: "^ProfoundData"
cran: "ProfoundData"
links:
  - name: "GitHub"
    url: "https://github.com/COST-FP1304-PROFOUND/ProfoundData"
  - name: "Database (PIK)"
    url: "https://doi.org/10.5880/PIK.2019.008"
---

**ProfoundData** is an R interface to the PROFOUND database, which collects
data for evaluating vegetation models and simulating climate impacts at the
scale of forest stands. For nine forest sites across Europe it contains site
descriptions and soil, climate, CO₂, nitrogen-deposition, tree, stand and
remote-sensing data; for five of them also time series of carbon fluxes. The
package downloads the database and provides functions to query and plot it.

A shared dataset lets different forest models be benchmarked against the same
observations, rather than against whatever data each modelling team happened
to have. The database was produced by COST Action FP1304 PROFOUND and is
archived at the Potsdam Institute for Climate Impact Research
([doi:10.5880/PIK.2019.008](https://doi.org/10.5880/PIK.2019.008)).

The package was archived from CRAN in June 2025 and remains available from
GitHub. The database itself is unaffected.

**Authors:** Florian Hartig (maintainer), Ramiro Silveyra Gonzalez,
Christopher Reyer, Mats Mahnken. **Contributors:** Friedrich Bohn.
