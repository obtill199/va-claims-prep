#!/usr/bin/env python3
# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
tools/readability.py — how hard is this to read, per screen.

The audience is not a general one. It includes people with traumatic brain
injury, people reading on a phone in a parking lot, people who are tired
and stressed and doing this because they have to. Plain-language guidance
for federal health material lands around 6th-8th grade; VA.gov targets the
same. Anything written at college level is a barrier dressed as
thoroughness.

This measures rather than guesses: Flesch-Kincaid grade per screen, the
sentences long enough to lose someone, and words that mean something
specific to this project and nothing to a member.

    python tools/readability.py
"""

import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TARGET_GRADE = 9.0     # above this, rewrite
LONG_SENTENCE = 25     # words

# Words that are precise internally and opaque to somebody filing a claim.
JARGON = {
    "proposal": "answer we found",
    "proposals": "answers we found",
    "extraction": "reading your records",
    "extracted": "found",
    "ICD-10": "diagnosis code",
    "AcroForm": "form field",
    "tier": "group",
    "parser": "reader",
    "crosswalk": "matching list",
    "confidence": "how sure we are",
    "presumptive": "(needs a plain-English gloss nearby)",
    "secondary service connection": "(needs a plain-English gloss nearby)",
    "aggregate": "combine",
    "instantiate": "start",
    "populate": "fill in",
    "utilize": "use",
    "commence": "start",
    "remediate": "fix",
    "leverage": "use",
    "facilitate": "help",
}


def syllables(word):
    word = word.lower().strip(".,;:!?()[]\"'—-")
    if not word:
        return 0
    groups = re.findall(r"[aeiouy]+", word)
    n = len(groups)
    if word.endswith("e") and n > 1 and not word.endswith(("le", "ee", "ye")):
        n -= 1
    return max(1, n)


def sentences_of(text):
    parts = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
    return [p.strip() for p in parts if len(p.split()) >= 3]


def grade(text):
    sents = sentences_of(text)
    words = [w for w in re.findall(r"[A-Za-z'’-]+", text)]
    if not sents or not words:
        return None, 0, 0
    syl = sum(syllables(w) for w in words)
    fk = (0.39 * (len(words) / len(sents))
          + 11.8 * (syl / len(words)) - 15.59)
    return round(fk, 1), len(words), len(sents)


def visible_text(html):
    """What a reader actually sees: no script, no style, no attributes."""
    html = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    html = re.sub(r"<[^>]+>", " ", html)
    html = (html.replace("&mdash;", "—").replace("&rsquo;", "'")
                .replace("&ldquo;", '"').replace("&rdquo;", '"')
                .replace("&amp;", "&").replace("&middot;", "·")
                .replace("&hellip;", "…").replace("&rarr;", "→"))
    return re.sub(r"\s+", " ", html).strip()


def screens():
    """Each step of the tool is its own screen; measure them separately,
    because an average across the whole page hides the one that is hard."""
    out = []
    for label, rel in (("disclaimer", "docs/disclaimer/index.html"),
                       ("home", "docs/home/index.html")):
        with open(os.path.join(REPO, rel), encoding="utf-8") as fh:
            out.append((label, visible_text(fh.read())))

    with open(os.path.join(REPO, "docs/form/index.html"), encoding="utf-8") as fh:
        page = fh.read()
    titles = {1: "1 About you", 2: "2 Your records", 3: "3 What's missing",
              4: "4 Review", 5: "5 Explanations", 6: "6 Package"}
    for n, title in titles.items():
        m = re.search(rf'<section id="step-{n}".*?</section>', page, re.S)
        if m:
            out.append((title, visible_text(m.group(0))))
    return out


def main():
    print("=" * 74)
    print(f"  READING LEVEL PER SCREEN   (target: grade {TARGET_GRADE} or below)")
    print("=" * 74)
    worst = []
    for label, text in screens():
        fk, words, sents = grade(text)
        if fk is None:
            continue
        flag = "  <-- too hard" if fk > TARGET_GRADE else ""
        print(f"  {label:<18} grade {fk:>5}   {words:>5} words  "
              f"{sents:>3} sentences{flag}")
        if fk > TARGET_GRADE:
            worst.append(label)

        longs = [s for s in sentences_of(text) if len(s.split()) > LONG_SENTENCE]
        for s in longs[:2]:
            print(f"      {len(s.split()):>3} words: {s[:88]}…")

    print()
    print("=" * 74)
    print("  JARGON A MEMBER WOULD NOT KNOW")
    print("=" * 74)
    # A term used AND explained on the same screen is not jargon -- it is
    # teaching. "Presumptive" is VA's own word and a member will meet it
    # again on VA.gov, so glossing it is better than avoiding it.
    GLOSSED = {
        "presumptive": ("without you having to prove", "without having to prove"),
        "secondary service connection": ("caused or made worse", "caused by"),
    }
    any_hits = False
    for label, text in screens():
        low = text.lower()
        hits = []
        for term in sorted(JARGON):
            if term.lower() not in low:
                continue
            gloss = GLOSSED.get(term.lower())
            if gloss and any(g in low for g in gloss):
                continue
            hits.append(term)
        if hits:
            any_hits = True
            print(f"  {label:<18} {', '.join(hits)}")
    if not any_hits:
        print("  None. Every specialist term is explained where it is used.")

    print()
    if worst:
        print(f"  {len(worst)} screen(s) above the target: {', '.join(worst)}")
    else:
        print("  Every screen is at or below the target.")


if __name__ == "__main__":
    main()
