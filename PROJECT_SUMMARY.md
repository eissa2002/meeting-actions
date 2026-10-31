# Meeting Actions: Project Summary

A plain-language walkthrough of what we built and how we got here.

## What the service does

You send it the text of your meeting notes. It sends the notes to an AI model, which picks out
the **action items**: who has to do what, and by when. You get back a clean list.

- If the notes say who or when, you get it **exactly as written** (for example, "Friday").
- If they don't say, that field is left empty (`null`). The service never guesses.
- If there's nothing to do, you get an **empty list**, not an error.
- If you send nothing, or more than 20,000 characters, you get a **clear error message**.
- Your notes are **never saved and never written to the logs**.

## The steps we followed

We used **Spec Kit**, a step-by-step method: agree on the rules, describe what to build, plan
it, split it into tasks, check everything, then write the code.

### 1. Set the ground rules (the constitution)

Five rules every part of the project must follow:

1. Every feature has automatic tests (pytest).
2. All code says what kind of data it uses (type hints).
3. Everything the AI sends back is checked against a fixed shape before we use it.
4. No passwords or API keys in the code, ever.
5. Keep it simple.

### 2. Describe what to build (the spec)

We wrote down what the service must do, in everyday terms: three user stories, 12
requirements, and 5 measurable targets. For example, the AI should find at least 90% of real
action items and invent at most 5% fake ones.

### 3. Settle open questions

One question came up: should due dates be converted to real calendar dates? We decided **no**:
keep them exactly as written, because "next Friday" can't be turned into a date without
knowing when the meeting happened.

### 4. Make the technical plan

- **Language and framework:** Python 3.12 with FastAPI.
- **AI connection:** at first the plan used Anthropic's Claude directly. You then asked for
  something more flexible, so we switched to the common "OpenAI-compatible" style. Now **any
  provider** that speaks this style works, and you switch providers by changing three settings
  in the `.env` file, with no code changes:
  - `LLM_BASE_URL`: the provider's web address
  - `LLM_API_KEY`: your secret key (kept only in `.env`, never in the code)
  - `LLM_MODEL`: which model to use
- **Packaging:** a Dockerfile, so it can run in a container.

### 5. Split the work into tasks

The plan became 31 small tasks, grouped by user story, with tests written before the code
each time.

### 6. Check everything before coding

An automatic review compared the spec, plan, and tasks. It found a few things, which we fixed:

- Two development tools weren't explained in the plan (rule 5 requires that). We added the
  explanation.
- Nothing measured the AI's accuracy. We added a set of **15 made-up sample meetings** and a
  script that scores the AI against them.
- The timeout was long (up to about 90 seconds on failure). We cut it to **15 seconds with 1
  retry**.
- Later we noticed one development tool (`httpx`) wasn't needed after all, and removed it.

### 7. Build it

We built it in two rounds:

- **Round 1:** project setup, the core data shapes and settings, and the main feature:
  getting action items out of notes.
- **Round 2:** the empty-list behavior, the clear error messages, the Dockerfile, the README,
  and the accuracy-check script.

Then one small fix: **every request now writes one line to the log**, including errors. The
log line holds only the result, the length of the notes, and the time taken; never the notes
themselves.

**Result:** 49 automatic tests, all passing. The type checker reports no problems. A scan
found no secrets in the code.

### 8. Try it with a real AI provider

We tried three providers. This is where switching providers with no code changes paid off:
each switch was just a change to the settings file.

| Provider | What happened |
|----------|---------------|
| 1st | Worked, but took **25 seconds** per answer. Our service gives up after 15, so every request timed out. |
| 2nd | Refused every request: the account needed a $1 card verification first. |
| 3rd | **Worked.** Answers in about 1 second. It only allows a few requests close together, so the accuracy check waits 5 seconds between samples. |

With the third provider, all six example requests behaved correctly:

| Example | Result |
|---------|--------|
| "Alice will send the budget report by Friday." | Alice, budget report, Friday ✅ |
| "Bob to book the venue." | Bob, book the venue, no due date ✅ |
| Notes with no tasks | Empty list ✅ |
| Empty notes | Correct error ✅ |
| Notes over 20,000 characters | Correct error ✅ |
| Badly formed request | Correct error ✅ |

**Accuracy check** (15 made-up sample meetings):

| What we measured | Target | Result |
|------------------|--------|--------|
| Real action items found | at least 90% | **100%** ✅ |
| Made-up items returned | at most 5% | **0%** ✅ |
| "Nothing to do" meetings returning an empty list | all of them | **3 of 3** ✅ |
| Response time (95% of requests) | under 10 s | **3.6 s** ✅ |

**Privacy check:** the server log shows only results, lengths, and times. None of the notes
text appears in it. ✅

## Where things stand

- **Done:** everything except one step.
- **Still to do:** build the Docker image. Docker Desktop wasn't running, so this hasn't been
  tried yet.
- **Watch out:** the working settings are in a file named `.env.txt`, not `.env`. Rename it to
  `.env` (replacing the old one) so the service picks them up normally. Make sure no copies of
  your key are left in other files.

## How to use it

```powershell
# One-time setup
uv venv --python 3.12 .venv
uv pip install --python .venv -e ".[dev]"

# Run the automatic tests (no AI or key needed)
.venv\Scripts\python -m pytest

# Start the service (reads your .env first)
Get-Content .env | ForEach-Object { if ($_ -match '^(\w+)=(.*)$') { Set-Item "env:$($matches[1])" $matches[2] } }
.venv\Scripts\uvicorn --factory meeting_actions.main:create_app --port 8000

# Try it (in a second terminal)
Invoke-RestMethod -Method Post -Uri http://localhost:8000/v1/action-items -ContentType 'application/json' -Body '{"notes": "Alice will send the budget report by Friday."}'

# Check AI accuracy (calls the real AI 15 times, costs a little)
# --delay 5 waits 5 seconds between samples, for providers with rate limits
.venv\Scripts\python eval/run_eval.py --delay 5
```

## Where things are

| Path | What it is |
|------|------------|
| `src/meeting_actions/` | The service code (4 small files) |
| `tests/` | The automatic tests (use a fake AI, so they're free and fast) |
| `eval/` | The 15 sample meetings and the accuracy-check script |
| `specs/001-meeting-action-items/` | The spec, plan, tasks, and design notes |
| `.specify/memory/constitution.md` | The five ground rules |
| `.env` | Your real settings and key (never shared or committed) |
| `.env.example` | A template for `.env` with fake values |
| `Dockerfile` | Instructions to package the service as a container |
| `README.md` | The short technical guide |
