#!/usr/bin/env python3
# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
timing.py — where the member sits relative to the deadlines that cost money.

The questionnaire asked branch, component and duty status but never a date,
so the tool could not tell a member with 120 days left (file now, through
BDD) from one with 80 (that door is shut) from one who separated in 2019
(different rules entirely). Those three people need different first moves,
and getting it wrong is measured in months of back pay.

Nothing here advises what to claim. It reports which window the calendar
puts you in and what that window is for -- facts about VA's process, not
judgements about your case.

The rules encoded, from VA's pre-discharge and effective-date guidance:

  BDD (Benefits Delivery at Discharge) accepts claims from 180 to 90 days
  before separation. Inside it, VA works the claim while you are still in
  and a decision can land close to your discharge date. Under 90 days the
  program is closed to you -- you can still file, it is just processed as
  a standard claim, generally after you separate.

  After separation, filing within one year of discharge can set the
  effective date back to the day after discharge. Past a year, the
  effective date generally runs from the date of claim.

BDD also requires being on full-time active duty and available for VA
exams for 45 days from the date of claim, which is why component and duty
status are carried into the eligibility note rather than assumed.
"""

from datetime import date, timedelta

BDD_OPENS = 180      # days before separation
BDD_CLOSES = 90      # days before separation
RETRO_WINDOW = 365   # days after separation for the retroactive effective date


def parse(value):
    """Accept an ISO date, a date, or nothing. Never raise on user input."""
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        return None


def assess(separation_date, today=None, component=None, duty_status=None):
    """Return where this member sits, as a plain dict the UI can render.

    state is one of:
      unknown        no date given
      before_window  more than 180 days out -- BDD not open yet
      bdd_window     180 to 90 days out -- the window that closes
      bdd_missed     under 90 days out, still serving
      recently_out   separated within the last year
      long_out       separated more than a year ago
    """
    today = today or date.today()
    sep = parse(separation_date)
    if sep is None:
        return {"state": "unknown", "days": None, "urgency": "info",
                "headline": "Tell us your separation date and this gets specific.",
                "detail": ("The deadlines that decide your effective date are all "
                           "counted from that one date. Without it this tool cannot "
                           "tell you which window you are in."),
                "actions": []}

    delta = (sep - today).days

    if delta > BDD_OPENS:
        opens = sep - timedelta(days=BDD_OPENS)
        return {
            "state": "before_window", "days": delta, "urgency": "info",
            "bdd_opens": opens.isoformat(), "separation": sep.isoformat(),
            "headline": f"BDD opens for you on {opens.isoformat()}.",
            "detail": (f"You have {delta} days until you separate. The BDD window "
                       f"runs from {BDD_OPENS} to {BDD_CLOSES} days out, so it is "
                       f"not open yet — filing early does not help, and the window "
                       f"is only 90 days wide."),
            "actions": [
                f"Set a calendar reminder for {opens.isoformat()}. That is the "
                "first day you can file through BDD.",
                "Request your complete service treatment records now. They take "
                "weeks, and BDD requires you to provide them.",
                "Use the time to get anything undocumented into your record while "
                "you still have military health care.",
            ]}

    if BDD_CLOSES <= delta <= BDD_OPENS:
        closes = sep - timedelta(days=BDD_CLOSES)
        left = delta - BDD_CLOSES
        return {
            "state": "bdd_window", "days": delta, "urgency": "critical",
            "bdd_closes": closes.isoformat(), "separation": sep.isoformat(),
            "days_left_in_window": left,
            "headline": (f"You are in the BDD window. It closes in {left} "
                         f"day{'' if left == 1 else 's'}, on {closes.isoformat()}."),
            "detail": (f"You separate in {delta} days. This is the window VA "
                       f"designed for you, and it does not reopen. Filing inside it "
                       f"is what gets a decision close to your discharge date "
                       f"instead of months after it."),
            "actions": [
                "File VA Form 21-526EZ now, through BDD. This package is what you "
                "take to a VSO to do that.",
                "Book the VSO appointment this week, not after your records arrive. "
                "They can file with what you have and supplement later.",
                "Stay available for VA exams for 45 days from the date you file — "
                "that is a BDD requirement.",
            ]}

    if 0 <= delta < BDD_CLOSES:
        return {
            "state": "bdd_missed", "days": delta, "urgency": "warn",
            "separation": sep.isoformat(),
            "headline": "BDD has closed, but filing now still protects your date.",
            "detail": (f"You separate in {delta} days, which is inside the 90-day "
                       f"cutoff, so BDD is no longer available. That is not a lost "
                       f"claim — it is a slower one. Your claim gets processed as "
                       f"a standard claim, generally after you separate."),
            "actions": [
                "Start the claim anyway. VA sets your effective date when you begin "
                "the online form, and back pay runs from that date.",
                "See a VSO before your last day, while you still have easy access to "
                "your unit and your records.",
                "Get anything undocumented seen and written down before you lose "
                "military health care.",
            ]}

    out = -delta
    if out <= RETRO_WINDOW:
        deadline = sep + timedelta(days=RETRO_WINDOW)
        left = RETRO_WINDOW - out
        return {
            "state": "recently_out", "days": -out, "urgency": "critical",
            "separation": sep.isoformat(), "retro_deadline": deadline.isoformat(),
            "days_left_in_window": left,
            "headline": (f"File within {left} day{'' if left == 1 else 's'} and your "
                         f"benefits can date back to the day after you separated."),
            "detail": (f"You separated {out} days ago. Filing within one year of "
                       f"discharge — by {deadline.isoformat()} — can set your "
                       f"effective date to the day after separation. That is roughly "
                       f"{out // 30} month{'' if out // 30 == 1 else 's'} of back pay "
                       f"already on the table, and it grows until you file."),
            "actions": [
                "Start the online claim today, even with nothing gathered. Beginning "
                "the form sets your effective date before you submit it.",
                "Take this package to a VSO to finish it properly.",
                "Filing on paper instead? Submit an Intent to File (21-0966) first — "
                "that is what preserves the date for paper claims.",
            ]}

    years = out // 365
    return {
        "state": "long_out", "days": -out, "urgency": "info",
        "separation": sep.isoformat(),
        "headline": "There is no deadline to file. There is a cost to waiting.",
        "detail": (f"You separated about {years} year{'' if years == 1 else 's'} ago. "
                   f"The one-year retroactive window has passed, so your effective "
                   f"date generally runs from the day you file — which means every "
                   f"week you wait is a week you do not get back. There is no time "
                   f"limit on filing itself."),
        "actions": [
            "Start the online claim today. The effective date is set when you begin "
            "the form, so starting it costs nothing and stops the clock.",
            "Take this package to a VSO.",
            "If a condition has worsened since an earlier rating, that is an increase "
            "claim, not a new one — ask your VSO which applies.",
        ]}


def bdd_eligibility_caveat(component, duty_status):
    """BDD needs full-time active duty. Guard and Reserve members not on
    full-time orders are the common near-miss, so say it rather than let
    someone plan around a window they cannot use."""
    if not component:
        return None
    # The duty-status labels carry the double spacing of the form they came
    # from; quoting that back at the member looks like a typo in our text.
    duty = " ".join((duty_status or "").split()) or None
    if component in ("National Guard", "Reserve"):
        if duty and duty.startswith("Active Duty"):
            return ("BDD requires full-time active duty. You listed "
                    f"{component} on {duty} — confirm with your VSO "
                    "that your orders qualify before planning around the window.")
        return (f"BDD requires full-time active duty. You listed {component}"
                + (f" and {duty}" if duty else "")
                + ", which usually does not qualify. Ask your VSO which "
                "pre-discharge route applies to you.")
    return None
