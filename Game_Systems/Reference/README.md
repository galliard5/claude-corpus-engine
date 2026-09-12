---
name: Game Systems Reference
type: reference
keywords: [reference, provenance, recall, hazards, interface, adaptation, measurement, not-rules]
description: Evidence behind the system modules and the interface between them — recall measurements, interface test findings, and the reasoning they support. Not rules; nothing here is loaded at play.
---

# Game_Systems/Reference

**Nothing in this directory is a rule, and nothing here is loaded at play.**

The modules beside it state what a system does. This directory holds the **measurements and findings
those statements rest on** — what a model actually recalls about a published system, and what
building a second module revealed about the interface itself.

## What is here

| | |
|---|---|
| `Recall_Hazards.md` | Where model recall of a published system fails, and the shape of the failure. Shared across modules rather than copied into each; cited by `Game_Systems/DnD5e/dnd5e.md` |
| `Interface_Test_Notes.md` | What building the sample d20 module revealed about the call-site interface — including why the adaptation pass exists at all |
| `Recall_Tests/` | The prediction-then-verify pairs behind `Recall_Hazards.md`, committed before any source was consulted |

## Why the hazards document is shared

`Interface_Test_Notes.md` §1 settles this: the measured hazard is **structure-shaped, not
system-shaped**. What recall drops is second damage components, non-primary dice counts, riders and
defensive traits — and that pattern holds regardless of which system is loaded. A copy inside each
module would duplicate it and invite the copies to drift apart. Each module carries only its own
deviation from the general picture.

## How to read the recall tests

**As measurements with a date and a subject, not as facts about models in general.** Each pair
records predictions committed before any source was consulted, then the verified result. They
measure one model against one system at one time. A different model, a later version, or another
system is a different measurement, and treating one of these results as standing for any of those
would be exactly the error the tests were built to catch.

They are kept because the operating rule in `Recall_Hazards.md` is only as good as the evidence
under it, and a rule whose evidence is gone becomes folklore.

## Attribution

`Recall_Tests/` cites SRD 5.1 values as measurements. That content is available under CC-BY-4.0 and
the repository-level `NOTICE` carries the attribution for it, alongside the module's own — one
notice covering both, rather than a line per file.

## What belongs here later

Evidence supporting the system modules or the interface between them. Provenance for the **core
rules** split — why a rule is doctrine rather than system — lives in `Core_Rules/Reference/`
instead.

Where a document here disagrees with a module, **the module is right.** This is the record of how a
decision was reached, not a second copy of the decision.
