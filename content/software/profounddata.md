---
title: "ProfoundData"
weight: 60
category: "Contributions to other projects"
summary: "An R interface to the PROFOUND database of European forest data for evaluating vegetation models."
paper: "reyer2020profound"
scholar_match: "^ProfoundData"
cran: "ProfoundData"
# Archived on CRAN 2025-06-13 (CRAN package page); downloads stay counted.
cran_archived: "2025-06-13"
links:
  - name: "GitHub"
    url: "https://github.com/COST-FP1304-PROFOUND/ProfoundData"
  - name: "Database (DOI)"
    url: "https://doi.org/10.5880/PIK.2020.006"
# Entry in the publication list: title and first-release year
# from the Crossref record of the CRAN DOI, authors from the credit line below.
pub_entry:
  title: "ProfoundData: Downloading and Exploring Data from the PROFOUND Database"
  year: "2020"
  doi: "10.32614/CRAN.package.ProfoundData"
  authors:
    - "Florian Hartig"
    - "Ramiro Silveyra Gonzalez"
    - "Christopher Reyer"
    - "Mats Mahnken"
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
openly available
([doi:10.5880/PIK.2020.006](https://doi.org/10.5880/PIK.2020.006)).

The package was archived from CRAN in June 2025 and remains available from
GitHub. The database itself is unaffected.

**Authors:** Florian Hartig (maintainer), Ramiro Silveyra Gonzalez,
Christopher Reyer, Mats Mahnken. **Contributors:** Friedrich Bohn.
