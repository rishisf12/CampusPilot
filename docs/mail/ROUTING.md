# ROUTING.md — how a message finds its section

The rule the college gave: **a message is filed by who sent it.** The
address it was sent to is recorded and shown, but it never decides anything.

---

## 1. The rule model

A **cluster** is a named group of sender ids, filed under one section:

```
"Placement Cell"  -> section: placement
    exact    tnp@iiitdmj.ac.in
    exact    placements@iiitdmj.ac.in
    domain   @placementcell.iiitdmj.ac.in
```

A **rule** is one member of a cluster and carries everything the admin needs
to keep order:

| Field | Meaning |
|---|---|
| `type` | `exact` (one address), `domain` (`@college.ac.in` — every sender on it), `pattern` (a wildcard such as `notice-*@iiitdmj.ac.in`) |
| `value` | the address, the domain or the pattern |
| `section` | where mail from it is filed |
| `cluster` | which named group it belongs to |
| `priority` | higher wins inside a type |
| `is_active` | a disabled rule never matches (and never routes) |
| `notes` | why the rule exists ("the new internship office") |
| `created_by` / `created_at` | the audit trail |

## 2. The routing function

```
routeMail(message) -> { section, matchedRuleId, reason }
```

### Step 1 — normalise the sender

1. Trim; take the address out of `Display Name <addr@host>`.
2. Lowercase. (`TNp@IIITDMJ.ac.IN` is the same office.)
3. Strip a `+tag` when the college's setting says to (`tnp+june@…` is
   `tnp@…`).
4. Which header decides? **From** — after the authentication check. The
   `Sender` and `Reply-To` headers are kept as metadata, and a mismatch
   between `From` and `Sender` is a signal for the quarantine, not a reason
   to route differently.

### Step 2 — match, in this order

1. **exact** rules for the address
2. **domain** rules for the address's domain
3. **pattern** rules

Inside one type: the higher `priority` wins; on a tie, the older rule wins
(so the first registration is the stable one).

### Step 3 — conflicts

A sender registered in two sections is a **conflict**. The rule engine
resolves it by the same order (exact beats domain beats pattern, then
priority) and **writes the conflict to the admin's Conflicts view**, with
both rules named. The admin resolves it by editing a priority or disabling a
rule — the engine never guesses silently.

### Step 4 — no match

The message goes to **Unassigned**: a queue, not a section. Students do not
see it; the admin does, with the sender's address, how much mail it wrote,
and a **suggested section** taken from the words in the mail (a hint, never
a filing). One click puts the sender in a cluster.

### Step 5 — retro-apply

Registering a sender files the mail it already wrote, not only what arrives
later. The re-filing is idempotent (a message already in the right section
is not touched) and every re-filing is written to the audit log.

### Step 6 — manual re-route

An admin can move a message by hand ("Move to"). The move is recorded with
who did it, when, and from where — and it never duplicates or loses a
message.

## 3. What the real clients do (and what we take from them)

The rule shapes below are the ones that exist in the wild; the engine above
takes the best of them.

| System | Its rule shape | What we take |
|---|---|---|
| **Gmail filters** | condition → action ("apply the label X"), all matching filters apply | the *gesture*: "filter messages like these" — a rule created from a message |
| **Outlook rules** | ordered list, per-rule "stop processing more rules" | **the order is explicit and answerable**: "which rule won?" must have an answer |
| **Thunderbird filters** | `AND`/`OR` over conditions, per-account, reorderable | the admin can see and reorder their own rules |
| **Sieve (RFC 5228)** | `if / elsif / else`, first match wins, `stop` | the canonical fallback: `else { fileinto "INBOX.Undecided" }` — our Unassigned queue |
| **MailFlow** | a registered-sender table (`category_list_sources`) + rules with priority, exact-beats-domain by construction | the registered-sender table *is* the cluster model; plus "always for this sender" with a backfill |
| **Fastmail** | rules + per-alias actions, applied to existing mail too | rules that apply to mail already received — our retro-apply |
| **Superhuman** | Split Inbox: a name and a criterion; the system remembers the move | the one-click "this sender always goes to Placement" |

Two decisions worth stating, because the evidence is not unanimous:

1. **Gmail's filter precedence is undocumented**, so we do not copy Gmail's
   behaviour; we use Outlook's explicit ordering (priority, then age) and
   show the winning rule in the UI.
2. **An unmatched sender gets a real home.** Every serious client has one —
   Sieve's "Undecided", Superhuman's "other" split, Gmail's "Primary"
   catch-all. Ours is the Unassigned queue, and it is admin-only, counted,
   and one click from being fixed.

## 4. The test matrix (Phase 2's acceptance)

Table-driven, in `backend/app/tests/test_mail_routing.py`:

| # | Case | Expected |
|---|---|---|
| 1 | exact address matches | that rule's section |
| 2 | the same address in different case | the same section |
| 3 | `Display Name <addr@host>` | the address is used |
| 4 | `tnp+june@host` with tag-stripping on | the `tnp@host` rule |
| 5 | `tnp+june@host` with tag-stripping off | no match → Unassigned |
| 6 | domain rule `@college.ac.in` | that rule's section |
| 7 | pattern rule `notice-*@college.ac.in` | that rule's section |
| 8 | exact **and** domain both match | the exact rule wins |
| 9 | domain **and** pattern both match | the domain rule wins |
| 10 | two exact rules, different priority | the higher priority wins |
| 11 | two exact rules, equal priority | the older rule wins |
| 12 | the same sender in two sections | resolved by priority **and** written to the conflicts view |
| 13 | no rule matches | Unassigned |
| 14 | a disabled rule | never matches |
| 15 | **the same sender to each of the six intake addresses** | **the same section every time** |
| 16 | **six different senders to the same intake address** | **six different sections** |
| 17 | retro-apply after registering a sender | the past mail is filed, once, and audited |
| 18 | routing twice with the same message | one message, no duplicate |
| 19 | a manual re-route | the message moves, the audit records it |
| 20 | a rule that changes section | the mail it filed follows it |

Rows 15 and 16 are the acceptance criteria of the whole product, written as
tests.
