# Architecture

How this is put together, why it is put together that way, and what will
break if you change it without knowing. Written for the next person, which
may be you in six months.

## The one rule everything else follows

**Nothing reaches a form that a human did not confirm.**

DD Form 2807-1 is a sworn statement. It carries a federal false-statement
warning — up to five years' confinement or a $10,000 fine — and the person
signing it is the veteran, not this tool. Every design decision below is
downstream of that.

The rule is enforced in one place, `fill_forms.assert_all_confirmed()`, and
`fill_forms.py` is the only module in the repository permitted to write to a
PDF. If you find yourself adding a second one, stop.

There is exactly one exception, and it is not really an exception: answers
the member typed themselves on the questionnaire go straight through. They
are the source. Asking them to re-approve their own address one screen later
is friction that teaches people to click past confirmation screens, which is
the opposite of what the rule is for.

## Two things the tool is careful never to do

**It does not diagnose.** `self_report.py` phrases everything as a symptom in
the member's own words. The catalogue says "ringing, buzzing or hissing in my
ears", never "tinnitus", because the member is reporting an experience and
the diagnosis belongs to a clinician.

**It does not decide that things are connected.** `secondary.py` and
`presumptives.py` both report overlaps and hand them to a VSO. Neither has
vocabulary for asserting a link, and tests enforce that: every rule must end
in a question mark, no rule may say "is caused by" or "you qualify", and
neither module may reference `fill_forms`, `target_field` or `Proposal`.

These are not stylistic preferences. A nexus opinion is medical practice and
an eligibility determination is VA's. Crossing either line turns a useful
tool into an unaccredited claims consultant, which is a different thing with
different law attached.

## Data flow

```
  questionnaire ──────────────────┐
  (intake.py)                     │
                                  ▼
  record PDFs ──► pdf_io ──► extract_conditions ──► conditions
                     │        coded_records            │
                     └──► ocr (scans only)             │
                                                       ▼
  self-report ─────────────────────────────► field_map ──► proposals
  (self_report.py)                                            │
                                                              ▼
                                                    ┌── REVIEW GATE ──┐
                                                    │  human confirms │
                                                    └────────┬────────┘
                                                             ▼
                                     explanations ──► fill_forms ──► PDFs
                                                             │
                    timing ─┐                                ▼
                 secondary ─┼──────────────────────► package_bundle ──► zip
              presumptives ─┘                        buddy_letter
```

Everything left of the gate produces *proposals*. Everything right of it
produces documents. `timing`, `secondary` and `presumptives` bypass the gate
entirely because they never touch a form — they only write prose into the
worksheet and README.

## The modules, by what they own

| Module | Owns |
|---|---|
| `pdf_io.py` | Getting text and page offsets out of a PDF |
| `extract_conditions.py` | MHS Genesis structure: diagnoses, problem lists, providers |
| `coded_records.py` | Generic ICD-10 lines from CCD-A and claims formats |
| `ocr.py`, `ocr_backends.py` | Scans. Per-platform backends, never presented as high confidence |
| `condition_library.py` | ICD-10 → form question. 76 range rules. **Rots every October** |
| `field_map.py` | Condition → AcroForm field, plus record-level rules |
| `proposals.py` | Building the reviewable proposal list |
| `schema.py` | `Proposal`, the confidence tiers, and their ordering |
| `self_report.py` | What is *not* in the records, and the treatment-question guard |
| `intake.py` | The questionnaire, and `BLANK_BY_DESIGN` |
| `explanations.py` | Item 29 and SHA explanation drafts |
| `timing.py` | BDD and effective-date windows |
| `secondary.py` | Secondary-connection questions |
| `presumptives.py` | Exposure → presumptive category. **Changes by statute** |
| `fill_forms.py` | The only writer of PDFs. The confirm gate lives here |
| `package_bundle.py` | The zip, the README, the worksheet |
| `buddy_letter.py` | Lay-statement templates |

## Two front ends, one pipeline

There are two ways to run this and they are not equivalent:

**`docs/app/`** — the browser build. Python runs in Pyodide via WebAssembly.
Records never leave the tab; there is no server to send them to. This is what
people actually use. It cannot OCR, because the OCR backends are native.

**`app/`** — a local Flask server on `127.0.0.1`. Full OCR. Used for
development and for scanned records.

`web/py/web_pipeline.py` is the browser's replacement for `ingest.py` and
`pdf_io.py`. Everything else is shared, and shared by *copying*:
`tools/build_web.py` copies the modules into `docs/app/py/` and writes
`MANIFEST.txt`.

**Copying is the sharp edge in this design.** Three separate failures came
from it, and there is now a test for each:

- Editing a module and not rebuilding → `test_shipped_copies_match_the_source`
- A syntax error in a browser-only module, invisible to a suite that never
  imports it → `test_every_shipped_module_compiles`
- A returning visitor running cached older modules against a newer page →
  `PY_BUILD`, a content hash stamped into the page and hung on every fetch

If you edit anything in the table above, run:

```bash
python tools/build_web.py && python tools/stamp_assets.py
```

CI fails if you forget.

## Generated, do not hand-edit

- `docs/app/py/*` — copied from the repo root
- `docs/app/py/MANIFEST.txt` — the module list
- The `QUESTIONS` array in `docs/app/index.html` — generated from
  `intake.QUESTIONS`, between the `GENERATED QUESTIONS` markers. It used to be
  a hand-kept duplicate, which is how a question got added everywhere except
  the page people use
- `PY_BUILD` and `PRESUMPTIVE_REVIEWED` in the same file
- `?v=` hashes on the stylesheet links
- `forms/FORM_VERSIONS.txt` — `tools/pin_forms.py`

## What rots, and when

| Thing | Cadence | Guard |
|---|---|---|
| ICD-10-CM | Every 1 October | `condition_library.REVIEWED` + `test_freshness` |
| Presumptive lists | By statute, unpredictably | `presumptives.REVIEWED`, shown to users |
| The two forms | New editions rename fields | `forms/FORM_VERSIONS.txt` |
| Government URLs | Constantly | `tools/check_links.py`, monthly in CI |

The freshness tests fail on a schedule, by design. A CI job that goes red
every October is the cheapest reminder to re-check a list people are making
decisions from. The alternative is finding out from a veteran.

## PHI, and why the tests are paranoid

This repository is public. The tool's working files land in the same
directory as its source. PHI reached debug output twice during development
and a real clinician's name reached three commit messages, which needed a
history rewrite.

`tests/test_repo_hygiene.py` scans every committed file for SSNs, DoD IDs and
clinician-name patterns, verifies the shipped forms are blank, verifies no
PDF outside `forms/` except the synthetic sample, and reads that sample's
text so a real record committed in its place would be caught.

Two rules when working here:

1. Never print an extracted value while debugging. Print its shape — length,
   type, whether it matched. Masked output only.
2. Never paste record text into a commit message, an issue, or a test
   fixture. `tools/make_sample_record.py` generates synthetic records with
   real ICD-10 codes and invented names; use that.

## `hosted/`

An architecture prototype for a server-side version, deliberately
unfinished. Every control in `hosted/security.py` raises
`NotImplementedError`, every endpoint returns 501 while any control is a
stub, and startup refuses a non-loopback bind. It exists to make the trust
boundary concrete — what crosses the network, where it lands, how long it
lives — not to be deployed. `hosted/SECURITY_REQUIREMENTS.md` is the
contract a real deployment would owe.

It is fail-closed. Do not "temporarily" implement a stub to get it running.

## Testing

```bash
python -m pytest tests/ -q
```

The suite splits roughly into:

- **Extraction** — golden-output regression against synthetic records
- **Contract** — the pipeline's shape, so a signature change fails at test
  time rather than in a browser
- **Guards** — the confirm gate, the treatment-question filter, the
  no-assertion rules in `secondary` and `presumptives`
- **Hygiene and freshness** — the two above
- **Shipped build** — the browser bundle compiles and matches source

What is *not* covered: there is no end-to-end browser test. The flow has
been walked by hand many times, and several bugs found that way (a boot
race, a decision counter that over-reported, a stale-module cache). A
Playwright pass through upload → review → package is the highest-value test
this project does not have.
