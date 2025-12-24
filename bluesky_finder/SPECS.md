NOTE This is an old spec, it is called bluesky-finder now.

The goal is to find accounts, dctech is just one example.

---

## Spec: DC-Area Techies Discovery on Bluesky (Python 3)

### 0) Goal

Identify Bluesky accounts likely to be **DC-area tech professionals** without asking for explicit city. Use **graph +
hashtag + curated-anchor signals**, then **LLM scoring** on profile + recent posts. Output a ranked list with evidence
and an audit trail.

Non-goals:

* “Perfect” geo accuracy. Expect probabilistic decisions.
* Full-firehose ingestion. Work with targeted discovery loops.

---

## 1) Definitions

### 1.1 “Candidate”

A Bluesky account (`did`, `handle`) that is plausibly:

* **Location**: DC / DMV / Northern VA / Montgomery / Prince George’s / Arlington / Alexandria, etc.
* **Profession/Interest**: software dev, SRE, data, PM, security, design, devrel, startup, etc.

### 1.2 Signals (examples)

**Seed / discovery signals**

* Posts containing hashtags: `#dctech`, `#dmvtech`, `#dc`, `#washingtondc`, etc. (configurable list)
* Follows / interactions with anchor accounts: e.g. `capitalweather.bsky.social` (configurable)
* Membership in lists/starter packs (if accessible via API) tied to DC tech (optional)

**Evaluation signals**

* Profile bio strings mentioning DC/DMV neighborhoods, local orgs, events
* Recent posts mentioning local weather, transit (WMATA, Metro), events, venues, sports
* Professional keywords: “engineer”, “developer”, “SWE”, “SRE”, “CTO”, “security”, etc.
* Weak signals: time-of-day patterns, local slang. Treat as low weight.

---

## 2) System Overview (Pipeline)

### 2.1 Stages

1. **Seed expansion**

    * From hashtags, anchors, and optionally followers/following graphs
2. **Candidate normalization**

    * Resolve `handle → did`, fetch profile, de-duplicate
3. **Content acquisition**

    * Fetch profile + *most recent 50 posts* (not “tweets”; they’re posts)
4. **LLM classification**

    * Prompt LLM with bio + posts; request structured score + rationale
5. **Ranking + storage**

    * Persist raw data, derived features, and LLM decisions with versioning
6. **Re-crawl scheduling**

    * Re-evaluate periodically; cache aggressively to minimize API and LLM calls

---

## 3) Data Model (Typed)

Use Python dataclasses or pydantic models (either is fine). Minimum typed structures:

### 3.1 Core entities

* `Did: NewType("Did", str)`
* `Handle: NewType("Handle", str)`
* `Uri: NewType("Uri", str)` (post URIs)
* `Timestamp: datetime`

### 3.2 Models

**Profile**

* `did: Did`
* `handle: Handle`
* `display_name: str | None`
* `description: str | None` (bio)
* `avatar_url: str | None`
* `followers_count: int | None`
* `follows_count: int | None`
* `indexed_at: datetime | None` (if provided by API)

**Post**

* `uri: Uri`
* `cid: str`
* `author_did: Did`
* `created_at: datetime`
* `text: str`
* `langs: list[str] | None`
* `reply_count: int | None`
* `repost_count: int | None`
* `like_count: int | None`

**Candidate**

* `did: Did`
* `handle: Handle`
* `discovery_sources: set[DiscoverySource]` (enum: hashtag, anchor_follow, anchor_interaction, etc.)
* `discovered_at: datetime`
* `profile: Profile | None`
* `posts: list[Post]` (0–50)
* `features: CandidateFeatures | None`
* `llm_eval: LlmEvaluation | None`

**CandidateFeatures** (lightweight, deterministic)

* `location_keywords_hit: list[str]`
* `tech_keywords_hit: list[str]`
* `hashtag_hits: list[str]`
* `anchor_hits: list[str]`
* `local_entities_hit: list[str]` (e.g., “WMATA”, “Rock Creek”)
* `language_hint: str | None`

**LlmEvaluation**

* `model: str`
* `prompt_version: str`
* `run_at: datetime`
* `score_location: float` (0–1)
* `score_tech: float` (0–1)
* `score_overall: float` (0–1)
* `label: Literal["match","maybe","no"]`
* `rationale: str` (short)
* `evidence: list[str]` (quotes/snippets; capped)
* `uncertainties: list[str]`
* `token_usage: dict[str,int] | None` (if available)

---

## 4) Inputs / Outputs

### 4.1 Inputs (config)

A single config object (typed) loaded from YAML/JSON/env:

* `seed_hashtags: list[str]` default includes `["dctech", "dmvtech"]`
* `anchor_handles: list[Handle]` e.g. `["capitalweather.bsky.social"]`
* `discovery_limits`:

    * max candidates per hashtag per run
    * max followers/following expansion depth (default 1)
    * max accounts per anchor graph expansion
* `fetch_posts_limit: int = 50`
* `min_interval_profile_refresh: timedelta`
* `min_interval_posts_refresh: timedelta`
* `min_interval_llm_refresh: timedelta` (only re-run if data changed or TTL exceeded)
* `cache_dir: Path`
* `db_path: Path` (SQLite recommended)
* `openrouter_model: str` and parameters (temperature, max_tokens)
* `openai_api_key_env: str` (or openrouter key env)
* `scoring_thresholds`:

    * `match_overall >= 0.75`
    * `maybe_overall >= 0.50` etc.

### 4.2 Output artifacts

* SQLite DB with:

    * raw profile snapshots (versioned)
    * raw post snapshots
    * LLM eval table (versioned by prompt+model)
    * run metadata (start/end, counts)
* Export formats:

    * JSONL of ranked candidates (for downstream CRM)
    * optional CSV summary

---

## 5) Discovery Methods

### 5.1 Hashtag-based

Use Bluesky search endpoints for posts containing `#<tag>` and/or `text: "<tag>"`.

* For each matching post:

    * take the author as candidate
    * optionally take participants (reply authors) if accessible

Dedup by `did`.

### 5.2 Anchor-based graph expansion

Given anchor handles:

* Resolve to `did`
* Pull:

    * followers list (bounded)
    * following list (bounded)
* Add each as candidate with source `anchor_follow`

Optionally:

* Pull recent posts by anchor; include accounts that reply/repost/like (if endpoints allow). Bounded.

### 5.3 Hybrid scoring pre-filter (cheap)

Before LLM:

* If neither location hints nor DC-related interactions exist, deprioritize.
* Keep a “cold storage” queue so you don’t lose them permanently.

---

## 6) Fetching Content

### 6.1 Profile fetch

* Use AT Protocol endpoint for profile by `did` or `handle`.
* Store snapshot with `fetched_at`.
* Only refetch if stale (TTL) or forced.

### 6.2 Posts fetch

* Fetch author feed (or posts list) with limit=50, newest first.
* Exclude reposts? Configurable:

    * Default: include original + replies; exclude pure reposts unless they contain commentary (if API distinguishes)
* Persist posts with stable identifiers (`uri`, `cid`).

### 6.3 Content normalization

* Strip excessive whitespace
* Preserve hashtags and proper nouns
* Cap per-post text length in LLM payload (avoid token blowups)
* Provide deterministic ordering (newest→oldest)

---

## 7) LLM Evaluation

### 7.1 LLM call trigger

Run LLM evaluation if:

* No prior eval exists, OR
* profile bio changed, OR
* new posts since last eval, OR
* TTL expired (config)

### 7.2 Prompt contract (structured)

Use a strict JSON schema output; reject non-JSON responses.
Request:

* location probability (0–1)
* tech/profession probability (0–1)
* overall (0–1)
* label match/maybe/no
* evidence list: short citations (<= 5), each referencing either bio or post index
* uncertainties list (<= 3)

### 7.3 LLM payload format

Provide:

* `profile`: handle, display name, bio
* `posts`: list of `{idx, created_at, text}`
* `discovery_sources`: hashtags hit, anchor relations
* `instructions`: decide if DC-area tech professional

### 7.4 Safety + privacy

* Only analyze publicly available info you fetched.
* Do not infer sensitive attributes beyond location/profession signals.
* Store LLM output but cap stored evidence to avoid retaining large text blobs unnecessarily.

---

## 8) Caching Strategy (Aggressive by default)

### 8.1 Cache layers

1. **HTTP response cache** (requests-cache or equivalent)

    * Cache GET responses keyed by URL+params+auth scope
    * TTL: profile/posts endpoints per config
2. **Persistent DB cache**

    * Profiles table with `etag`/`cid` if available
    * Posts table keyed by `uri` and `cid`
3. **LLM memoization**

    * Key = hash(prompt_version + model + normalized bio + normalized posts)
    * If key unchanged, skip call.

### 8.2 Invalidations

* New run doesn’t imply refresh.
* Refresh only on TTL expiry or explicit `--force-*` flags.

### 8.3 Deterministic hashing

* Canonical JSON encoding (sorted keys, stable list order)
* Hash algo: SHA-256

---

## 9) Ranking and Decision Logic

### 9.1 Primary ranking

Sort by:

1. `llm_eval.score_overall` desc
2. tie-breaker: `score_location` desc
3. tie-breaker: `score_tech` desc
4. tie-breaker: recency of latest post

### 9.2 Labels

* `match`: overall ≥ threshold_match
* `maybe`: between maybe and match
* `no`: below maybe threshold

### 9.3 Auditing

For each final candidate, retain:

* which discovery methods found them
* which anchors/hashtags triggered
* LLM evidence snippets (short)
* prompt_version and model

---

## 10) CLI / Entry Points

### 10.1 Commands

* `discover`: run discovery and enqueue candidates
* `fetch`: fetch/refresh profile+posts for queued candidates
* `evaluate`: run LLM evaluation for eligible candidates
* `export`: write JSONL/CSV for match/maybe

### 10.2 Common flags

* `--limit N`
* `--force-profile`, `--force-posts`, `--force-llm`
* `--since <date>`
* `--label match|maybe|no|all`
* `--dry-run` (no writes, no LLM calls)

---

## 11) Error Handling and Rate Limits

### 11.1 Network/API errors

* Retries with exponential backoff on transient errors (429/5xx)
* Respect server-provided rate limit headers if present
* Hard cap retries to avoid thundering loops

### 11.2 LLM failures

* If invalid JSON: retry once with “repair” instruction; if still invalid, mark eval as failed and continue.
* Store failures with reason and timestamp; do not retry repeatedly within a short window.

---

## 12) Testing Strategy

### 12.1 Unit tests

* normalization/hashing deterministic
* TTL logic correctness
* prompt serialization and JSON parsing strictness

### 12.2 Integration tests (record/replay)

* VCR-style HTTP fixtures for Bluesky endpoints
* Mock LLM responses (golden JSON)

### 12.3 Evaluation sanity set

* Curated list of known DC tech handles and non-DC controls
* Track precision/recall drift over time

---

## 13) Milestones

1. **MVP**

* hashtag discovery + profile+50 posts fetch + LLM eval + JSONL export + SQLite cache

2. **Graph expansion**

* anchor follower/following expansion + bounded paging + dedup

3. **Quality upgrades**

* deterministic feature extraction + better prompt + repair handling + dashboards (optional)

---

## 14) Open Questions / Assumptions (explicit)

* Assumption: AT Protocol endpoints used are available and stable for search, profiles, and author feeds.
* Unknown: exact availability of “who liked/reposted/replied” endpoints without additional indexing services. If
  unavailable, skip interaction expansion.
* Unknown: whether starter packs/lists are accessible easily; treat as optional.
