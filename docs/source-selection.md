# Source Selection

> Operational source list for AI Observatory. This is the machine-readable counterpart to `docs/research.md`: `research.md` explains *who* is credible; this file lists *what the system actually ingests*, with real feed URLs verified on 2026-07-20.

## How to read this

Sources are split into two classes, following the local-first, high-signal principles in `docs/vision.md`:

- **Automatable** — has a real RSS/Atom feed or public JSON API. This is the engine of the system; it runs daily with zero intervention.
- **Bridged** — no official feed, but high enough value to be worth ingesting through a self-hosted feed generator (see [RSSHub](#no-feed-sources-the-bridge-layer) below).
- **Manual** — no reliable automated path (X, Discord, hard paywalls). You paste a link by hand only when something genuinely matters. Kept deliberately minimal.

Each source has a **priority** used later for filtering and ranking:

- **P1** — high signal, low noise. Primary sources and the best curators. Weight these heavily in the daily/weekly synthesis.
- **P2** — strong, moderate volume. Worth reading, some filtering needed.
- **P3** — high volume or broad; keep but filter aggressively by keyword/score.

`Type` is `RSS`, `Atom`, or `API`.

---

## Tier 1 — Frontier labs (primary sources)

The announcements themselves. When a model or feature ships, it appears here first.

| Source | Feed / API URL | Type | Priority | Notes |
| --- | --- | --- | --- | --- |
| OpenAI | `https://openai.com/news/rss.xml` | RSS | P1 | Official news feed. |
| Anthropic | *no official feed* → bridge | — | P1 | See [bridge layer](#no-feed-sources-the-bridge-layer). High value; worth bridging. |
| Google DeepMind | `https://deepmind.google/blog/rss.xml` | RSS | P1 | Research + model announcements. |
| Google (The Keyword, AI) | `https://blog.google/technology/ai/rss/` | RSS | P2 | Product/company AI news. |
| Google Research | `https://research.google/blog/rss/` | RSS | P2 | Deeper research posts (trailing slash required). |
| Meta AI | *no official feed* → bridge | — | P2 | Bridge `ai.meta.com/blog`. |
| Mistral AI | *no official feed* → bridge | — | P2 | Bridge `mistral.ai/news`. |
| xAI | *no official feed* → bridge | — | P3 | Bridge `x.ai/news`. |
| Qwen (Alibaba) | `https://qwenlm.github.io/blog/index.xml` | RSS | P2 | Official QwenLM blog. |
| DeepSeek | *no official feed* → bridge | — | P2 | Bridge `api-docs.deepseek.com/news`. |
| Microsoft Research | `https://www.microsoft.com/en-us/research/blog/feed/` | RSS | P3 | Use the `/blog/feed/` path (not `/research/feed/`). |

## Tier 2 — Research firehose

New papers. High volume — this is where filtering by upvotes/score matters most.

| Source | Feed / API URL | Type | Priority | Notes |
| --- | --- | --- | --- | --- |
| Hugging Face — Daily Papers | `https://huggingface.co/api/daily_papers` | API | P1 | JSON; already curated by community upvotes. Best signal-to-noise in this tier. Supports `?date=YYYY-MM-DD`. Filter by `upvotes`. |
| arXiv cs.AI | `https://rss.arxiv.org/rss/cs.AI` | RSS | P2 | Combine categories with `+`, e.g. `.../rss/cs.AI+cs.CL+cs.LG`. |
| arXiv cs.CL | `https://rss.arxiv.org/rss/cs.CL` | RSS | P2 | NLP / LLMs. |
| arXiv cs.LG | `https://rss.arxiv.org/rss/cs.LG` | RSS | P3 | Machine learning (broad, noisy). |
| arXiv stat.ML | `https://rss.arxiv.org/rss/stat.ML` | RSS | P3 | Optional. |
| Papers with Code | `https://paperswithcode.com/api/v1/papers/` | API | P3 | Paginated JSON. Hosting has been uncertain — treat as optional, check availability before relying on it. |

For richer arXiv metadata/search instead of the raw firehose, use the API: `http://export.arxiv.org/api/query?search_query=cat:cs.AI`.

## Tier 3 — Aggregators & community

Where the ecosystem reacts, and where undocumented releases surface. Good for catching what the labs *don't* announce.

| Source | Feed / API URL | Type | Priority | Notes |
| --- | --- | --- | --- | --- |
| Hacker News (AI, by date) | `https://hn.algolia.com/api/v1/search_by_date?query=AI&tags=story&numericFilters=points>30` | API | P1 | Best HN primitive. No key. Tune the `points>` threshold to control volume. |
| Hacker News front page | `https://hnrss.org/frontpage` | RSS | P2 | Or `https://news.ycombinator.com/rss`. |
| Reddit — r/LocalLLaMA | `https://www.reddit.com/r/LocalLLaMA/.rss` | RSS | P2 | Local-model community. **Requires a real User-Agent** — Reddit blocks default/empty UAs and rate-limits datacenter IPs. |
| Reddit — r/MachineLearning | `https://www.reddit.com/r/MachineLearning/.rss` | RSS | P3 | Same UA/rate-limit caveat. |

## Tier 4 — Newsletters & independent analysts

The curation layer. These people already did signal-vs-noise filtering; several are strong enough to weight like primary sources.

| Source | Feed URL | Type | Priority | Notes |
| --- | --- | --- | --- | --- |
| Import AI (Jack Clark) | `https://importai.substack.com/feed` | RSS | P1 | Policy, safety, geopolitics. Mirror: `https://jack-clark.net/feed/`. |
| Last Week in AI | `https://lastweekin.ai/feed` | RSS | P1 | Excellent weekly recap — pairs well with your own weekly synthesis. |
| Interconnects (Nathan Lambert) | `https://www.interconnects.ai/feed` | RSS | P1 | Deep, technical, RLHF/open-model focus. |
| Simon Willison | `https://simonwillison.net/atom/everything/` | Atom | P1 | Fast, practical, hands-on eval of new releases. |
| TLDR AI | `https://tldr.tech/api/rss/ai` | RSS | P1 | Daily technical bullets; great for catching links fast. |
| Ahead of AI (Sebastian Raschka) | `https://magazine.sebastianraschka.com/feed` | RSS | P2 | Training methods, architectures. |
| One Useful Thing (Ethan Mollick) | `https://www.oneusefulthing.org/feed` | RSS | P2 | Real-world/impact angle — useful for content framing. |
| Latent Space (swyx) | `https://www.latent.space/feed` | RSS | P2 | Applied AI engineering. |
| The Decoder | `https://the-decoder.com/feed/` | RSS | P2 | Independent, EU perspective, factual. |
| AI Snake Oil (Narayanan & Kapoor) | `https://www.aisnakeoil.com/feed` | RSS | P2 | Skeptical counterweight — valuable for balanced content. |
| Ben's Bites | `https://www.bensbites.com/feed` | RSS | P2 | Startup/funding lens. Use this exact URL (not `/news`). |
| The Neuron | `https://rss.beehiiv.com/feeds/N4eCstxvgX.xml` | RSS | P3 | Business-focused, lighter. |
| The Batch (DeepLearning.AI) | *no official feed* → bridge | — | P2 | Andrew Ng's weekly. Bridge required. |
| Stratechery (Ben Thompson) | `https://stratechery.com/feed/` | RSS | P3 | Free weekly only; daily analysis is a paid personalized feed. Optional. |

## Tier 5 — Tech news / industry

Broad outlets. Keep for M&A, funding, adoption, and security stories; filter hard.

| Source | Feed URL | Type | Priority | Notes |
| --- | --- | --- | --- | --- |
| Semianalysis (Dylan Patel) | `https://www.semianalysis.com/feed` | RSS | P1 | Best open source on hardware/infra/compute economics. |
| VentureBeat AI | `https://venturebeat.com/category/ai/feed/` | RSS | P2 | Enterprise adoption, security, B2B. |
| TechCrunch AI | `https://techcrunch.com/category/artificial-intelligence/feed/` | RSS | P2 | Funding and startup news. |
| MIT Technology Review AI | `https://www.technologyreview.com/topic/artificial-intelligence/feed/` | RSS | P2 | Deeper, slower, policy/society. |
| Ars Technica (tech) | `https://feeds.arstechnica.com/arstechnica/technology-lab` | RSS | P3 | No dedicated AI feed — filter by keyword. |
| The Verge | `https://www.theverge.com/rss/index.xml` | RSS | P3 | Main feed — filter by keyword (AI sub-slug unconfirmed). |

## Tier 6 — Tooling, changelogs & model catalogs

Quiet but important: capability and pricing changes that ship without a press release.

| Source | Feed / API URL | Type | Priority | Notes |
| --- | --- | --- | --- | --- |
| Ollama | `https://ollama.com/blog/rss.xml` | RSS | P2 | Local inference; relevant to local-first workflows. |
| Hugging Face — Blog | `https://huggingface.co/blog/feed.xml` | RSS | P2 | Library/tooling releases. |
| models.dev | `https://models.dev/api.json` | API | P2 | Open model/pricing/spec catalog. Poll and diff to detect new models, price and context-window changes. Large payload. |
| GitHub releases (per repo) | `https://github.com/{owner}/{repo}/releases.atom` | Atom | P2 | No auth for public repos. Track key repos (transformers, vllm, llama.cpp, ollama, etc.). Also `.../tags.atom`, `.../commits/{branch}.atom`, and user/org `https://github.com/{user}.atom`. GitHub Trending has **no** official feed. |

---

## No-feed sources: the bridge layer

Several high-value official sources publish no RSS: **Anthropic, Meta AI, Mistral, xAI, DeepSeek, The Batch** (and, if wanted, specific X accounts). Rather than writing a fragile scraper for each, run one self-hosted [**RSSHub**](https://docs.rsshub.app) instance locally (Docker). It fits the local-first principle, turns all of these into normal feeds your collector reads uniformly, and is the single most valuable piece of infrastructure for coverage.

Priority sources to bridge, in order: **Anthropic** (P1), Meta AI, Mistral, DeepSeek, The Batch (all P2), xAI (P3). If RSSHub lacks a route for one, a scoped scraper of that single `/news` page or a hosted generator (RSS.app) is the fallback.

## Manual / curated layer (deliberately minimal)

Not automated. These stay manual because reliable automation isn't possible or worth it, and because the automatable tiers above already capture the same news secondhand within hours.

- **X / Twitter accounts** (`@OpenAI`, `@AnthropicAI`, `@sama`, `@_akhaliq`, `@karpathy`, `@simonw`, etc., per `research.md`). No stable API. Optionally bridge a *few* critical accounts via RSSHub, but expect breakage. Treat X as read-when-curious, not as a system input.
- **Discord servers** (Anthropic Developer, Latent Space, Hugging Face, EleutherAI). Ephemeral, closed — read live when debugging, never ingested.
- **The Information.** Full-text feed is authenticated/paid (`subscriber_feed`); the public feed is teasers only. Manual unless you hold a subscription.

---

## Ingestion notes (for the collector)

- **Send a real `User-Agent` header** on every request. Reddit and several outlets reject default/empty UAs outright.
- **Handle gzip.** Google, Hugging Face, Microsoft, Qwen feeds are served compressed; a standard RSS library (e.g. `feedparser`) handles this transparently.
- **Deduplicate by canonical URL** (strip UTM/query params) plus a title hash. The same story arrives via multiple feeds — dedup is essential to the daily record (`vision.md`).
- **Respect rate limits.** arXiv and Reddit throttle aggressive polling. Once daily is well within limits; add a small delay between requests.
- **Threshold the firehose tiers.** Apply `upvotes`/`points` cutoffs to HF Daily Papers and Hacker News before they reach synthesis, or the noise floor swamps the signal.
- **Store raw + normalized.** Keep the original entry and a normalized record (`title, url, source, source_priority, published_at, summary`) so every insight stays traceable to its source.

## Coverage summary

Automatable today, no bridge needed: **~28 feeds/APIs** catalogued as candidates across labs, research, community, newsletters, news, and tooling — of which **25 are currently wired** in `sources.yaml` (the P1 + P2 set). Add one local RSSHub instance and the six bridged sources (Anthropic first) and coverage is effectively complete for a high-signal, low-intervention system. X and Discord remain the only genuinely manual gaps — and their news reliably reaches the automated tiers within hours.

_Last verified: 2026-07-20._
