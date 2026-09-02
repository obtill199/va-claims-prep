# Working in this repository

A tool that reads a veteran's own medical records and prepares their VA
disability paperwork. It runs entirely in the browser; records never leave
the user's machine.

Read `ARCHITECTURE.md` before changing anything about how proposals reach a
form. What follows is the short list of things that have actually gone
wrong here, and the habits that prevent them recurring.

## The rule everything else serves

**Nothing reaches a form that a human did not confirm.** DD Form 2807-1 is
a sworn statement carrying a federal false-statement penalty. One module —
`fill_forms.py` — may write to a PDF, and it refuses to run on anything
unconfirmed. Do not add a second writer.

Three lines the tool does not cross, each enforced by tests rather than by
policy: it does not diagnose, it does not decide two conditions are
related, and it does not determine eligibility. Advisory modules
(`secondary.py`, `presumptives.py`, `rating_criteria.py`, `increase.py`)
emit questions, never conclusions, and may not import the form layer.

## PHI

- **Never print an extracted value while debugging.** Print its shape:
  length, type, whether it matched. This has leaked twice.
- **Never paste record text** into a commit message, an issue, or a
  fixture. `tools/make_sample_record.py` and `tools/make_cfile.py` generate
  synthetic records with real ICD-10 codes and invented names.
- `tests/test_repo_hygiene.py` fails the build if an identifier or a
  real-looking clinician name is committed.

## Before you push

```bash
python tools/build_web.py && python tools/stamp_assets.py
ruff check .
python -m pytest -q
```

`docs/form/py/` is **generated**. Editing it directly is silently reverted
by the next build; a test catches this, but only after you have wasted the
time.

## The failure mode that keeps recurring

Every bug that has shipped here was a verification gap, not a knowledge
gap. Specifically:

**A rename on one side of the JS/Python boundary.** The page drives Python
by name inside template literals. `self_report.summarise` was renamed to
`summarize` in the HTML and not in the module; step 3 rendered empty in
production for a week and all 365 tests passed, because nothing else called
it. There is now a test that resolves every `module.function()` call in the
page against the shipped modules — but **if you touch anything the page
calls, drive the browser as well.** Tests will not catch a rendering
failure.

**A blanket edit crossing a boundary it was not scoped to.** The spelling
pass above targeted `docs/` and `*.md`, so it rewrote a call site and left
the callee. Scope blanket edits by behaviour, not by file glob, and check
what fell outside the glob.

**`.gitignore` swallowing a needed file.** `*.txt` is ignored to keep
record artifacts out. It has silently dropped `requirements.txt` and
`forms/FORM_VERSIONS.txt`; `git add -A` reports nothing when a file is
ignored. Exceptions are explicit and a test asserts required files are
tracked.

**Writing into the current working directory.** `build_review()` once wrote
its scratch file to the CWD and destroyed a gitignored golden fixture. Use
a temp file. Nothing here should be able to reach a file somebody else
owns.

**`open()` without an encoding.** Fine on macOS and Linux, cp1252 on
Windows, and the files this tool writes carry condition names and free text
a member typed. A test enforces `encoding=` everywhere.

## What rots on a calendar

ICD-10 revises every October. Presumptive lists change by statute. Rating
criteria change by rulemaking. The forms get new editions that rename the
AcroForm fields written to. Each carries a `REVIEWED` stamp or a pinned
hash, and `tests/test_freshness.py` goes red when one is a year stale. That
is intended: a CI failure is cheaper than a veteran finding out.

## Linting

`ruff` is configured in `pyproject.toml`, including bandit security rules.
The selection is deliberate and each disabled rule says why. Every `noqa`
in the codebase carries a written reason. Keep it that way — a suppression
without a reason is indistinguishable from a bug.

## Style

Match the surrounding code. Comments explain *why*, not *what*, and the
reasoning behind a non-obvious decision is worth more than brevity. Several
modules document the bug that produced their design; keep that when editing
them.
