---
title: "ProfoundData"
weight: 60
category: "Contributions to other projects"
summary: "The PROFOUND database of European forest data, for calibrating, validating and benchmarking vegetation models."
paper: "reyer2020profound"
links:
  - name: "GitHub"
    url: "https://github.com/COST-FP1304-PROFOUND/ProfoundData"
  - name: "Database (PIK)"
    url: "https://doi.org/10.5880/PIK.2019.008"
---

An R package giving access to the **PROFOUND database** — a collection of
European forest site, climate and remote-sensing data assembled for
calibrating, validating and benchmarking dynamic vegetation models.

The point of the database is comparability. Forest models are usually
evaluated against whatever data the authors had to hand, which makes results
hard to compare across models; PROFOUND provides a common set so that
benchmarking exercises can be run on equal terms. The package downloads the
database and provides query and plotting functions over it.

Produced by COST Action FP1304 PROFOUND. The database itself is archived at
the Potsdam Institute for Climate Impact Research
([doi:10.5880/PIK.2019.008](https://doi.org/10.5880/PIK.2019.008)) and
described in [Reyer et al. (2020)](/publications/reyer2020profound/) in *Earth
System Science Data*.

The R package was archived from CRAN in June 2025 and is now available from
GitHub only; the database and the data paper are unaffected.
