# Archive Report: MVP-2 Ollama Local-LLM Adapter

**Change**: mvp-2-ollama-adapter
**Archived**: 2026-07-21
**Verdict**: Fully implemented, verified PASS WITH WARNINGS (0 CRITICAL, 2 WARNING, 0 SUGGESTION), and archived.

## SDD Artifacts Archived

This archive contains the complete artifact trail for the MVP-2 Ollama Local-LLM Adapter change, closing the SDD cycle.

### Artifact Observation IDs (Engram traceability)

| Artifact | Topic Key | Observation ID | Status |
|----------|-----------|---|---|
| Proposal | sdd/mvp-2-ollama-adapter/proposal | 1412 | Complete |
| Spec | sdd/mvp-2-ollama-adapter/spec | 1422 | Complete |
| Design | sdd/mvp-2-ollama-adapter/design | 1423 | Complete |
| Tasks | sdd/mvp-2-ollama-adapter/tasks | 1424 | 23/23 complete |
| Verification Report | sdd/mvp-2-ollama-adapter/verify-report | 1430 | PASS WITH WARNINGS |

### Archived Contents

- `proposal.md` — Intent, scope, capabilities, approach, 8 key decisions
- `design.md` — Technical architecture, decisions, failure-mode mapping, file changes, interfaces
- `exploration.md` — Scope investigation, approaches considered, ollama HTTP surface, recommendations
- `tasks.md` — 23 implementation tasks across 4 phases (all checked)
- `verify-report.md` — Full verification with 96/96 tests passing, 0 CRITICAL issues
- `specs/` — 1 new capability specification (llm-adapter)

## Specifications Synced to Main Specs

One new capability was defined and is now archived as the source of truth. The delta spec is a full spec (no prior main spec existed).

### Synced to `openspec/specs/`

| Domain | Status | Details |
|--------|--------|---------|
| llm-adapter | Created | Thin resilient local Ollama LLM adapter; 7 requirements, 10 scenarios covering success, server-unreachable, timeout, model-not-found, malformed-response, config settings, injectable HTTP client |

**Note**: No existing main specs required merging — the llm-adapter is a new capability added by this change.

## Verification Summary

**Verdict**: PASS WITH WARNINGS (0 CRITICAL, 2 WARNING, 0 SUGGESTION)

- **Test Suite**: 96/96 passing (`uv run pytest -q`)
- **Lint**: All checks passed (`uv run ruff check .`)
- **Tasks**: 23/23 implementation tasks checked
- **Spec Coverage**: 7/7 requirements, 10/10 scenarios test-covered
- **Critical Issues**: 0 (no blockers found)

### Non-Blocking Findings

**WARNINGs:**
1. Spec scenario count in launch context (12) does not match actual spec content (10 scenarios across 7 requirements) — informational only, does not affect coverage
2. `apply-progress` reported new-test count (16: "10 + 6") off by one against actual count (15: 9 in `test_llm.py` + 6 in `test_config.py`) — minor bookkeeping inaccuracy in apply-phase report, not a coverage gap

All findings are non-blocking and do not prevent archive.

## Known Deferred Limitations

The following limitations are intentionally deferred to future releases and are recorded here for visibility:

| Limitation | Target | Notes |
|-----------|--------|-------|
| Retry/backoff on transient failures | v1.0 | Deferred to roadmap hardening phase. Timeout handling exists; backoff logic is v1.0. |
| Structured/JSON-schema output | hybrid filter slice | Format parameter pass-through and response schema negotiation are filter slice concerns, not this adapter. Adapter stays prompt-in / typed-text-out. |
| Source expansion (HF Daily Papers, HN Algolia, P2) | later MVP-2 slices | Out of scope for this local-LLM adapter. Feed collection remains mvc-1's responsibility. |
| Async/streaming generation | out of scope | Codebase is sync throughout; async adds no value for single sequential calls and complicates tests. Deferred if needed. |
| System prompt / `/api/chat` support | hybrid filter slice | `/api/generate` suffices for first slice. System-role separation is filter's concern when classification/prompt-engineering begins. |

## Spec Coverage

All 7 requirements in the spec are fully implemented and test-covered:

- **Successful Generation**: 1 scenario PASS (valid response returns typed result)
- **Server Unreachable Handling**: 1 scenario PASS (connection refused)
- **Timeout Handling**: 1 scenario PASS (request exceeds timeout)
- **Model Not Found Handling**: 1 scenario PASS (unpulled model → 404)
- **Malformed Response Handling**: 2 scenarios PASS (non-JSON body, missing response field)
- **Configuration-Driven Settings**: 2 scenarios PASS (defaults, overrides)
- **Injectable HTTP Client**: 2 scenarios PASS (injected client used directly, scoped client created when none injected)

All 10 scenarios independently verified via strict TDD (RED→GREEN→TRIANGULATE).

## Implementation Summary

**Scope**: 1 new capability (new package `synthesis/` with LLMClient port, OllamaClient adapter, LLMError hierarchy)
**Size**: ~320-390 changed lines across 5 files (2 new, 3 modified)
**Approach**: Strict TDD (httpx sync over `/api/generate` → typed `LLMResponse` or `LLMError`, zero network tests)
**Architecture**: Mirrors mvp-1 `HttpxFetcher` seam exactly: optional-injected `httpx.Client`, explicit `httpx.Timeout`, per-call client when none injected
**Failure Handling**: Typed exception hierarchy (`LLMUnavailableError`, `LLMTimeoutError`, `LLMModelNotFoundError`, `LLMResponseError`), never swallowed
**Config**: 3 additive `AIOBS_OLLAMA_*` env vars with hardcoded defaults; new `_float_env()` helper
**Dependencies**: No new runtime deps (reuse `httpx` + stdlib `json`)

## Rollback

This is a new feature slice with no existing behavior depending on it:
- Revert the feature branch (commit bac2fcc)
- Delete `synthesis/` package and `config.py` modifications
- No database migrations to unwind
- No data cleanup needed (synthesis/ is unused until the next MVP-2 filter slice)

## Next Steps

The MVP-2 Ollama Local-LLM Adapter is complete and closed. The next change follows from the project roadmap:

**Next change**: MVP-2 hybrid daily filter (consumes this `llm-adapter` port, adds classification logic, wires to item synthesis)

This adapter provides the typed `LLMClient` port the hybrid filter will depend on. The filter will add:
- Classification prompt engineering
- Structured output negotiation (`format`, JSON schema)
- System prompt wiring via `/api/chat` (future expansion)
- Retry/backoff orchestration (v1.0 hardening phase)

---

**Archive prepared**: 2026-07-21
**SDD Cycle**: Complete
**Status**: Ready for production merge and release.
