## 1. High-Level Overview

- **Goal**: Turn recent public GROWW app reviews (Play Store / App Store exports) into a **weekly one-page pulse** with:
  - **Top themes** (3–5 max, but note uses **Top 3**)
  - **3 real user quotes** (no PII)
  - **3 concrete action ideas**
  - **Draft email** to send to yourself/alias

- **Key constraints baked into architecture**:
  - **Source**: Public Play Store / App Store data only — either **CSV/JSON exports** or **direct scrape via a Play Store library**, but no scraping behind logins or private APIs.
  - **Time window**: Last **8–12 weeks** (configurable).
  - **Review volume**: Scrape/ingest **around 400 reviews per run**, filtering for texts with **≥100 characters**.
  - **Themes**: **Max 5 themes** total; exactly **Top 3** shown in the note.
  - **Note length**: ≤ **250 words**, scannable sections.
  - **PII**: Strip usernames, emails, IDs, phone numbers, obvious names from all **stored** and **output** artifacts.
  - **LLMs**:
    - Use the **Grok (Groq) API** for Phase 2 (theme discovery + review classification).
    - Use the **Gemini API** for Phase 3 (weekly pulse / note generation).

- **Main subsystems**:
  1. **Review Import & Normalization**
  2. **PII & Content Filtering**
  3. **Theme Discovery (LLM: OpenRouter)**
  4. **Review Classification into Themes (LLM: OpenRouter)**
  5. **Weekly Note Generator (Gemini + template)**
  6. **Email Draft Generator / Send Phase**
  7. **Orchestration Layer (CLI + simple Web UI trigger)**
  8. **Storage & File Formats**
  9. **Config, Secrets, and PII Safety**

---

## 2. User Flows

### 2.1 Weekly Analyst Flow (Manual or via Web UI)

1. **Export reviews** from Google Play Console / App Store Connect as CSV (public export).
2. **Upload or drop file** into the tool:
   - CLI: pass `--reviews-file data/raw/reviews-YYYY-MM-DD.csv`
   - Web UI: upload via form.
3. **Configure run**:
   - Select **weeks window** (8–12).
   - Optional: choose **platform** (Play Store / App Store).
   - Optional: toggle **“send email”**.
4. **Run pipeline**:
   - System imports, filters, groups by themes, and generates note.
5. **Review outputs**:
   - One-page weekly pulse (Markdown + possibly PDF/Doc).
   - Email draft (subject + body).
   - Sanitized reviews JSON/CSV used, and a **theme legend**.
6. **Send email**:
   - CLI: `--send` or manual copy.
   - Web: “Send to myself” button (SMTP).

---

## 3. Data Model & File Formats

All stored artifacts must be **PII-cleaned** and **safe to share**.

### 3.1 Raw Review Source (Input Only – Not Shared)

- **Location**: `data/raw/` (not checked into repo; internal only).
- **Formats**:
  - CSV or JSON as exported by Play Store / App Store, **or**
  - JSON produced by the built-in Play Store scraper (`google-play-scraper` or similar).
- These raw files may still contain PII and **must never be committed or shared**.

### 3.2 Normalized Review Record (Internal)

After parsing and PII filtering, each review becomes:

```json
{
  "reviewId": "string",
  "rating": 1,
  "title": "string | null",
  "text": "string",
  "date": "ISO8601 datetime"
}
```

- **reviewId**:
  - Either the platform’s review ID or a **hashed/synthetic** ID to avoid exposing raw IDs.
- **Title**:
  - May be kept internally; final note usually only uses text.

### 3.3 Normalized Reviews File (Post-Import / Pre-Theming)

- **Path**: `data/normalized/reviews-YYYY-MM-DD.json`
- **Shape**:

```json
{
  "generatedAt": "ISO8601",
  "sourceFile": "data/raw/reviews-YYYY-MM-DD.csv",
  "appId": "com.nextbillion.groww",
  "platform": "play_store",
  "weeksWindow": 10,
  "reviews": [ { /* Normalized Review Record */ }, ... ]
}
```

- Only **8–12 weeks** window applied here.
- Reviews failing PII or content filters are **excluded**.

### 3.4 Theme Definition

```json
{
  "id": "theme_slug",
  "label": "Human Theme Name",
  "description": "One-line description for non-technical readers"
}
```

### 3.5 Theme Set File (Optional Debug)

- **Path**: `data/themes/themes-YYYY-MM-DD.json`
- **Shape**:

```json
{
  "generatedAt": "ISO8601",
  "sourceReviewsFile": "data/normalized/reviews-YYYY-MM-DD.json",
  "themes": [ { /* Theme */ }, ... ]
}
```

### 3.6 Grouped Reviews by Theme

- **Path**: `data/grouped/grouped_reviews-YYYY-MM-DD.json`
- **Shape**:

```json
{
  "generatedAt": "ISO8601",
  "sourceReviewsFile": "data/normalized/reviews-YYYY-MM-DD.json",
  "themes": [ { /* Theme */ }, ... ],
  "byTheme": {
    "theme_slug_1": [ { /* Normalized Review Record */ }, ... ],
    "theme_slug_2": [ ... ]
  },
  "unclassified": [ /* any reviews not assigned, optional */ ]
}
```

### 3.7 Weekly Pulse Note (Primary Artifact)

- **Paths**:
  - Markdown: `data/notes/pulse-YYYY-MM-DD.md`
  - Plain text: `data/notes/pulse-YYYY-MM-DD.txt`
  - Optional PDF/Doc: `data/notes/pulse-YYYY-MM-DD.pdf` / `.docx`

- **Content structure (Markdown)**:

```markdown
## GROWW Weekly Review Pulse — Week of {date}

### Top Themes
1. {Theme 1 label} — {one-line summary} ({N} mentions)
2. {Theme 2 label} — {one-line summary} ({N} mentions)
3. {Theme 3 label} — {one-line summary} ({N} mentions)

### Real User Quotes
- "{quote 1}" — {rating}★
- "{quote 2}" — {rating}★
- "{quote 3}" — {rating}★

### Action Ideas
1. {Action idea 1} (linked to Theme X)
2. {Action idea 2} (linked to Theme Y)
3. {Action idea 3} (linked to Theme Z)
```

- **Constraints enforced**:
  - At most **3 themes shown** (even if up to 5 exist).
  - Exactly **3 quotes**.
  - Exactly **3 action ideas**.
  - **Total text length ≤ 250 words** (enforced by word-counter logic).

### 3.8 Email Draft Artifact

- **Path**: `data/email/pulse-YYYY-MM-DD.eml` (MIME message file)  
  And/or JSON structure:

```json
{
  "generatedAt": "ISO8601",
  "subject": "GROWW Weekly Review Pulse — Week of {date}",
  "to": "alias@example.com",
  "from": "you@example.com",
  "bodyText": "Hi ...",
  "bodyHtml": "<p>Hi ...</p>..."
}
```

### 3.9 Sanitized Reviews Snapshot (Shareable Deliverable)

- **Path**: `data/share/reviews-YYYY-MM-DD-sanitized.json`
- **Shape**:
  - Subset of `normalized` reviews with **all PII removed** and possibly **truncated** texts for sharing.

---

## 4. System Components

### 4.1 Review Import & Normalization Module

- **Responsibilities**:
  - Either:
    - Accept a CSV/JSON **export file**, or
    - **Scrape reviews directly** from the Play Store using a public library (e.g. `google-play-scraper`) for the GROWW app.
  - Parse platform-specific fields into **normalized review records**.
  - Apply **time window filter (8–12 weeks)**.
  - Enforce **volume and length constraints**:
    - Target **≈400 reviews per run**.
    - Keep only reviews with **text length ≥100 characters** after basic cleaning.
  - Drop unhelpful content (e.g. trivial “Good” / “Nice app” with <100 chars).
  - Save `normalized` file in deterministic location.

- **Sub-components**:
  - **Importer / Scraper interface**:
    - `import_reviews(source_path, platform) -> List[RawReview]` (for exports).
    - `scrape_reviews(app_id, max_count=400) -> List[RawReview]` (for live Play Store scraping).
  - **Play Store scraper config**:
    - App ID: `com.nextbillion.groww`
    - Language: `en`, Country: `in`
    - Sort: newest first
    - Max count: **400** reviews per run
  - **Normaliser**:
    - Map platform-specific or scraper fields (e.g. `rating`, `content`, `at`) to internal schema.
  - **Window filter**:
    - Filter by `date >= (report_date - weeks*7 days)`.
  - **Deduplication**:
    - Use hashed combination of (`platform_review_id`, `text`, `date`) to ensure no duplicates.

### 4.2 PII & Content Filter Module

- **Responsibilities**:
  - Remove or mask:
    - Emails, phone numbers, URLs.
    - Usernames, explicit IDs, obvious real names where possible.
  - Ensure all persisted and shared data is **PII-free**.
  - Optionally:
    - Drop reviews with very low information value (e.g. `<5` words after stripping stopwords).

- **Techniques**:
  - **Regex-based detection**:
    - Emails, phones, URLs, numeric IDs.
  - **Name/handle patterns**:
    - “@username,” `user123`, etc → replace with `[User]`.
  - **Language detection (optional)**:
    - Ensure primarily English content for the LLM; drop others or mark them separately.

- **Outputs**:
  - Sanitized review text used for:
    - Theme discovery
    - Classification
    - Quotes in the note

### 4.3 Theme Discovery Module (LLM: Grok / Groq API)

- **Input**:
  - Sanitized reviews from `normalized` file.
  - Sampled subset (e.g. **100–150** reviews, stratified by rating).

- **Stratified sampling**:
  - Separate reviews into buckets by rating (1–5 stars).
  - Pick proportional sample from each bucket to ensure diversity.

- **Prompt design (conceptual)**:
  - Role: “You are a product/growth analyst for the GROWW app.”
  - Task: “Given these reviews, identify **3–5 recurring themes**.”
  - Model: a Grok model called via the Groq API.
  - Output format: **strict JSON**: array of `{id, label, description}`; no extra text.

- **Post-processing**:
  - Validate:
    - 3 ≤ number of themes ≤ 5.
    - Each theme has non-empty `id`, `label`, `description`.
  - Slugify `id` (lowercase, underscores only).
  - Optionally merge near-duplicate themes (e.g. if `app_speed` and `performance` are distinct but similar).

- **Output**:
  - In-memory list of `Theme`.
  - Optional `themes-YYYY-MM-DD.json` for inspection.

### 4.4 Review Classification Module (LLM: Grok / Groq API)

- **Input**:
  - Full sanitized review list.
  - Theme list from 4.3.

- **Process**:
  - Chunk reviews into **batches** (e.g. 50–80 reviews) to fit Groq context limits.
  - For each batch:
    - Call the Groq API (Grok model) with a prompt:  
      - Given `themes_json`, classify each review into **exactly one theme**.
      - Output strict JSON: list of `{reviewId, theme_id}`.
  - Retry logic:
    - If JSON parsing fails, re-prompt with “return only valid JSON, no commentary.”
    - If still failing, log and skip problematic batch for manual review.

- **Aggregation**:
  - Build mapping `reviewId -> theme_id`.
  - Construct `byTheme[theme_id] = [review, ...]` with full review records.
  - Any review **missing in LLM output**:
    - Option A: put into `unclassified`.
    - Option B: assign to **most common** theme (documented in README).

- **Output**:
  - `grouped_reviews-YYYY-MM-DD.json` (see 3.6).

### 4.5 Weekly Note Generator

- **Input**:
  - `grouped_reviews-YYYY-MM-DD.json`
  - Optional `report_date` (default today).

- **Steps**:
  1. **Compute metrics**:
     - For each theme: number of reviews, average rating.
     - Sort themes by count (descending).
  2. **Select Top 3 themes**:
     - Pick first 3 by count (ties broken by avg rating or recency).
  3. **Select 3 quotes**:
     - Strategy:
       - At least one quote from a lower rating (1–2 stars) if available.
       - Prefer reviews with **clear, non-PII** text.
       - Enforce PII filter again on selected quotes (second pass).
  4. **Generate action ideas**:
     - Option A: LLM-suggested:
       - Call the Gemini model with top themes + example reviews → get 3 action ideas, each tagged with theme.
       - Enforce constraints: must be concrete, not vague.
     - Option B: Part rule-based (short term) + LLM (opt-in).
  5. **Assemble Markdown**:
     - Use fixed headings and bullet structure (see 3.7).
     - Run **word counter**, trim or compress content to ≤ 250 words (e.g. shorter descriptions).
  6. **Generate plain text**:
     - Strip Markdown formatting or render to plain.

- **Output**:
  - `pulse-YYYY-MM-DD.md`
  - `pulse-YYYY-MM-DD.txt`
  - Optional: use markdown-to-PDF/Doc for additional deliverables.

### 4.6 Email Draft / Send Phase

This is a **distinct phase** in the architecture (Phase 4) dedicated to taking the weekly pulse note and producing/sending an email.

- **Input**:
  - Markdown note (`pulse-*.md`).
  - Configured `FROM`, `TO`, optional recipient name.

- **Process**:
  - Convert Markdown to HTML (via markdown library).
  - Prepend greeting (`Hi {name},`) if name is provided.
  - Wrap note into simple HTML template with headings.
  - Form MIME message with text + HTML alternatives.

- **Modes**:
  - **Dry-run (default)**:
    - Save `.eml` + JSON summary in `data/email/`.
  - **Send mode**:
    - Use SMTP (host, port, TLS, auth) to send.
    - Never log passwords.
    - Log success/failure to console and log file.

- **Output**:
  - `.eml` file.
  - Optional: log line showing subject and recipient.

---

## 5. LLM Integration (Grok + Gemini)

### 5.1 LLM Client Abstraction

- **Interface**:
  - `generate_themes(reviews_sample) -> List[Theme]`
  - `classify_reviews(themes, reviews_batch) -> List[Classification]`
  - `suggest_actions(themes, grouped_reviews) -> List[ActionIdea]`
  - Optional: `draft_note(...)` if using LLM to write full note.

- **Configuration**:
  - API key from env.
  - Model name for Grok (abstracted so we can swap versions).
  - Timeouts and retries.

### 5.2 Safety & PII with LLM

- Always send **sanitized texts** to Grok (no raw usernames/IDs/emails).
- Instructions in prompts:
  - “Do not generate or infer any names, emails, or IDs.”
  - “When referring to users, say ‘users’ or ‘[User]’.”
- Post-process LLM outputs through PII filter again (names, emails, etc.).

---

## 6. PII & Compliance Safeguards

- **At ingest**:
  - Raw exports stored only under `data/raw/` (gitignored).
  - Normalized/sanitized versions saved in `data/normalized/`.
- **Throughout pipeline**:
  - Use **synthetic IDs** in normalized records and outputs.
  - Run PII filter:
    - Before saving normalized reviews.
    - Before sending text to LLM.
    - Before saving quotes and final note.
- **Artifacts**:
  - All artifacts under `data/share/`, `data/notes/`, `data/email/` are **safe to share**.
  - README clearly states: do **not** commit `data/raw/` or any file with raw exports.

---

## 7. Interfaces: CLI & Web UI

### 7.1 CLI

- **Entry command**: `python -m groww_pulse.main` or `groww-pulse` (if packaged).
- **Key options**:
  - `--phase {import|analyze|classify|note|email|all}`
  - `--reviews-file PATH` (for `import` or `all`)
  - `--platform {play_store, app_store}`
  - `--weeks N` (8–12)
  - `--send` (email send vs. dry-run)
  - `--recipient EMAIL`
  - `--recipient-name NAME`
  - `--date YYYY-MM-DD` (report date; default: today)

- **Typical weekly command**:

```bash
python -m groww_pulse.main \
  --phase all \
  --reviews-file data/raw/reviews-2026-03-09.csv \
  --platform play_store \
  --weeks 10 \
  --send \
  --recipient your.alias@example.com
```

### 7.2 Web UI (Prototype-Friendly)

- **Stack**:
  - Simple backend (e.g. FastAPI/Flask) with:
    - `POST /api/run` to trigger pipeline.
    - `GET /api/latest-note` to fetch `pulse-*.md`/HTML.
  - Frontend:
    - Minimal page with:
      - File upload (CSV).
      - Dropdown for weeks (8–12).
      - Checkbox “Send email when done”.
      - Button “Run weekly pulse”.

- **Flow**:
  - User uploads export, configures options, clicks run.
  - Backend:
    - Stores file into `data/raw/`.
    - Runs phases sequentially.
  - UI polls for status and, when done:
    - Shows rendered weekly note.
    - Provides download links:
      - Note (MD or PDF)
      - Email draft (.eml or JSON view)
      - Sanitized reviews JSON
    - Shows a “Sent to: …” confirmation if email was sent.

- This UI (deployed somewhere like Render/Heroku/railway) can be the **“working prototype link”**.

---

### 7.3 Weekly Scheduler

A **scheduler** runs the full weekly pulse pipeline **once per week at a fixed time** (default **Monday 11pm** local time) and **sends the email** to a fixed recipient.

- **Entry point**: `python run_scheduler.py` (from project root).
- **Behaviour**:
  - Computes the next run time as the next occurrence of the configured weekday at the configured hour (e.g. Monday 23:00).
  - Sleeps until that time, then invokes the **CLI** via subprocess:
    - `python -m groww_pulse.main --phase all --weeks N --max-reviews M --recipient <recipient> --send`
  - After the run completes, computes the next weekly run and repeats.
- **Recipient**: Fixed to **anshbhalla421@gmail.com** by default. Override with env `GROWW_SCHEDULER_RECIPIENT`.
- **Configuration** (env or `.env`):
  - `GROWW_SCHEDULER_RECIPIENT` — email to send the weekly pulse to (default: `anshbhalla421@gmail.com`).
  - `GROWW_SCHEDULER_WEEKS` — review window in weeks (default: 8).
  - `GROWW_SCHEDULER_MAX_REVIEWS` — max reviews for scrape (default: 400).
  - `GROWW_SCHEDULER_DAY` — weekday for run, 0=Monday … 6=Sunday (default: 0).
  - `GROWW_SCHEDULER_HOUR` — hour in 24h format (default: 23 for 11pm).
  - `GROWW_SCHEDULER_MINUTE` — minute (default: 0).
- **Logging**: Logs to `data/logs/scheduler.log` and stdout (startup, next run time, CLI invocation, success/failure).

---

## 8. Logging & Observability

- **Logging**:
  - Per-phase start/end logs.
  - Key metrics:
    - Number of reviews imported, filtered out, kept.
    - Number of themes, distribution of reviews per theme.
    - Whether email send succeeded.
  - Warning logs for:
    - LLM failures, JSON parse errors, unclassified reviews ratio.

- **Files**:
  - `data/logs/pipeline-YYYY-MM-DD.log`

---

## 9. README & Deliverables Mapping

### 9.1 README Content (High-Level)

- **Sections**:
  - **Overview**: what the tool does, who it’s for.
  - **Prerequisites**:
    - Python version, virtualenv, API keys (Grok + SMTP).
  - **Setup**:
    - Install dependencies.
    - Configure `.env` (GROK_API_KEY, EMAIL_SENDER, etc.).
  - **How to run for a new week**:
    1. Export reviews CSV from Play Store/App Store.
    2. Place under `data/raw/`.
    3. Run CLI or use Web UI.
    4. Find outputs in `data/notes/`, `data/email/`, `data/share/`.
  - **Theme legend**:
    - Show example theme IDs and labels.
    - Explain how to interpret them (e.g. “app_performance: app speed, crashes, lag”).
  - **Directory structure**:
    - `data/raw/`, `data/normalized/`, `data/grouped/`, `data/notes/`, `data/email/`, `data/share/`, `data/logs/`.
  - **PII policy**:
    - Raw exports not committed.
    - Sanitized outputs only in deliverables.

### 9.2 Deliverables Output Paths

- **Working prototype**:
  - URL to Web UI (or notebook-based demo).
- **Latest weekly note**:
  - `data/notes/pulse-YYYY-MM-DD.md` (and PDF/Doc if generated).
- **Email draft**:
  - `data/email/pulse-YYYY-MM-DD.eml` (and possibly JSON).
- **Reviews CSV/JSON used**:
  - `data/share/reviews-YYYY-MM-DD-sanitized.json` (or CSV).
- **Theme legend**:
  - In README, optionally also as `data/themes/theme_legend-YYYY-MM-DD.json`.

