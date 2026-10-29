---
title: "Florian Hartig"
description: "Florian Hartig is a theoretical ecologist and ecological data scientist, Full Professor (W3) at the University of Regensburg."
# Research themes: drawn as a ring of five equal segments on the homepage
# (layouts/_shortcodes/research-wheel.html; equal on purpose — not shares)
# and as an expandable list on phones. `label` is the two-line text next to
# the ring, `title` the full wording, `text` the short description shown when
# a segment is hovered or clicked. (An optional `papers` list of publication
# keys adds linked papers.)
research_themes:
  - title: "Understanding the assembly of communities and biotic interaction networks"
    label: ["Community assembly &", "biotic interaction networks"]
    text: >-
      Why do some species coexist while others exclude each other, and how do networks of competition, pollination and other interactions arise? We combine data from forest plots, interaction networks and eDNA surveys with models to infer and test mechanisms such as density dependence and trait matching.
  - title: "Mechanisms behind biodiversity patterns in macroecology and macroevolution"
    label: ["Mechanisms behind", "biodiversity patterns"]
    text: >-
      Why are there more species in the tropics, and how did today's distribution of species richness arise? We link ecological and evolutionary processes such as speciation, dispersal, extinction and adaptation to large-scale patterns, using eco-evolutionary simulations such as gen3sis and phylogenetic models of diversification.
  - title: "Systems ecology and process-based simulation models"
    label: ["Process-based models of", "ecological systems"]
    text: >-
      How do forests, vegetation and populations respond to climate and land use? We develop and apply process-based models, from forest growth and dynamic vegetation models to population models, to understand and project the dynamics of ecological systems. R interfaces such as r3PG and rLPJGUESS make these models accessible.
  - title: "Model-data integration, simulation-based inference and Bayesian statistics"
    label: ["Model-data integration &", "Bayesian inference"]
    text: >-
      How can complex simulation models be fitted to data, and how certain are their predictions? We develop methods to calibrate process-based and stochastic models, from approximate Bayesian computation to Bayesian calibration and uncertainty quantification, and software such as BayesianTools that makes these methods usable.
  - title: "Statistics, machine learning and deep learning in ecology"
    label: ["Statistics, machine learning", "& deep learning in ecology"]
    text: >-
      How can statistics and machine learning deliver robust inference, not only predictions, from ecological data? We develop and test such methods; our R packages, such as DHARMa for residual diagnostics, sjSDM for joint species distribution models and cito for deep learning, bring them into everyday practice, and we apply them to predict and monitor biodiversity, for example in the BaySenseAI and bAImo projects.
research_center: ["Biodiversity", "in ecology, evolution", "and conservation"]
# Homepage overview tiles (layouts/_partials/overview.html). Publications
# and Software figures are computed from data/stats.yaml; the Projects and
# Teaching figures come from data/projects.yaml and data/courses.yaml.
overview:
  lead: "The outcome of our activities is documented through research papers, software, projects and teaching activities. To find out more about this, see below."
  publications:
    text: >-
      Ecological theory and statistical methods, applied to community ecology,
      macroecology, macroevolution and conservation.
  software:
    text: >-
      Open-source R packages for the methods we develop, from regression
      diagnostics to Bayesian inference and deep learning.
  # projects: tile text is generated from data/projects.yaml
  teaching:
    text: >-
      Ecology, statistics, data science and machine learning for BSc, MSc and
      PhD students; coordinator of the MSc Ecology, Evolution & Conservation.
---

## About me {.visually-hidden}

I am a theoretical ecologist and ecological data scientist. I am
head of the [Theoretical Ecology Group](https://www.uni-regensburg.de/biologie-vorklinische-medizin/forschen/arbeitsgruppen/ag-hartig)
and Deputy Dean of Research of the Faculty of Biology and Preclinical Medicine.
I arrived here in Regensburg via stops in Berlin, Uppsala, Leipzig and
Freiburg, as you can see below.

{{< career-tile >}}

## Research interests {.visually-hidden}

With my research group, I study the **mechanisms and principles underlying
biodiversity patterns**, using computer
simulations, statistical methods and, more recently, algorithms from machine
learning and artificial intelligence.

<p class="home-news">News from the group, such as new papers and new team members: <a href="https://www.uni-regensburg.de/biologie-vorklinische-medizin/forschen/arbeitsgruppen/ag-hartig/news" rel="noopener">group news page&nbsp;→</a></p>

Our work centres on five themes: how communities and biotic interaction networks
assemble; what drives biodiversity patterns in macroecology and macroevolution; how
ecological systems behave, studied with process-based models; how such models can be
integrated with data; and statistics and machine learning for ecology. To find out more
about these topics, please click on the topics in the <span class="only-wide">ring</span><span class="only-narrow">list</span> below.

{{< research-wheel >}}
