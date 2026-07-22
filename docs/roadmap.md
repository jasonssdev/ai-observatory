# Roadmap — MVPs

How AI Observatory is built: a small number of **vertical slices**, each usable and validatable on its own, growing toward the full system in [architecture.md](architecture.md).

## The approach, and why not one big MVP

It's tempting to build this in one shot — the project isn't huge. But the risky part of AI Observatory isn't the plumbing (fetching feeds, writing files); that's well-understood. The risk is **signal quality**: does the filter actually keep what matters, and does the weekly synthesis produce something you'd really turn into content? That can only be judged by using it.

So the build is split into three MVPs plus a final v1.0, as **vertical slices** rather than horizontal layers. Each MVP is something you run and validate yourself before the next is built. This matters because if you built everything at once and the weekly briefing came out mediocre, you couldn't tell whether the sources, the filter, or the synthesis was at fault. Slicing lets each layer's quality be confirmed with real usage before anything is stacked on top — and because each slice is small, the overhead of splitting is low. It also means the project is useful even if you stop early: MVP 1 alone already saves you the daily feed-checking.

**Answer to "how many MVPs":** three to reach a fully functional, automatic system, then a v1.0 that hardens it and closes coverage gaps. Each is deliberately small.

---

## MVP 1 — The daily record

**Status: Done ✓ (merged & archived).**

**Goal:** stop checking feeds by hand. Run one command, open one file, see the day's AI developments — deduplicated and linked.

**Included:**

- `uv` project scaffold (`pyproject.toml`), `config.py`, `cli.py` with a `collect` command.
- `sources.yaml` with ~8–10 **P1 RSS feeds** from [source-selection.md](source-selection.md) (OpenAI, DeepMind, Google AI, Import AI, Last Week in AI, Simon Willison, TLDR AI, Interconnects, Semianalysis…).
- `RssCollector` + deduplication (canonical URL + title hash).
- SQLite store (`items` table) as source of truth, plus a Markdown daily record grouped by category/priority.
- Tests for collector, dedup, and storage (success, malformed feed, duplicate item), per [AGENTS.md](../AGENTS.md).

**Not yet:** no LLM, no filtering (it shows everything collected), no weekly briefing, no scheduling (you run it manually), no JSON-API/bridged/Apify sources.

**How you validate it:** run `collect` for several days, open `data/records/<date>.md`. Is it capturing the day's real items? Any duplicates? Do the links work? Would you actually read this instead of visiting the sites?

**Done when:** a manual daily run produces a clean, deduplicated, readable record you'd genuinely open each morning.

---

## MVP 2 — Signal

**Status: Done ✓ (merged & archived).**

**Goal:** the daily record becomes *curated*, not a raw dump. Significant developments separated from routine noise.

**Included:**

- Ollama integration (`llm.py`) — the **local** LLM.
- The **hybrid daily filter**: deterministic rules first (source-priority auto-keep, HF/HN score-keep, category-routine, and noise-keyword) to decide the obvious cases, then local-LLM classification on what survives. The category-routine rule routes configured categories (default `research`) to routine. The daily record now keeps the significant items and sets aside the rest.
- Source expansion: the **JSON APIs** (HF Daily Papers with an upvote threshold, HN Algolia with a points threshold) and the P2 feeds.
- Tests for the filter (rule behavior, thresholds, malformed input).

**Not yet:** no weekly briefing, no scheduling, no bridged/Apify sources.

**How you validate it:** over a few days, compare the filtered record against the raw collection. Is it keeping what matters and hiding the noise? Tune the thresholds and the prompt yourself until it feels right.

**Done when:** the daily record reliably surfaces what's worth knowing and suppresses the routine — you trust it without cross-checking the raw list.

---

## MVP 3 — The weekly briefing + autopilot

**Goal:** the actual payoff — the weekly research material, produced automatically without you touching anything.

**Included:**

- **Weekly synthesis**: a ranked list of **at most 10 topics**, each with a one-line "why it matters" and its source links, with the traceability rule enforced (no topic without a backing item).
- `synthesize --daily` / `synthesize --weekly` CLI.
- **`launchd` agents**: daily (collect + filter) and weekly (briefing), running unattended. Idempotent runs so a missed day is safe to catch up.

**Not yet:** bridged (RSSHub) sources, Apify for X.

**How you validate it:** at the end of a week, open `data/briefings/<week>.md`. Could you sit down and create a video/article/post straight from it? Are the 10 topics the *right* 10? Is each one traceable to a real source?

**Done when:** the system runs on its own daily and weekly, and the briefing is usable as content research without you visiting a single source. **At this point the success criteria in [vision.md](vision.md#success-criteria) are met** — this is the functional product.

---

## v1.0 — Full coverage + hardening

**Goal:** close the coverage gaps the MVPs deferred, and make it durable enough to trust long-term.

**Included:**

- `RsshubCollector` (self-hosted RSSHub in Docker) for the no-RSS official blogs: **Anthropic first**, then Meta AI, Mistral, xAI, DeepSeek, The Batch.
- `ApifyCollector` — **optional, off by default** — for a small curated set of X/Twitter accounts (the zero-latency layer).
- Robustness: retries/backoff on flaky sources, a source-health report, structured logging, `.env.example`, finalized setup docs in the README.

**How you validate it:** coverage now includes the labs that have no feed; disable the optional collectors and confirm the system still runs fully on free RSS + local LLM.

**Done when:** coverage is effectively complete, optional cloud pieces are cleanly toggle-able, and a single failing source never breaks a run.

---

## At a glance

| Stage | Status | Delivers | You can validate | Runs automatically? | LLM |
| --- | --- | --- | --- | --- | --- |
| **MVP 1** | ✓ Shipped | Deduplicated daily record from P1 RSS feeds | "Is it catching the day, cleanly?" | No — manual `collect` | None |
| **MVP 2** | ✓ Shipped | Curated daily record (signal vs noise) + more sources | "Is the filter keeping the right things?" | No — manual | Ollama (filter) |
| **MVP 3** | Pending | Weekly ranked briefing (≤10 topics) + scheduling | "Could I make content from this?" | Yes — daily + weekly | Ollama (filter + briefing) |
| **v1.0** | Pending | Bridged + optional X sources, hardening | "Is coverage complete and resilient?" | Yes | Ollama |

Everything remains within the [non-goals](vision.md#non-goals): no real-time alerting, no auto-publishing, no multi-user/SaaS, no exhaustive crawling. The human always decides what becomes content.
