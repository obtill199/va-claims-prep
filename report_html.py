#!/usr/bin/env python3
# Copyright (c) 2026 Oliver Tillinghast.
# Licensed under the PolyForm Noncommercial License 1.0.0.
# Free for veterans, VSOs, nonprofits and government. Commercial use
# requires a separate licence -- see LICENSE, NOTICE.md, COMMERCIAL.md.
"""
report_html.py — package documents in formats a VSO office can actually open.

The package used to ship its worksheet, evidence index and buddy letters as
Markdown. Markdown is a fine intermediate and a poor deliverable: double-
clicking a .md file on a government desktop opens Notepad, or nothing, and
what it shows is the pipe characters rather than a table. Handing that
across a desk undercuts the document before anyone reads a line of it.

Two formats, chosen for what happens on a machine you do not control:

  HTML for the reference documents. Opens in any browser by double-click,
  needs nothing installed, and prints to PDF from the browser's own dialog
  -- which matters because VSO appointments run on paper. Styles are
  inlined; there is no stylesheet to lose.

  RTF for the buddy letters. Those exist to be written IN, by somebody who
  is not the veteran and may not be technical. RTF opens editable in Word,
  Pages, Google Docs and WordPad. The desktop build writes .docx instead,
  which is better still, but python-docx needs lxml and lxml does not build
  in the browser.

PDF would be better than HTML and is deliberately not used: generating one
in the browser means another dependency to vendor, and print-to-PDF gets
the same result through software the reader already has.
"""

import html as _html
import re


def _inline(text):
    """Bold and code spans. Escaped first -- the source is generated from
    record data, and a condition name is not trusted markup."""
    out = _html.escape(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"`(.+?)`", r"<code>\1</code>", out)
    return out


STYLE = """
  :root { color-scheme: light; }
  body { font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI",
         Roboto, Helvetica, Arial, sans-serif; color: #1b1b1b;
         background: #fff; margin: 0; padding: 2.2rem 2rem 4rem; }
  main { max-width: 60rem; margin: 0 auto; }
  h1 { font-size: 1.6rem; margin: 0 0 .3rem; }
  h2 { font-size: 1.15rem; margin: 2rem 0 .6rem;
       border-bottom: 2px solid #005ea2; padding-bottom: .3rem; }
  h3 { font-size: 1rem; margin: 1.4rem 0 .4rem; }
  p, li { margin: .5rem 0; }
  /* The conditions table runs to nine columns. On a narrow window it has
     to scroll rather than clip -- a cut-off Source column loses the page
     citation, which is the column a VSO checks first. */
  .scroll { overflow-x: auto; margin: .8rem 0 1.4rem; }
  table { border-collapse: collapse; width: 100%; font-size: 13.5px; }
  th { background: #f0f0f0; text-align: left; font-weight: 650; }
  th, td { border: 1px solid #dfe1e2; padding: .38rem .55rem;
           vertical-align: top; }
  tr:nth-child(even) td { background: #fafafa; }
  code { font-family: ui-monospace, Menlo, Consolas, monospace;
         font-size: .93em; }
  .meta { color: #565c65; font-size: 13px; margin: 0 0 1.4rem; }
  hr { border: 0; border-top: 1px solid #dfe1e2; margin: 2rem 0; }
  /* Paper is the point: VSO appointments run on it. */
  @media print {
    body { padding: 0; font-size: 9.5pt; }
    .scroll { overflow: visible; }
    table { font-size: 8.5pt; }
    th, td { padding: .2rem .3rem; }
    @page { margin: 12mm; }
    h2 { page-break-after: avoid; }
    table, tr { page-break-inside: avoid; }
    a { text-decoration: none; color: inherit; }
  }
"""


def to_html(markdown_text, title, subtitle=None):
    """Render the generated Markdown as a standalone page.

    Deliberately a small converter rather than a dependency: the input is
    produced by this project, so it only ever contains headings, tables,
    bullets, bold and paragraphs.
    """
    body, rows, in_table = [], [], False

    def flush_table():
        nonlocal rows, in_table
        if not rows:
            return
        head, *rest = rows
        body.append("<div class=\"scroll\"><table><thead><tr>"
                    + "".join(f"<th>{_inline(c)}</th>" for c in head)
                    + "</tr></thead><tbody>")
        for row in rest:
            body.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row)
                        + "</tr>")
        body.append("</tbody></table></div>")
        rows, in_table = [], False

    in_list = False
    for line in markdown_text.split("\n"):
        stripped = line.strip()

        if stripped.startswith("|") and stripped.endswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):   # separator row
                continue
            rows.append(cells)
            in_table = True
            continue
        if in_table:
            flush_table()

        if stripped.startswith(("- ", "* ")):
            if not in_list:
                body.append("<ul>")
                in_list = True
            body.append(f"<li>{_inline(stripped[2:])}</li>")
            continue
        if in_list:
            body.append("</ul>")
            in_list = False

        if not stripped:
            continue
        if stripped.startswith("### "):
            body.append(f"<h3>{_inline(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            body.append(f"<h2>{_inline(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            body.append(f"<h1>{_inline(stripped[2:])}</h1>")
        elif set(stripped) <= set("-=") and len(stripped) > 3:
            body.append("<hr>")
        else:
            body.append(f"<p>{_inline(stripped)}</p>")

    flush_table()
    if in_list:
        body.append("</ul>")

    sub = f'<p class="meta">{_html.escape(subtitle)}</p>' if subtitle else ""
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        f"<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{_html.escape(title)}</title>\n<style>{STYLE}</style>\n"
        "</head>\n<body>\n<main>\n"
        + sub + "\n".join(body)
        + "\n</main>\n</body>\n</html>\n"
    )


def _rtf_escape(text):
    out = text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
    # RTF is not Unicode-native; anything above ASCII goes as \uN.
    return "".join(c if ord(c) < 128 else f"\\u{ord(c)}?" for c in out)


def to_rtf(markdown_text, title=None):
    """Render as RTF: editable in Word, Pages, Google Docs and WordPad.

    Buddy letters are the one output somebody has to write into, and the
    person writing is not the veteran and may not be technical. Handing
    them a file their word processor opens and lets them type in is most of
    whether the letter ever gets written.
    """
    out = [r"{\rtf1\ansi\ansicpg1252\deff0",
           r"{\fonttbl{\f0\fswiss Helvetica;}}", r"\fs22"]

    for line in markdown_text.split("\n"):
        stripped = line.strip()
        if not stripped:
            out.append(r"\par")
            continue
        if stripped.startswith("### "):
            out.append(r"\par\b\fs24 " + _rtf_escape(stripped[4:]) + r"\b0\fs22\par")
        elif stripped.startswith("## "):
            out.append(r"\par\b\fs26 " + _rtf_escape(stripped[3:]) + r"\b0\fs22\par")
        elif stripped.startswith("# "):
            out.append(r"\par\b\fs30 " + _rtf_escape(stripped[2:]) + r"\b0\fs22\par")
        elif stripped.startswith(("- ", "* ")):
            out.append(r"{\pntext\f0 \'b7\tab}" + _rtf_escape(stripped[2:]) + r"\par")
        elif set(stripped) <= set("-=_") and len(stripped) > 3:
            out.append(r"\par")
        else:
            text = re.sub(r"\*\*(.+?)\*\*", lambda m: r"\b " + m.group(1) + r"\b0 ",
                          stripped)
            out.append(_rtf_escape(text).replace("\\\\b ", "\\b ")
                       .replace("\\\\b0 ", "\\b0 ") + r"\par")

    out.append("}")
    return "\n".join(out)
