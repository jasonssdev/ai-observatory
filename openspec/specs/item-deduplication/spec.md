# item-deduplication Specification

## Purpose

Give every collected item a stable, persistent identity derived from its
canonical URL, and resolve same-story duplicates surfaced via title collision
within a single run.

## Requirements

### Requirement: Canonical URL Identity
The system MUST derive `id = sha256(canonical_url)`, where canonicalization
lowercases scheme/host, drops fragment, default port, and trailing slash, and
strips tracking params (`utm_*`, `ref`, `ref_src`, `fbclid`, `gclid`, `mc_cid`,
`mc_eid`, `igshid`, `source`, `cmpid`) while preserving other query params.

#### Scenario: Tracking params collapse to same id
- GIVEN two URLs identical except for a `utm_source` query param
- WHEN both are canonicalized and hashed
- THEN both produce the same id

#### Scenario: Non-tracking params remain distinct
- GIVEN two URLs identical except for a non-tracking query param (e.g. `page`)
- WHEN both are canonicalized and hashed
- THEN they produce different ids

### Requirement: Cross-Run Persistent Dedup
The id MUST be stable across runs, so the same canonical URL always maps to
the same id.

#### Scenario: Same item across two runs
- GIVEN a feed item collected today and the same item collected again tomorrow
- WHEN each is canonicalized and hashed
- THEN both runs produce the identical id

### Requirement: In-Run Title-Hash Collision Resolution
Within a single run, items whose normalized-title hash (lowercased,
punctuation/whitespace-normalized, sha256) collides but whose canonical URLs
differ MUST be deduplicated, keeping the item from the highest-priority
source (lowest priority integer); ties break by earliest `published_at`, then
lexically smallest id.

#### Scenario: Higher-priority source wins
- GIVEN the same story from a priority-1 source and a priority-2 source in one run
- WHEN title-hash collision is resolved
- THEN the priority-1 source's item is kept and the other is dropped

#### Scenario: Equal priority, earlier publish time wins
- GIVEN two colliding items with equal source priority but different published_at
- WHEN resolved
- THEN the item with the earlier published_at is kept

#### Scenario: Equal priority and time, lexical id tie-break
- GIVEN two colliding items with equal priority and equal published_at
- WHEN resolved
- THEN the item with the lexically smaller id is kept
