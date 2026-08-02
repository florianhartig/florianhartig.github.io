# florianhartig.github.io

Source for [florianhartig.github.io](https://florianhartig.github.io/), the
personal academic site of Florian Hartig — Professor of Theoretical Ecology at
the University of Regensburg.

Built with [Hugo](https://gohugo.io/) and deployed automatically to GitHub
Pages on every push to `main`.

## Building locally

Requires Hugo **extended**, no other dependencies (no theme, no Node, no Go
toolchain).

```bash
hugo server        # live preview at localhost:1313
hugo --gc --minify # production build, output in public/
```

## Updating the publication list

Publication pages are generated from `bibliography/publications.bib`. Edit
that file, then run:

```bash
python3 scripts/bib2content.py
```

This regenerates `content/publications/` — do not edit those files by hand.
