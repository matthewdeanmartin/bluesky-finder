# Recommendations: Scaling to 5,000 DC/East Coast Techies

## Current State

The pipeline discovers candidates via hashtag search + anchor account graph expansion,
then fetches profiles/posts and runs LLM scoring. This works but the current seed
configuration is very narrow: 3 generic hashtags and 1 anchor account will produce
hundreds, not thousands, of candidates.

## 1. Massively Expand Seed Hashtags

The current seeds (`#python`, `#terraform`, `#rstats`) are global and not DC-specific.
Add DC/DMV-specific and broader tech hashtags:

**DC/DMV location signals (high value):**
- `#dctech`, `#dmvtech`, `#washingtondc`, `#dc`, `#dmv`
- `#nova` (Northern VA), `#arlingtonva`, `#moco` (Montgomery County)
- `#wmata`, `#dcstartup`, `#dcjobs`, `#dctechjobs`
- `#govtech`, `#fedtech`, `#civictech` (DC-heavy niches)

**East Coast tech hubs:**
- `#nyctech`, `#bostontech`, `#philly`, `#rdu`, `#atl`
- `#techtwitter` (many east coasters migrated to Bluesky)

**Profession signals (to cast wider net):**
- `#infosec`, `#cybersecurity`, `#devops`, `#sre`, `#kubernetes`
- `#machinelearning`, `#datascience`, `#dataeng`
- `#webdev`, `#frontend`, `#backend`, `#rust`, `#golang`
- `#opensource`, `#buildinpublic`

This alone could 5-10x your candidate pool.

## 2. Add Many More Anchor Accounts

One anchor account is a trickle. You need 20-50 anchors to reach 5K scale.
Good anchor categories:

- **DC tech meetup organizers**: DCPython, NoVA Hackers, DC Golang, etc.
- **DC tech influencers/devrel**: people who post about DC tech events
- **DC-area companies**: Capital One tech, Booz Allen, MITRE, Palantir DC
- **Federal tech accounts**: USDS, 18F, GSA tech
- **East coast tech conferences**: speakers/organizers at local events
- **Local tech journalists/newsletters**: DC tech press accounts
- **Starter packs**: if any DC tech starter packs exist, mine their members

For each anchor, the tool pulls followers AND following. 50 anchors x 200 accounts
each = 10,000 raw candidates (many dupes, so ~3-5K unique).

## 3. Add New Discovery Methods

### 3a. Starter Pack / List Mining
Bluesky has "starter packs" and curated lists. If any DC tech lists exist,
scraping their members is the highest-signal discovery method. The AT Protocol
has `app.bsky.graph.getList` for this.

### 3b. Reply/Interaction Graph
When anchor accounts post, look at who replies/likes/reposts. These interactions
are a strong signal of being in the same community. Currently unused.

### 3c. Snowball / Second-Degree Expansion
After the first run, take your top-scoring "match" candidates and use THEM as
new anchors. This snowball effect is how you go from 1K to 5K. Add a
`run_snowball()` pipeline step that:
1. Queries DB for top N matches
2. Uses each as an anchor for follower/following expansion
3. Deduplicates against existing candidates

### 3d. Keyword Search on Bios
Use the Bluesky search API to find users whose bios contain location keywords
("DC", "DMV", "Arlington", "Bethesda", etc.) combined with tech terms.

## 4. Batch/Parallel Processing

At 5K candidates, sequential fetch + LLM eval will be very slow.

- **Async fetching**: Use `asyncio` + `httpx` for profile/post fetching. You can
  do 10-20 concurrent fetches while respecting rate limits.
- **LLM batching**: OpenRouter supports concurrent requests. Run 5-10 evals in
  parallel with `asyncio.gather()` or a thread pool.
- **Progress tracking**: Add a progress bar (the GUI already captures stdout;
  add `tqdm` or periodic count updates).

## 5. Improve the LLM Prompt for Scale

At 5K scale, LLM cost and accuracy both matter:

- **Use a cheaper model for pre-filtering**: Run a fast/cheap model (Gemini Flash,
  Haiku) on ALL candidates first with a simple yes/no. Only run the expensive
  model on "maybe" results.
- **Add discovery context to the prompt**: Tell the LLM which hashtags/anchors
  led to this candidate. This is strong context the current prompt doesn't include.
- **Tune thresholds down slightly**: A 0.50 "maybe" threshold might be too
  aggressive for DC-specific filtering. Consider 0.40 for the first pass to
  avoid losing borderline candidates.

## 6. Add a "Follow" Action

The pipeline finds candidates but doesn't help you follow them. Add:

- **Export as Bluesky list**: Use the AT Protocol to create a Bluesky list of
  matches. Then you can follow the whole list or review in the app.
- **Auto-follow with confirmation**: A GUI button that shows the next batch of
  matches and lets you approve/skip each one, then follows approved accounts
  via the API (`app.bsky.graph.follow`).
- **Follow tracking**: Track which candidates you've already followed in the DB
  to avoid re-processing.

## 7. Ongoing/Scheduled Runs

5K is not a one-shot goal. New people join Bluesky daily.

- **Schedule weekly runs**: Use the Makefile or a cron job to run discovery weekly.
- **Incremental mode**: Only fetch/evaluate new candidates (already supported via
  TTL, but make sure discovery doesn't skip existing candidates' new connections).
- **Decay/refresh**: Re-evaluate candidates whose posts are >30 days stale.
  People move, change jobs, etc.

## 8. Summary: Quickest Path to 5K

| Action | Effort | Expected yield |
|--------|--------|---------------|
| Add 30+ DC-specific hashtags | Low | +2,000 candidates |
| Add 20-50 anchor accounts | Low | +3,000 candidates |
| Snowball from top matches | Medium | +2,000 candidates |
| Starter pack/list mining | Medium | +500 high-quality |
| Async parallel fetching | Medium | 10x faster processing |
| Two-tier LLM (cheap pre-filter) | Medium | 5x cheaper at scale |
| Auto-follow integration | Medium | Actually reach the 5K follow goal |

Start with the first two rows — they're config-only changes you can make right
now in the GUI's Discovery tab.
