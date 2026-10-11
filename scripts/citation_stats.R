#!/usr/bin/env Rscript
# citation_stats.R
#
# Pulls citation statistics for every paper in bibliography/publications.bib:
#
#   1. Authoritative per-paper and total citation counts from Google Scholar,
#      via the `scholar` package reading your public profile. This is the
#      number that matches what's displayed on the website and on Scholar
#      itself.
#   2. The actual list of citing papers per publication, from OpenAlex.
#      Google Scholar has no API and no supported way to list who cited a
#      given paper (its "Cited by" pages are unstructured HTML with no
#      stable format, and scraping them at this scale reliably triggers
#      Google's bot detection) — OpenAlex is a free, documented, no-API-key
#      alternative that provides exactly this via a `filter=cites:<work_id>`
#      query per work. Its own aggregate citation counts run somewhat below Scholar's
#      (broader coverage vs. different indexing), which is why both sources
#      are reported side by side rather than picked as "the" number.
#
# Usage:
#   Rscript scripts/citation_stats.R
#
# Requires (install once):
#   install.packages(c("scholar", "httr2", "jsonlite", "dplyr", "purrr", "stringr", "tibble"))
#
# Output, written to citation_reports/ (gitignored, not part of the site):
#   - papers_summary.csv   one row per paper: key, title, year, doi,
#                          scholar_citations, scholar_pubid, openalex_citations
#   - citing_papers.csv    one row per (paper, citing paper) pair, from
#                          OpenAlex: cited_key, cited_title, citing_title,
#                          citing_year, citing_doi, citing_authors
#
# Runtime: a few minutes for ~110 papers, most of it deliberate pauses to
# stay within both services' rate limits.

suppressPackageStartupMessages({
  library(dplyr)
  library(purrr)
  library(stringr)
  library(tibble)
})

# R >= 4.4 ships this natively; defining it ourselves keeps the script working
# on older R and is a harmless no-op override otherwise.
`%||%` <- function(a, b) if (is.null(a)) b else a

# Under a C/POSIX locale R writes non-ASCII characters in titles as "<U+2010>".
invisible(Sys.setlocale("LC_CTYPE", "en_US.UTF-8"))

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCHOLAR_ID <- "AdcDit0AAAAJ"
BIB_PATH <- "bibliography/publications.bib"
OUT_DIR <- "citation_reports"

# Optional: OpenAlex's "polite pool" gives faster, more reliable responses to
# requests that identify a contact e-mail. Purely a courtesy to OpenAlex, not
# required — leave blank to use the (slower, shared) anonymous pool.
OPENALEX_MAILTO <- ""

dir.create(OUT_DIR, showWarnings = FALSE)

for (pkg in c("scholar", "httr2", "jsonlite")) {
  if (!requireNamespace(pkg, quietly = TRUE)) {
    stop(sprintf(
      "Package '%s' is not installed. Run:\n  install.packages(\"%s\")",
      pkg, pkg
    ), call. = FALSE)
  }
}

# ---------------------------------------------------------------------------
# 1. Parse key / title / year / doi out of the .bib
#
# Mirrors the brace-depth-matching approach in scripts/bib2content.py rather
# than a naive line-by-line regex, so LaTeX escapes like {\"u} inside other
# fields (which look like nested braces) don't throw off field boundaries.
# ---------------------------------------------------------------------------

read_bib_field <- function(body, field) {
  m <- regexpr(paste0("(?i)", field, "\\s*=\\s*\\{"), body, perl = TRUE)
  if (m == -1) return(NA_character_)
  start <- m + attr(m, "match.length")
  depth <- 1L
  i <- start
  n <- nchar(body)
  while (i <= n && depth > 0L) {
    ch <- substr(body, i, i)
    if (ch == "{") depth <- depth + 1L
    else if (ch == "}") depth <- depth - 1L
    i <- i + 1L
  }
  str_squish(substr(body, start, i - 2L))
}

parse_bib <- function(path) {
  text <- paste(readLines(path, warn = FALSE, encoding = "UTF-8"), collapse = "\n")
  starts <- gregexpr("@\\w+\\s*\\{", text, perl = TRUE)[[1]]
  if (starts[1] == -1) stop("No BibTeX entries found in ", path, call. = FALSE)
  lengths_ <- attr(starts, "match.length")

  entries <- map(seq_along(starts), function(idx) {
    open_brace <- starts[idx] + lengths_[idx] - 1L
    depth <- 1L
    i <- open_brace + 1L
    n <- nchar(text)
    while (i <= n && depth > 0L) {
      ch <- substr(text, i, i)
      if (ch == "{") depth <- depth + 1L
      else if (ch == "}") depth <- depth - 1L
      i <- i + 1L
    }
    body <- substr(text, open_brace + 1L, i - 2L)
    key <- str_trim(str_split_1(body, ",")[1])
    tibble(
      key   = key,
      title = read_bib_field(body, "title"),
      year  = read_bib_field(body, "year"),
      doi   = read_bib_field(body, "doi")
    )
  })
  bind_rows(entries)
}

normalize_title <- function(x) {
  x |> str_to_lower() |> str_replace_all("[^a-z0-9 ]", " ") |> str_squish()
}

message("Parsing ", BIB_PATH, " ...")
bib <- parse_bib(BIB_PATH)
message(sprintf("  %d entries, %d with a DOI", nrow(bib), sum(!is.na(bib$doi))))

# ---------------------------------------------------------------------------
# 2. Google Scholar: per-paper and total citation counts
# ---------------------------------------------------------------------------

message("Fetching your Google Scholar profile (", SCHOLAR_ID, ") ...")

scholar_pubs <- tryCatch(
  scholar::get_publications(SCHOLAR_ID),
  error = function(e) {
    warning(
      "Could not read the Google Scholar profile (", conditionMessage(e), "). ",
      "Scholar occasionally rate-limits or CAPTCHA-blocks automated requests; ",
      "if this keeps happening, wait a while and retry, or run this section by ",
      "hand later. Continuing with OpenAlex only.",
      call. = FALSE
    )
    NULL
  }
)

scholar_raw <- if (!is.null(scholar_pubs)) as_tibble(scholar_pubs) else NULL

if (!is.null(scholar_pubs)) {
  scholar_pubs <- scholar_pubs |>
    as_tibble() |>
    transmute(
      scholar_title = title,
      scholar_citations = cites,
      scholar_pubid = pubid,
      norm_title = normalize_title(title)
    )
  bib <- bib |> mutate(norm_title = normalize_title(title))

  matched <- bib |> inner_join(scholar_pubs, by = "norm_title")
  unmatched_bib <- bib |> anti_join(scholar_pubs, by = "norm_title")

  # Exact normalized-title match fails for the handful of cases where Scholar
  # truncates a long title with "…" — fall back to approximate matching
  # (base R's agrepl, no extra dependency) before giving up on a paper.
  if (nrow(unmatched_bib) > 0) {
    fuzzy <- map_dfr(seq_len(nrow(unmatched_bib)), function(i) {
      row <- unmatched_bib[i, ]
      hit <- agrepl(row$norm_title, scholar_pubs$norm_title, max.distance = 0.1)
      if (any(hit)) {
        bind_cols(row, scholar_pubs[which(hit)[1], c("scholar_title", "scholar_citations", "scholar_pubid")])
      } else {
        bind_cols(row, tibble(scholar_title = NA_character_, scholar_citations = NA_integer_, scholar_pubid = NA_character_))
      }
    })
    bib <- bind_rows(matched, fuzzy) |> select(-norm_title)
  } else {
    bib <- matched |> select(-norm_title)
  }

  still_unmatched <- sum(is.na(bib$scholar_citations))
  if (still_unmatched > 0) {
    message(sprintf(
      "  %d/%d papers could not be matched to a Scholar profile entry (title differs too much) — scholar_citations left NA for those.",
      still_unmatched, nrow(bib)
    ))
  }
} else {
  bib$scholar_title <- NA_character_
  bib$scholar_citations <- NA_integer_
  bib$scholar_pubid <- NA_character_
}

# ---------------------------------------------------------------------------
# 3. OpenAlex: citation counts + the actual list of citing papers
# ---------------------------------------------------------------------------

openalex_get <- function(url) {
  req <- httr2::request(url) |> httr2::req_user_agent("citation_stats.R (personal research script)")
  if (nzchar(OPENALEX_MAILTO)) req <- httr2::req_url_query(req, mailto = OPENALEX_MAILTO)
  req |>
    httr2::req_retry(max_tries = 3, backoff = \(i) 2^i) |>
    httr2::req_perform() |>
    httr2::resp_body_json()
}

openalex_work_for_doi <- function(doi) {
  tryCatch(
    openalex_get(paste0("https://api.openalex.org/works/doi:", utils::URLencode(doi, reserved = TRUE))),
    error = function(e) NULL
  )
}

openalex_citing_papers <- function(work_id, cited_key, cited_title) {
  # OpenAlex's older `cited_by_api_url` response field has been dropped from
  # current API responses, but it only ever pointed at this same
  # filter=cites:<id> query — building it directly from the work's own `id`
  # gets the identical result.
  out <- list()
  url <- paste0("https://api.openalex.org/works?filter=cites:", work_id, "&per-page=200&cursor=*")
  repeat {
    page <- tryCatch(openalex_get(url), error = function(e) NULL)
    if (is.null(page) || length(page$results) == 0) break

    rows <- map_dfr(page$results, function(w) {
      authors <- map_chr(w$authorships %||% list(), \(a) a$author$display_name %||% NA_character_)
      tibble(
        cited_key = cited_key,
        cited_title = cited_title,
        citing_title = w$title %||% NA_character_,
        citing_year = w$publication_year %||% NA_integer_,
        citing_doi = w$doi %||% NA_character_,
        citing_authors = paste(authors[!is.na(authors)], collapse = "; ")
      )
    })
    out[[length(out) + 1]] <- rows

    next_cursor <- page$meta$next_cursor
    if (is.null(next_cursor)) break
    # Replaces whatever cursor value is currently in the URL (the literal "*"
    # on the first page, a real cursor token from then on), so pagination
    # keeps advancing past the second page instead of looping on it.
    url <- sub("cursor=[^&]*", paste0("cursor=", next_cursor), url)
    Sys.sleep(0.1)
  }
  bind_rows(out)
}

dois <- bib |> filter(!is.na(doi))
message(sprintf("Fetching OpenAlex data for %d papers with a DOI ...", nrow(dois)))

openalex_results <- vector("list", nrow(dois))
citing_all <- vector("list", nrow(dois))

for (i in seq_len(nrow(dois))) {
  row <- dois[i, ]
  work <- openalex_work_for_doi(row$doi)
  if (is.null(work)) {
    message(sprintf("  [%d/%d] %s: not found in OpenAlex, skipping", i, nrow(dois), row$key))
    next
  }
  openalex_results[[i]] <- tibble(key = row$key, openalex_citations = work$cited_by_count %||% NA_integer_)

  if (!is.null(work$cited_by_count) && work$cited_by_count > 0 && !is.null(work$id)) {
    work_id <- sub("^https://openalex.org/", "", work$id)
    citing_all[[i]] <- openalex_citing_papers(work_id, row$key, row$title)
  }
  message(sprintf(
    "  [%d/%d] %s: %s citation(s)", i, nrow(dois), row$key,
    work$cited_by_count %||% "?"
  ))
  Sys.sleep(0.1) # stay well within OpenAlex's rate limit
}

openalex_summary <- bind_rows(openalex_results)
citing_papers <- bind_rows(citing_all)

# ---------------------------------------------------------------------------
# 4. Combine and write output
# ---------------------------------------------------------------------------

papers_summary <- bib |>
  select(key, title, year, doi, scholar_citations, scholar_pubid) |>
  left_join(openalex_summary, by = "key") |>
  arrange(desc(coalesce(scholar_citations, openalex_citations, 0L)))

readr_write <- function(df, path) {
  if (requireNamespace("readr", quietly = TRUE)) {
    readr::write_csv(df, path, na = "")
  } else {
    write.csv(df, path, row.names = FALSE, na = "")
  }
}

readr_write(papers_summary, file.path(OUT_DIR, "papers_summary.csv"))
readr_write(citing_papers, file.path(OUT_DIR, "citing_papers.csv"))

# ---------------------------------------------------------------------------
# 5. data/citations.yaml — feeds the per-paper citation count shown on each
#    publication page (layouts/publications/page.html) and in the
#    publications list (layouts/_partials/citation.html), via
#    hugo.Data.citations, the same pattern data/metrics.yaml already uses for
#    the homepage aggregate figures. Written by hand (not the `yaml` package)
#    for predictable, minimal-diff formatting since this file is re-generated
#    on every run.
# ---------------------------------------------------------------------------

citations_yaml_path <- "data/citations.yaml"
if (dir.exists("data")) {
  lines <- c(
    "# Per-paper citation counts, shown on each publication page and in the",
    "# publications list. Generated by scripts/citation_stats.R from Google",
    "# Scholar + OpenAlex — do not hand-edit, re-run the script to refresh.",
    sprintf('as_of: "%s"', format(Sys.Date(), "%d %B %Y")),
    sprintf('scholar_url: "https://scholar.google.de/citations?user=%s"', SCHOLAR_ID),
    sprintf('scholar_user: "%s"', SCHOLAR_ID),
    "papers:"
  )
  paper_lines <- papers_summary |>
    filter(!is.na(scholar_citations) | !is.na(openalex_citations)) |>
    pmap_chr(function(key, scholar_citations, scholar_pubid, openalex_citations, ...) {
      fields <- c(
        if (!is.na(scholar_citations)) sprintf("scholar: %d", as.integer(scholar_citations)),
        if (!is.na(scholar_pubid)) sprintf('scholar_id: "%s"', scholar_pubid),
        if (!is.na(openalex_citations)) sprintf("openalex: %d", as.integer(openalex_citations))
      )
      sprintf("  %s: { %s }", key, paste(fields, collapse = ", "))
    })
  writeLines(c(lines, paper_lines), citations_yaml_path)
  message(sprintf("  %s: %d papers", citations_yaml_path, length(paper_lines)))
}

# ---------------------------------------------------------------------------
# 6. data/software.yaml — citation data for the /software/ pages. Which
#    sources belong to a package is set in each content/software/*.md front
#    matter: `scholar_match` (regex over Scholar profile titles, for the
#    package's own entries — DHARMa's citations are split over many version
#    entries), `paper` (companion paper's .bib key) and `cran` (package name,
#    for the CRAN DOI 10.32614/CRAN.package.<name>, which OpenAlex indexes).
#    `top_citing` = the most-cited articles/reviews citing the package or its
#    paper, by their own OpenAlex citation count, Hartig's own excluded.
# ---------------------------------------------------------------------------

read_front_matter <- function(path) {
  txt <- readLines(path, warn = FALSE, encoding = "UTF-8")
  d <- which(txt == "---")
  if (length(d) < 2) return(list())
  yaml::yaml.load(paste(txt[(d[1] + 1):(d[2] - 1)], collapse = "\n"))
}

strip_tags <- function(x) trimws(gsub("\\s+", " ", gsub("<[^>]+>", "", x)))

is_own_work <- function(w) {
  any(map_lgl(w$authorships %||% list(), function(a) {
    identical(a$author$orcid, "https://orcid.org/0000-0002-6255-9059") ||
      identical(a$author$display_name, "Florian Hartig")
  }))
}

if (dir.exists("content/software") && requireNamespace("yaml", quietly = TRUE)) {
  message("Collecting software citation data ...")
  software_files <- list.files("content/software", pattern = "\\.md$", full.names = TRUE)
  software_files <- software_files[basename(software_files) != "_index.md"]
  software_entries <- list()

  for (f in software_files) {
    fm <- read_front_matter(f)
    slug <- sub("\\.md$", "", basename(f))
    entry <- list()

    rows <- NULL
    if (!is.null(scholar_raw) && !is.null(fm$scholar_match)) {
      rows <- scholar_raw[grepl(fm$scholar_match, scholar_raw$title, ignore.case = TRUE), ]
    }
    if (!is.null(scholar_raw) && !is.null(fm$paper)) {
      pid <- bib$scholar_pubid[bib$key == fm$paper]
      if (length(pid) == 1 && !is.na(pid)) rows <- bind_rows(rows, scholar_raw[scholar_raw$pubid == pid, ])
    }
    if (!is.null(rows) && nrow(rows) > 0) {
      rows <- distinct(rows, pubid, .keep_all = TRUE)
      cids <- unique(unlist(strsplit(as.character(na.omit(rows$cid)), ",")))
      entry$scholar <- as.integer(sum(rows$cites, na.rm = TRUE))
      entry$scholar_entries <- nrow(rows)
      if (length(cids)) {
        entry$scholar_cites_url <- paste0("https://scholar.google.com/scholar?cites=", paste(cids, collapse = ","))
      }
    }

    work_ids <- character()
    if (!is.null(fm$cran)) {
      w <- openalex_work_for_doi(paste0("10.32614/cran.package.", tolower(fm$cran)))
      if (!is.null(w)) {
        work_ids <- c(work_ids, w$id)
        entry$cran_ref <- list(
          title = strip_tags(w$display_name),
          authors = paste(map_chr(w$authorships, \(a) a$author$display_name %||% ""), collapse = ", "),
          doi = paste0("10.32614/CRAN.package.", fm$cran)
        )
      }
    }
    if (!is.null(fm$paper)) {
      doi <- bib$doi[bib$key == fm$paper]
      if (length(doi) == 1 && !is.na(doi)) {
        w <- openalex_work_for_doi(doi)
        if (!is.null(w)) work_ids <- c(work_ids, w$id)
      }
    }
    if (length(work_ids)) {
      url <- paste0(
        "https://api.openalex.org/works?filter=cites:",
        paste(sub("https://openalex.org/", "", work_ids), collapse = "|"),
        ",type:article|review&sort=cited_by_count:desc&per-page=25",
        "&select=id,display_name,publication_year,cited_by_count,doi,authorships,primary_location"
      )
      page <- tryCatch(openalex_get(url), error = function(e) NULL)
      if (!is.null(page)) {
        top <- head(Filter(Negate(is_own_work), page$results), 5)
        if (length(top)) {
          entry$top_citing <- map(top, function(w) {
            au <- map_chr(w$authorships %||% list(), \(a) a$author$display_name %||% "")
            list(
              title = strip_tags(w$display_name %||% ""),
              authors = if (length(au) > 2) paste(au[1], "et al.") else paste(au, collapse = " & "),
              year = w$publication_year,
              venue = w$primary_location$source$display_name %||% "",
              doi = sub("^https://doi.org/", "", w$doi %||% ""),
              cited_by = w$cited_by_count
            )
          })
        }
      }
    }
    if (length(entry)) software_entries[[slug]] <- entry
    message(sprintf("  %s: Scholar %s, top citing %d", slug, entry$scholar %||% "-", length(entry$top_citing)))
  }

  writeLines(c(
    "# Citation data for the /software/ pages. Generated by scripts/citation_stats.R",
    "# from Google Scholar + OpenAlex — do not hand-edit, re-run the script to refresh.",
    yaml::as.yaml(list(as_of = format(Sys.Date(), "%d %B %Y"), software = software_entries))
  ), "data/software.yaml")
  message(sprintf("  data/software.yaml: %d packages", length(software_entries)))
}

message("\nDone.")
message(sprintf("  %s: %d papers", file.path(OUT_DIR, "papers_summary.csv"), nrow(papers_summary)))
message(sprintf("  %s: %d citing-paper records", file.path(OUT_DIR, "citing_papers.csv"), nrow(citing_papers)))
message(sprintf(
  "  Total citations — Scholar: %s | OpenAlex: %s",
  sum(papers_summary$scholar_citations, na.rm = TRUE),
  sum(papers_summary$openalex_citations, na.rm = TRUE)
))
