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
#   Rscript scripts/citation_stats.R                 # weekly: 5 history requests
#   Rscript scripts/citation_stats.R --histories=20  # while the histories are first filled (once a day)
#   (--citing also writes citing_papers.csv; --force overrides the one-run-per-20-h guard)
#
# Requires (install once):
#   install.packages(c("scholar", "httr2", "jsonlite", "yaml", "dplyr", "purrr", "stringr", "tibble"))
#
# Output for the site:
#   - data/stats.yaml      every citation and download figure the site shows
#                          (profile totals and citations per year, per-paper
#                          counts and histories, software data), from one run,
#                          written only if the consistency checks in section 7
#                          pass.
# Output for research, in citation_reports/ (gitignored, not part of the site):
#   - papers_summary.csv   one row per paper: key, title, year, doi,
#                          scholar_citations, scholar_pubid, openalex_citations, openalex_id
#   - citing_papers.csv    one row per (paper, citing paper) pair, from
#                          OpenAlex: cited_key, cited_title, citing_title,
#                          citing_year, citing_doi, citing_authors
#
# Runtime: about 15–20 minutes, most of it deliberate pauses to stay within
# Google Scholar's rate limits.

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
OPENALEX_MAILTO <- ""  # keep empty: no personal data in requests unless explicitly agreed

dir.create(OUT_DIR, showWarnings = FALSE)

# Rolling Scholar histories (section 6). Scholar is used despite its robots.txt, gently — 5 history requests per run, 20 while the
# file is first filled, at most one run per 20 hours.
ARGS <- commandArgs(trailingOnly = TRUE)
N_HIST <- if (any(grepl("^--histories=", ARGS))) as.integer(sub("^--histories=", "", grep("^--histories=", ARGS, value = TRUE)[1])) else 5L
PAUSE <- c(20, 40)  # seconds between history requests, drawn uniformly
LOG_PATH <- ".claude/maintenance/scholar_log.tsv"
QUEUE_PATH <- ".claude/maintenance/scholar_queue.json"
log_run <- function(what) {
  dir.create(dirname(LOG_PATH), recursive = TRUE, showWarnings = FALSE)
  cat(format(Sys.time(), "%Y-%m-%d %H:%M"), "\t", what, "\n", sep = "", file = LOG_PATH, append = TRUE)
}
if (file.exists(LOG_PATH) && !("--force" %in% ARGS)) {
  starts <- grep("\tstart\t", readLines(LOG_PATH), value = TRUE)
  if (length(starts)) {
    last <- as.POSIXct(substr(tail(starts, 1), 1, 16), format = "%Y-%m-%d %H:%M")
    hrs <- as.numeric(difftime(Sys.time(), last, units = "hours"))
    if (!is.na(hrs) && hrs < 20) {
      stop(sprintf("last Scholar run started %.1f h ago (%s) — at most one run per 20 h; use --force only if that run made no requests.",
                   hrs, LOG_PATH), call. = FALSE)
    }
  }
}
if (is.na(N_HIST) || N_HIST < 0 || N_HIST > 25) stop("--histories must be between 0 and 25", call. = FALSE)
log_run(sprintf("start\thistories=%d", N_HIST))

for (pkg in c("scholar", "httr2", "jsonlite", "yaml")) {
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
      doi   = read_bib_field(body, "doi"),
      # Optional pinned Scholar entry (`scholar_id = {pubid}` in the .bib) for
      # papers whose Scholar title differs too much for the title match
      # (e.g. truncated title, missing subtitle).
      scholar_id = read_bib_field(body, "scholar_id")
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
      "hand later.",
      call. = FALSE
    )
    NULL
  }
)

# get_publications() returns NA instead of throwing when Scholar refuses
# (HTTP 429). Without the Scholar list nothing can be written anyway (section 7
# requires it), so stop here instead of spending the OpenAlex budget.
if (!is.data.frame(scholar_pubs) || !all(c("title", "cites", "pubid") %in% names(scholar_pubs))) {
  stop("Google Scholar profile list unavailable — nothing written; data/stats.yaml unchanged.", call. = FALSE)
}
scholar_raw <- as_tibble(scholar_pubs)

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

  # Pinned entries first: matched by Scholar pubid, not by title.
  pinned <- bib |>
    filter(!is.na(scholar_id)) |>
    left_join(scholar_pubs |> select(scholar_pubid, scholar_title, scholar_citations),
              by = c("scholar_id" = "scholar_pubid")) |>
    mutate(scholar_pubid = scholar_id)
  if (nrow(pinned) > 0) {
    message(sprintf("  %d paper(s) pinned to a Scholar entry via scholar_id: %s", nrow(pinned),
                    paste(pinned$key, collapse = ", ")))
    if (any(is.na(pinned$scholar_citations)))
      warning("scholar_id not found in the Scholar profile: ",
              paste(pinned$key[is.na(pinned$scholar_citations)], collapse = ", "), call. = FALSE)
  }
  pinned <- pinned |> select(-norm_title)
  bib <- bib |> filter(is.na(scholar_id))

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
        # Approximate matches can pick the wrong Scholar entry — log them for a check.
        message(sprintf("  fuzzy match %s: \"%s\" <-> Scholar \"%s\"", row$key,
                        substr(row$title, 1, 70), substr(scholar_pubs$scholar_title[which(hit)[1]], 1, 70)))
        bind_cols(row, scholar_pubs[which(hit)[1], c("scholar_title", "scholar_citations", "scholar_pubid")])
      } else {
        bind_cols(row, tibble(scholar_title = NA_character_, scholar_citations = NA_integer_, scholar_pubid = NA_character_))
      }
    })
    bib <- bind_rows(pinned, matched |> select(-norm_title), fuzzy |> select(-norm_title))
  } else {
    bib <- bind_rows(pinned, matched |> select(-norm_title))
  }
  bib <- bib |> select(-scholar_id)

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

# The citing-paper lists (citation_reports/citing_papers.csv) are research data,
# not used by the site, capped at 200 per paper without an API key and costly
# for the shared keyless OpenAlex budget: only with --citing.
CITING <- "--citing" %in% commandArgs(trailingOnly = TRUE)
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
  openalex_results[[i]] <- tibble(key = row$key, openalex_citations = work$cited_by_count %||% NA_integer_,
                                  openalex_id = sub("^https://openalex.org/", "", work$id %||% NA_character_))

  if (CITING && !is.null(work$cited_by_count) && work$cited_by_count > 0 && !is.null(work$id)) {
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
# All lookups failed → bind_rows() gives a 0x0 tibble and the join below would
# crash. Keep the columns; the coverage check in section 7 decides.
if (!nrow(openalex_summary)) {
  openalex_summary <- tibble(key = character(), openalex_citations = integer(), openalex_id = character())
}
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

# (The CSVs are written at the end, only when the checks in section 7 pass.)

# ---------------------------------------------------------------------------
# 5. Software: per-package citation data for the /software/ pages. Which
#    sources belong to a package is set in each content/software/*.md front
#    matter: `scholar_match` (regex over Scholar profile titles, for the
#    package's own entries — DHARMa's citations are split over many version
#    entries), `paper` (companion paper's .bib key) and `cran` (package name,
#    for the CRAN DOI 10.32614/CRAN.package.<name>, which OpenAlex indexes,
#    and for download counts). `top_citing` = the most-cited articles/reviews
#    citing the package or its paper, by their own OpenAlex citation count,
#    Hartig's own excluded.
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

software_entries <- list()
software_pubids <- list()  # Scholar entries behind each package's total, for its yearly history (section 6)
if (dir.exists("content/software")) {
  message("Collecting software citation data ...")
  software_files <- list.files("content/software", pattern = "\\.md$", full.names = TRUE)
  software_files <- software_files[basename(software_files) != "_index.md"]

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
      # Entries that contribute citations: a package entry with 0 citations
      # beside its paper made "summed over 2 entries" misleading.
      entry$scholar_entries <- sum(rows$cites > 0, na.rm = TRUE)
      software_pubids[[slug]] <- rows$pubid
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

    # Yearly downloads from the Posit (RStudio) CRAN mirror via cranlogs, the
    # only CRAN mirror that publishes download logs.
    if (!is.null(fm$cran)) {
      dl <- tryCatch(
        httr2::request(paste0("https://cranlogs.r-pkg.org/downloads/daily/2012-10-01:last-day/", fm$cran)) |>
          httr2::req_retry(max_tries = 3) |> httr2::req_perform() |> httr2::resp_body_json(),
        error = function(e) NULL
      )
      days <- dl[[1]]$downloads
      if (length(days)) {
        yrs <- substr(map_chr(days, "day"), 1, 4)
        n <- map_int(days, \(d) as.integer(d$downloads %||% 0L))
        by_year <- tapply(n, yrs, sum)
        by_year <- by_year[cumsum(by_year) > 0]
        if (length(by_year)) {
          entry$downloads <- list(
            total = as.integer(sum(by_year)),
            years = as.list(as.integer(names(by_year))),
            counts = as.list(as.integer(by_year)),
            through = days[[length(days)]]$day
          )
        }
      }
    }

    if (length(entry)) software_entries[[slug]] <- entry
    message(sprintf("  %s: Scholar %s, downloads %s", slug, entry$scholar %||% "-", entry$downloads$total %||% "-"))
  }
}

# ---------------------------------------------------------------------------
# 6. Google Scholar profile totals and citations per year. Totals (citations,
#    h, i10) and the profile's yearly histogram are fetched back to back so
#    they describe the same moment, on every run.
#    Per-paper and per-package yearly histories need one request per Scholar
#    entry. They are fetched in a slow rolling queue —
#    at most N_HIST history requests per run (`--histories=N`, default 5;
#    20 a day while the file is first filled), 20–40 s apart, never fetched
#    first, then the oldest. get_article_cite_history() does not throw when
#    Scholar refuses — it returns an empty table — so 2 empty answers in a
#    row stop the queue. Every history keeps its own date; whatever was not
#    fetched in this run is carried over from the previous data/stats.yaml.
#    State (last attempt per item) and a run log are kept privately in
#    .claude/maintenance/.
# ---------------------------------------------------------------------------

STATS_PATH <- "data/stats.yaml"
TODAY <- format(Sys.Date(), "%Y-%m-%d")

previous <- if (file.exists(STATS_PATH)) yaml::read_yaml(STATS_PATH, fileEncoding = "UTF-8") else list()
# Under a non-UTF-8 locale read_yaml() can return NULL with only warnings; then
# every carried-over history and every drop check would silently vanish.
if (file.exists(STATS_PATH) && length(previous$papers) == 0) {
  stop("could not read the previous ", STATS_PATH, " (locale/encoding?) — nothing written.", call. = FALSE)
}

fill_years <- function(h) {
  if (is.null(h) || nrow(h) == 0) return(NULL)
  yrs <- seq(min(h$year), max(h$year))
  # as.list(): yaml::as.yaml writes a length-1 vector as a scalar, not a list.
  list(years = as.list(as.integer(yrs)), cites = as.list(as.integer(vapply(yrs, \(y) sum(h$cites[h$year == y]), numeric(1)))))
}

message("Fetching Scholar profile totals and yearly citations ...")
prof <- tryCatch(scholar::get_profile(SCHOLAR_ID), error = function(e) NULL)
prof_hist <- tryCatch(suppressWarnings(scholar::get_citation_history(SCHOLAR_ID)), error = function(e) NULL)

paper_history <- list()
history_date <- list()
software_history <- list()
pub_to_key <- setNames(bib$key, bib$scholar_pubid)
targets <- bib |> filter(!is.na(scholar_pubid), coalesce(scholar_citations, 0L) > 0) |>
  select(key, scholar_pubid, scholar_citations)

# The queue: every paper with citations, and every package (all Scholar entries
# behind its total, fetched together so its chart sums one moment).
queue_state <- if (file.exists(QUEUE_PATH)) jsonlite::fromJSON(QUEUE_PATH, simplifyVector = FALSE) else list()
last_paper <- function(k) {
  o <- previous$papers[[k]]
  if (is.null(o$years)) NA_character_ else (o$history_as_of %||% previous$as_of)
}
last_software <- function(slug) previous$software[[slug]]$scholar_history$as_of %||% NA_character_
sw_pids <- lapply(software_pubids, function(pids) {
  pids[vapply(pids, function(pid) isTRUE(scholar_raw$cites[scholar_raw$pubid == pid][1] > 0), logical(1))]
})
sw_pids <- sw_pids[lengths(sw_pids) > 0]
items <- bind_rows(
  tibble(kind = "paper", id = targets$key, cost = 1L, cites = as.integer(targets$scholar_citations),
         fetched = vapply(targets$key, last_paper, character(1))),
  tibble(kind = "software", id = names(sw_pids), cost = as.integer(lengths(sw_pids)),
         cites = vapply(names(sw_pids), function(x) as.integer(software_entries[[x]]$scholar %||% 0L), integer(1)),
         fetched = vapply(names(sw_pids), last_software, character(1)))
)
items$qid <- paste(items$kind, items$id, sep = ":")
items$tried <- vapply(items$qid, function(q) queue_state[[q]] %||% NA_character_, character(1))
# An item tried but answered empty counts as attempted on that day, so one
# entry Scholar cannot serve does not block the head of the queue forever.
items$last <- pmax(items$fetched, items$tried, na.rm = TRUE)
items <- items[order(!is.na(items$fetched), items$last, -items$cites, na.last = FALSE), ]
message(sprintf("History queue: %d items (%d never fetched); this run: up to %d requests, %d–%d s apart",
                nrow(items), sum(is.na(items$fetched)), N_HIST, PAUSE[1], PAUSE[2]))

used <- 0L
empties <- 0L
blocked <- FALSE
get_hist <- function(pid) {
  if (used > 0) Sys.sleep(runif(1, PAUSE[1], PAUSE[2]))
  used <<- used + 1L
  h <- tryCatch(suppressWarnings(scholar::get_article_cite_history(SCHOLAR_ID, pid)), error = function(e) NULL)
  if (is.null(h) || nrow(h) == 0) {
    empties <<- empties + 1L
    if (empties >= 2) blocked <<- TRUE
    return(NULL)
  }
  empties <<- 0L
  h
}
for (j in seq_len(nrow(items))) {
  it <- items[j, ]
  if (used >= N_HIST || blocked) break
  if (used > 0 && used + it$cost > N_HIST) next  # a big package only as the first item of a run
  queue_state[[it$qid]] <- TODAY
  if (it$kind == "paper") {
    h <- get_hist(targets$scholar_pubid[targets$key == it$id])
    if (!is.null(h)) {
      paper_history[[it$id]] <- fill_years(h)
      history_date[[it$id]] <- TODAY
      message(sprintf("  %s: history fetched", it$id))
    } else message(sprintf("  %s: empty answer", it$id))
  } else {
    parts <- list()
    for (pid in sw_pids[[it$id]]) {
      k <- unname(pub_to_key[pid])
      if (!is.na(k) && identical(history_date[[k]], TODAY)) {
        h <- paper_history[[k]]
        parts[[pid]] <- data.frame(year = unlist(h$years), cites = unlist(h$cites))
        next
      }
      h <- get_hist(pid)
      if (is.null(h)) { parts <- NULL; break }
      parts[[pid]] <- h[, c("year", "cites")]
      if (!is.na(k) && k %in% targets$key) {
        paper_history[[k]] <- fill_years(h)
        history_date[[k]] <- TODAY
      }
    }
    if (length(parts)) {
      software_history[[it$id]] <- c(fill_years(do.call(rbind, parts)), list(as_of = TODAY))
      message(sprintf("  software %s: history fetched (%d entries)", it$id, length(parts)))
    } else message(sprintf("  software %s: incomplete, previous history kept", it$id))
  }
}
if (blocked) message("  2 empty answers in a row — Scholar is probably refusing; queue stopped")

# Carry over everything not fetched in this run, with its own date.
for (k in setdiff(targets$key, names(paper_history))) {
  old <- previous$papers[[k]]
  if (!is.null(old$years)) {
    paper_history[[k]] <- list(years = as.list(as.integer(unlist(old$years))), cites = as.list(as.integer(unlist(old$cites))))
    history_date[[k]] <- old$history_as_of %||% previous$as_of
  }
}
for (slug in setdiff(names(software_pubids), names(software_history))) {
  old <- previous$software[[slug]]$scholar_history
  if (!is.null(old)) {
    software_history[[slug]] <- list(years = as.list(as.integer(unlist(old$years))),
                                     cites = as.list(as.integer(unlist(old$cites))),
                                     as_of = old$as_of %||% previous$as_of)
  }
}
message(sprintf("  histories: %d paper(s) fetched now, %d carried over; %d history requests used",
                sum(unlist(history_date) == TODAY), sum(unlist(history_date) != TODAY), used))
done_now <- c(paste0("paper:", names(history_date)[unlist(history_date) == TODAY]),
              paste0("software:", names(software_history)[vapply(software_history, function(h) identical(h$as_of, TODAY), logical(1))]))
log_run(sprintf("histories\trequests=%d\tfetched=%d\tblocked=%s\tnever_fetched_left=%d",
                used, length(done_now), blocked, sum(is.na(items$fetched) & !(items$qid %in% done_now))))
dir.create(dirname(QUEUE_PATH), recursive = TRUE, showWarnings = FALSE)
writeLines(jsonlite::toJSON(queue_state, auto_unbox = TRUE, pretty = TRUE), QUEUE_PATH)
message(sprintf("  software histories: %d packages", length(software_history)))

# ---------------------------------------------------------------------------
# 7. Assemble data/stats.yaml — the single data source for every citation and
#    download figure on the site — check it, and write it only if it passes.
# ---------------------------------------------------------------------------

stats <- list(
  as_of = TODAY,
  scholar = list(
    user = SCHOLAR_ID,
    profile_url = paste0("https://scholar.google.de/citations?user=", SCHOLAR_ID)
  ),
  profile = NULL,
  papers = list(),
  software = software_entries
)
if (!is.null(prof)) {
  stats$profile <- c(
    list(citations = as.integer(prof$total_cites), h_index = as.integer(prof$h_index),
         i10_index = as.integer(prof$i10_index)),
    fill_years(prof_hist)
  )
}
for (r in seq_len(nrow(papers_summary))) {
  row <- papers_summary[r, ]
  p <- list()
  if (!is.na(row$scholar_citations)) p$scholar <- as.integer(row$scholar_citations)
  if (!is.na(row$scholar_pubid)) p$scholar_id <- row$scholar_pubid
  if (!is.na(row$openalex_citations)) p$openalex <- as.integer(row$openalex_citations)
  if (!is.na(row$openalex_id %||% NA)) p$openalex_id <- row$openalex_id
  if (!is.null(paper_history[[row$key]])) {
    p <- c(p, paper_history[[row$key]], list(history_as_of = history_date[[row$key]]))
  }
  if (length(p)) stats$papers[[row$key]] <- p
}
for (slug in intersect(names(software_history), names(stats$software))) {
  stats$software[[slug]]$scholar_history <- software_history[[slug]]
}

errors <- character()
warnings_ <- character()
pr <- stats$profile
if (is.null(pr) || is.null(pr$citations) || is.na(pr$citations)) {
  errors <- c(errors, "Scholar profile totals missing")
} else {
  if (is.null(pr$years)) errors <- c(errors, "Scholar yearly citations missing")
  else {
    s <- sum(unlist(pr$cites))
    # Scholar's yearly histogram leaves out some citations (it never exceeds the
    # total, but runs a little below it), so allow a gap but never an excess.
    if (s > pr$citations * 1.005) errors <- c(errors, sprintf("yearly citations sum to %d, more than the total %d", s, pr$citations))
    if (pr$citations - s > 0.03 * pr$citations) warnings_ <- c(warnings_, sprintf("yearly citations (%d) are more than 3%% below the total (%d)", s, pr$citations))
  }
  old_total <- previous$profile$citations
  if (!is.null(old_total) && pr$citations < old_total * 0.99) {
    errors <- c(errors, sprintf("total citations fell from %d to %d", old_total, pr$citations))
  }
}
matched <- mean(!is.na(papers_summary$scholar_citations))
if (matched < 0.9) errors <- c(errors, sprintf("only %.0f%% of papers matched to Scholar", 100 * matched))
for (k in names(stats$papers)) {
  p <- stats$papers[[k]]
  if (!is.null(p$cites) && !is.null(p$scholar) && sum(unlist(p$cites)) > p$scholar + 2) {
    warnings_ <- c(warnings_, sprintf("%s: yearly citations (%d) exceed its total (%d) — history dropped", k, sum(unlist(p$cites)), p$scholar))
    stats$papers[[k]][c("years", "cites", "history_as_of")] <- NULL
  }
  old_n <- previous$papers[[k]]$scholar
  if (!is.null(old_n) && !is.null(p$scholar) && p$scholar < old_n * 0.9) {
    warnings_ <- c(warnings_, sprintf("%s: Scholar count fell from %d to %d", k, old_n, p$scholar))
  }
}

for (slug in names(stats$software)) {
  sw <- stats$software[[slug]]
  h <- sw$scholar_history
  if (!is.null(h) && !is.null(sw$scholar) && sum(unlist(h$cites)) > sw$scholar + 2 * (sw$scholar_entries %||% 1)) {
    warnings_ <- c(warnings_, sprintf("software %s: yearly citations (%d) exceed its total (%d) — history dropped", slug, sum(unlist(h$cites)), sw$scholar))
    stats$software[[slug]]$scholar_history <- NULL
  }
}

# Partial failures of OpenAlex or cranlogs must not silently remove figures
# from the site (counts, links, "How to cite", downloads): fail instead, so the
# previous file stays. Carry-over per source is the next step.
n_oa <- function(x) sum(vapply(x, function(p) !is.null(p$openalex), logical(1)))
if (length(previous$papers) && n_oa(stats$papers) < n_oa(previous$papers) - 2) {
  errors <- c(errors, sprintf("OpenAlex counts for %d papers, previously %d — OpenAlex unavailable?",
                              n_oa(stats$papers), n_oa(previous$papers)))
}
for (slug in names(previous$software)) {
  for (field in c("downloads", "cran_ref", "top_citing")) {
    if (!is.null(previous$software[[slug]][[field]]) && is.null(stats$software[[slug]][[field]])) {
      errors <- c(errors, sprintf("software %s: %s missing in this run (was present before)", slug, field))
    }
  }
}

for (w in warnings_) message("  WARNING: ", w)
if (length(errors)) {
  for (e in errors) message("  ERROR: ", e)
  message("  ", STATS_PATH, " NOT written — the previous version stays in place.")
} else {
  # Atomic write: temp file in the gitignored .claude/maintenance/tmp/ (same
  # volume), then rename — a crash never leaves a half-written file.
  tmp_dir <- ".claude/maintenance/tmp"
  dir.create(tmp_dir, recursive = TRUE, showWarnings = FALSE)
  tmp <- tempfile("stats-", tmpdir = tmp_dir, fileext = ".yaml")
  writeLines(c(
    "# All citation and download figures on the site. Generated by",
    "# scripts/citation_stats.R from Google Scholar, OpenAlex and cranlogs in one",
    "# run, checked for consistency before writing — do not hand-edit. Figures for",
    "# the current year are partial.",
    yaml::as.yaml(stats)
  ), tmp, useBytes = TRUE)
  if (!file.rename(tmp, STATS_PATH)) stop("could not move ", tmp, " to ", STATS_PATH)
  readr_write(papers_summary, file.path(OUT_DIR, "papers_summary.csv"))
  if (CITING) readr_write(citing_papers, file.path(OUT_DIR, "citing_papers.csv"))
  message(sprintf("  %s written: %d papers, %d packages, profile %d citations (h=%d, i10=%d)",
                  STATS_PATH, length(stats$papers), length(stats$software),
                  pr$citations, pr$h_index, pr$i10_index))
}

message("\nDone.")
message(sprintf("  %s: %d papers", file.path(OUT_DIR, "papers_summary.csv"), nrow(papers_summary)))
message(sprintf("  %s: %d citing-paper records", file.path(OUT_DIR, "citing_papers.csv"), nrow(citing_papers)))
