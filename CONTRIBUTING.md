# Contributing

Bug reports, corrections and pull requests are welcome — particularly on the
parts that decay: the ICD-10 range rules, the presumptive lists, the form
field mappings, and the links.

## Before you send code

By opening a pull request you agree that your contribution is licensed to
the project owner under the same terms as the project ([PolyForm
Noncommercial 1.0.0](LICENSE)), **and** that you grant the owner permission
to license your contribution commercially as part of the project.

That second half is what makes it possible to offer a commercial licence at
all. Without it, every contributor would hold a veto over the project's
own licensing. It is the same arrangement most dual-licensed projects use.

If you are not willing to grant that, please open an issue describing the
fix instead of sending a patch — a clear bug report is genuinely just as
useful, and often more so.

## What makes a good change here

**Never paste record text into an issue, a commit message, or a test
fixture.** This project is built around other people's medical records and
PHI has nearly reached a commit twice. `tools/make_sample_record.py`
generates synthetic records with real ICD-10 codes and invented names — use
that. `tests/test_repo_hygiene.py` will fail the build if a real-looking
name or identifier gets committed.

**Never print an extracted value while debugging.** Print its shape: length,
type, whether it matched. Masked output only.

**Run the checks.** `python -m pytest -q` for the fast suite. If you touched
anything in `docs/form/`, also run `python tools/build_web.py && python
tools/stamp_assets.py` and commit the result — CI fails if the published
build is stale.

**Read [ARCHITECTURE.md](ARCHITECTURE.md) first** if you are changing
anything about how proposals reach a form. There is one rule that everything
else follows, and it is not negotiable: nothing reaches a form that a human
did not confirm.

## What will be turned down

Anything that makes the tool assert a medical or legal conclusion. It does
not diagnose, it does not decide that two conditions are related, and it
does not determine eligibility. Those lines are enforced by tests, and they
are the difference between a useful tool and an unaccredited claims
consultant.
