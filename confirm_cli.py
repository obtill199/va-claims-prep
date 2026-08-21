#!/usr/bin/env python3
"""
confirm_cli.py — the terminal review-and-confirm gate.

This is the ONLY place a Proposal's status can move off "pending"
(BUILD_BRIEF.md section 4, decision 1: review-and-confirm, never auto-fill).
fill_forms.py only ever reads what this writes.

Usage:
    python confirm_cli.py proposals.json -o confirmed.json
"""

import argparse

from schema import proposals_from_json, proposals_to_json, confirmed_only

PROMPT = "  [y] confirm  [n] reject  [e] edit  [q] save and quit > "


def review(proposals):
    total = len(proposals)
    for i, p in enumerate(proposals, 1):
        if p.status != "pending":
            continue  # resuming a partially-reviewed session

        print(f"\n--- {i}/{total} " + "-" * 40)
        print(f"  Form:       {p.target_form}")
        print(f"  Field:      {p.target_field}")
        print(f"  Proposed:   {p.proposed_value}")
        print(f"  Confidence: {p.confidence}  ({p.extraction_method})")
        print(f"  Source:     {p.source_document}"
              + (f", page {p.source_page}" if p.source_page else ""))
        print(f"  Why:        {p.rationale}")

        while True:
            choice = input(PROMPT).strip().lower()
            if choice == "y":
                p.status = "confirmed"
                p.confirmed_value = p.proposed_value
                break
            elif choice == "n":
                p.status = "rejected"
                break
            elif choice == "e":
                new_value = input(f"  New value (was {p.proposed_value!r}): ").strip()
                if new_value:
                    p.status = "edited"
                    p.confirmed_value = new_value
                    break
                print("  (empty — try again)")
            elif choice == "q":
                return proposals
            else:
                print("  y/n/e/q only")
    return proposals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("proposals_json")
    ap.add_argument("-o", "--output", default="confirmed.json")
    args = ap.parse_args()

    proposals = proposals_from_json(args.proposals_json)
    reviewed = review(proposals)

    # Save full review state (so a `-q` quit can resume later)...
    proposals_to_json(reviewed, args.proposals_json)
    # ...but the output file — what fill_forms.py is allowed to read — only
    # ever holds actually-confirmed values.
    proposals_to_json(confirmed_only(reviewed), args.output)

    n_confirmed = sum(1 for p in reviewed if p.status in ("confirmed", "edited"))
    n_rejected = sum(1 for p in reviewed if p.status == "rejected")
    n_pending = sum(1 for p in reviewed if p.status == "pending")
    print(f"\n{n_confirmed} confirmed, {n_rejected} rejected, "
          f"{n_pending} still pending -> {args.output}")


if __name__ == "__main__":
    main()
