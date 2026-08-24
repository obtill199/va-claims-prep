#!/usr/bin/env python3
"""
schema.py — the reviewable intermediate format.

Every proposed form answer is a Proposal: a value plus its source citation
and confidence, never a confirmed fact. Nothing downstream may write to a
PDF from anything but a list of Proposals with status == "confirmed".
See BUILD_BRIEF.md section 4, decision 1.
"""

import json
from dataclasses import asdict, dataclass, field
from typing import Optional

VALID_FORMS = ("DD2807-1", "SHA_PART_A")
# "self-reported" is not a weaker reading of a record -- it is a different
# kind of claim entirely: the member said it, and no document backs it.
# It gets its own tier so the review screen, the worksheet and the VSO can
# all tell the two apart at a glance, rather than a self-report borrowing
# the badge of something with a page number behind it.
VALID_CONFIDENCE = ("high", "medium", "low", "self-reported")

# Sort order for review. Defined here, next to the tiers themselves, because
# three separate modules were each keeping their own copy of it -- and adding
# a fourth tier broke two of them with a KeyError at runtime rather than at
# import. A self-report sorts with the strong tier: it is not a weak reading
# of a record, it is a statement from the person who would know.
CONFIDENCE_ORDER = {"high": 0, "self-reported": 0, "medium": 1, "low": 2}


def confidence_rank(confidence):
    """Never raise on an unknown tier -- sort it last instead."""
    return CONFIDENCE_ORDER.get(confidence, len(CONFIDENCE_ORDER))
VALID_METHOD = ("structured", "ocr")
VALID_STATUS = ("pending", "confirmed", "edited", "rejected")


@dataclass
class Proposal:
    id: str                        # stable hash of (condition_ref, target_form, target_field)
    condition_ref: str             # icd10 code, or condition name if uncoded
    target_form: str               # "DD2807-1" | "SHA_PART_A"
    target_field: str              # exact AcroForm field name (leaf, e.g. "Yes12C")
    question_text: str             # the question as printed on the form
    proposed_value: str            # "Yes" | "No" | free text
    source_document: str           # filename the value was extracted from
    source_page: Optional[int]     # 1-indexed page in source_document; None if not page-addressable
    confidence: str                # "high" | "medium" | "low"
    extraction_method: str         # "structured" | "ocr"
    rationale: str                 # plain-English "why", shown to the member.
                                   # No internal identifiers, no filenames —
                                   # the source file has its own field below
                                   # and renders at the foot of the card.
    status: str = "pending"        # "pending" | "confirmed" | "edited" | "rejected"
    confirmed_value: Optional[str] = None

    def __post_init__(self):
        if self.target_form not in VALID_FORMS:
            raise ValueError(f"target_form must be one of {VALID_FORMS}, got {self.target_form!r}")
        if self.confidence not in VALID_CONFIDENCE:
            raise ValueError(f"confidence must be one of {VALID_CONFIDENCE}, got {self.confidence!r}")
        if self.extraction_method not in VALID_METHOD:
            raise ValueError(f"extraction_method must be one of {VALID_METHOD}, got {self.extraction_method!r}")
        if self.status not in VALID_STATUS:
            raise ValueError(f"status must be one of {VALID_STATUS}, got {self.status!r}")


def proposals_to_json(proposals, path):
    with open(path, "w") as fh:
        json.dump([asdict(p) for p in proposals], fh, indent=2)


def proposals_from_json(path):
    with open(path) as fh:
        rows = json.load(fh)
    return [Proposal(**row) for row in rows]


def confirmed_only(proposals):
    """The only view fill_forms.py is allowed to consume. "edited" counts as
    confirmed too — the member corrected the value and approved that
    correction, which is still an explicit confirm, just not of the value
    extract_conditions.py originally proposed."""
    return [p for p in proposals if p.status in ("confirmed", "edited")]
