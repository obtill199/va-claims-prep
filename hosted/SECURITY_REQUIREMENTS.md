# Hosted deployment — what has to be true first

For whoever is taking this from prototype to something real. The code in
`hosted/` is a shell: the client/server split made concrete, with every
security control left as an unimplemented stub in `hosted/security.py`.
Nothing here accepts a record; the endpoints return HTTP 501 and start-up
refuses any non-loopback bind while the stubs remain.

## What the data actually is

One upload contains, in a single file: full name, date of birth, home
address, phone, SSN, DoD ID/EDIPI, complete diagnosis history with ICD-10
codes and dates, treating clinicians by name, duty limitations, and mental
health treatment history. The source records carry a **CUI** banner
(`CUI Category: PRVCY, HLTH`).

Practically this means a hosted deployment is handling PHI and CUI about a
protected population, and the operator is the custodian.

## Regimes this likely falls under

Not legal advice — a starting map for someone who knows this ground.

| Regime | Applies when | Core obligations |
|---|---|---|
| HIPAA Security Rule, 45 CFR §164.308–312 | Operating as a covered entity or business associate | Access control, audit controls, integrity, transmission security, risk analysis, BAAs |
| 38 U.S.C. §5701 / §7332 | Veteran records; §7332 covers drug/alcohol, HIV, sickle cell | Confidentiality, restrictions on disclosure that are stricter than HIPAA |
| FISMA + NIST SP 800-53 | Operated for, or connected to, a federal agency | Full control baseline, ATO process |
| VA Handbook 6500 | Anything touching VA systems | VA-specific control tailoring |
| NIST SP 800-171 | CUI held on non-federal systems | 110 controls; the likely floor even without a VA connection |
| State breach law | Always | Notification timelines, AG reporting |

`§7332` is worth early attention: the records this tool parses routinely
contain substance-use and mental-health treatment, and that category carries
disclosure restrictions that ordinary HIPAA consent does not satisfy.

## The seven stubs

Each is a function in `hosted/security.py` with its rationale in the
docstring. `unimplemented_controls()` reports which remain, and the app gates
on it.

| Stub | Control | The hard part |
|---|---|---|
| `authenticate` | IA-2, IA-8 | Veterans will expect Login.gov or ID.me. Data of this sensitivity argues for IAL2/AAL2, which means real identity proofing and MFA. |
| `authorize` | AC-3 | IDOR. Ownership checked on *every* access, not at creation. One veteran retrieving another's package is the worst outcome available. |
| `scan_upload` | SI-3, SI-10 | This service feeds uploaded bytes to pypdf, pdfplumber and PyMuPDF — memory-unsafe parsers, reachable by whoever gets past auth. Sandbox and resource-limit the parse. |
| `encrypt_at_rest` | SC-28 | Key management, not the cipher. KMS/HSM, per-record data keys, rotation, keys out of the app and the repo. |
| `decrypt_at_rest` | SC-28 | Same. |
| `audit_log` | AU-2, AU-9 | Append-only, tamper-evident, and must not become a second copy of the PHI — log identifiers and actions, never diagnoses or names. |
| `enforce_retention` | SI-12, MP-6 | Real destruction — overwrite or crypto-shred the data key — not a deleted flag. |

## Beyond the stubs

The stubs are the application layer. These are not represented in code and
still have to exist:

- **TLS everywhere**, HSTS, modern ciphers only (SC-8, §164.312(e)).
- **Retention policy as a decision.** The strongest control here is not
  keeping the data. Hold uploads for the life of the job, destroy inputs and
  outputs immediately after, and make the window a stated promise.
- **Rate limiting and abuse controls** on upload.
- **Secrets management** — no keys, tokens or credentials in the repo.
- **Logging hygiene** — application and web-server logs must not capture
  filenames, form values, or record content.
- **Backups are copies of PHI.** Whatever the retention promise is, backups
  must honour it too.
- **Incident response and breach notification** with named owners and
  timelines, written before it is needed.
- **Vulnerability management** for the PDF/OCR dependency chain.
- **Independent assessment** — pen test and, if federal, the ATO process.

## The architectural question worth asking first

The local tool has no meaningful attack surface: no listener reachable
off-box, no accounts, no stored records, no operator, nothing to breach.
Those are not accidents — they are the security design, and hosting trades
away all of them at once in exchange for convenience.

Before implementing the seven stubs, it is worth deciding whether the goal
("my buddy shouldn't have to run a terminal command") can be met without
taking custody of anyone's medical records at all:

1. **Packaged desktop app.** PyInstaller or similar produces a
   double-clickable bundle. Same local-first properties, no install
   friction, no server, no custodian. Cost: code signing and notarization,
   per-platform builds.
2. **Client-side only in the browser.** Pyodide/WASM would keep processing
   on the user's machine while being reachable from a URL. The blocker today
   is the dependency chain — PyMuPDF and the macOS Vision OCR path will not
   run in WASM; pypdf and pdfminer might.
3. **Hosted, processed in memory, never persisted.** If hosting is
   necessary, the smallest defensible version accepts a file, processes it
   in memory, returns the package, and retains nothing. Most of the table
   above still applies, but retention and backup risk largely disappear.

Option 1 gets most of the convenience for a small fraction of the
obligation. Option 3 is the one this shell is shaped for. The choice is a
security decision more than a product one, which is why it belongs to
whoever owns this document.
