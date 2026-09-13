---
name: Campaign Profile Template
type: template
keywords: [campaign, profile, template, settings, selections, chain, toggles]
description: Per-campaign settings — which rules chain is active, which compiled ruleset is in force, and which doctrine and presentation options are selected. Names its setting rather than restating anything the setting owns. Copy to Campaign_Profile.md in the campaign directory.
---

CAMPAIGN PROFILE — TEMPLATE
===========================

**Copy this to `Campaign_Profile.md` in the campaign's own directory**, beside its checkpoints and
its compiled ruleset. That filename is what `Core_Rules/Start_Here.md` looks for; a profile under any
other name will not be found.

It is the campaign's answer to every question the modules leave open. **A campaign without one is
not broken** — the shipped defaults apply and the setting is the directory it sits under. Write a
profile when you want to change something.

**This is a selection, not a rule change.** Three levels are easy to confuse:

| | What it does | Where it lives |
|---|---|---|
| **Shipped module** | Declares defaults and the menu of valid values | `Core_Rules/`, `Game_Systems/` |
| **Campaign profile** | *Selects* among the options a module offers | the campaign directory — this file |
| **Homebrew sidecar** | *Changes or adds rules* | beside the module, or `homebrew_campaign.md` |

Putting a rule change in the profile does nothing — no module reads it there. Putting a toggle in
homebrew works but hides a one-word decision inside a rules delta. Keep them separate.

---

```yaml
campaign: [Campaign_Name]
setting:  [Setting_Name]

# ---- Which rules are in force -------------------------------------------

chain: [Baseline]
# The module chain, lowest first. Baseline alone, or a system stacked on it:
#   [Baseline, DnD5e]
#   [Baseline, DnD5e, DarkSun]     — a variant module declaring `extends: DnD5e`

edition:
# Required where the active system has incompatible published editions.
# Omit when the chain is Baseline alone.

adaptation:
# The resolved profile for this chain, e.g. Game_Systems/Adaptations/Baseline_DnD5e.md.
# Required whenever the chain is longer than one module — the compile refuses
# without it, because a manifest alone cannot express "extend" or "partition".

homebrew:
  -
# Sidecars in effect, in load order. Campaign-scoped changes go in
# homebrew_campaign.md beside this file, which loads last and wins over all.

compiled_ruleset:
# The build output for the above, e.g. Active_Rules.md beside this file.
# Where this names a fresh compile, it is the whole ruleset and nothing else
# is loaded — see Core_Rules/Start_Here.md, branch (a). Leave empty to load
# the modules individually; that is correct for a Baseline-only campaign and
# provisional for any longer chain.

# ---- Doctrine ------------------------------------------------------------
# Defaults are Core_Rules/gm_rules.md's; state a value here only to change it.

pc_rendering: full
# full   — the GM renders the PC's delivery, body language and manner of speaking
# spoken — only what the player supplied; neutral staging only

pacing_bias: escalation
# escalation — scenes tend to make things worse or different
# causal     — a quiet scene or a routine success is a complete scene

momentum_stall: on
# on  — the world advances if the player is passive for three beats
# off — the world advances on its own causal schedule only

# ---- Presentation --------------------------------------------------------

choice_options: 3-5
# A range, a fixed number, or `none` for freeform-only play.

status_block: on
# on | time_only | off

scene_tag: on
# on | off — see the warning below before turning this off.

# ---- Progression ---------------------------------------------------------

skill_trees: off
# on  — the Emergent Skill Tree System is active for this PC
# off — no tree tracking
# Ignored when the active system defines its own advancement.
```

---

## Setting

The setting this campaign runs in. Naming it is what lets everything setting-scoped resolve without
being restated here.

> [Setting name — the directory under `World_Building/`.]

**The prose register lives with the setting, not in this file.** A setting's period, its tone, how
the fantastic sits inside everyday life and what the prose should and should not reach for are
shared by every campaign in that world; restating them per campaign is how two campaigns in one
setting quietly drift apart. `Core_Rules/gm_rules.md` sends the GM to the setting's register, and that
resolves at `World_Building/[Setting]/Setting_Profile.md` > *PROSE REGISTER*.

## Skill tree notes

Where `skill_trees: on`, record the **per-campaign** judgement `Game_Systems/Baseline/skill_trees.md` asks for: whether
this PC is a genuine blank slate, and what this campaign treats as capability development.

> [Notes, or "not applicable".]

**Essence starting points are per-setting, and are not recorded here.** What a transformation or a
binding produces is a fact about the setting's own machinery, and two campaigns in the same world
should not answer it differently. They live at `World_Building/Project_Profile.md` > *Essence
archetype — setting starting points*.

---

## Warnings

**Turning off the scene tag removes the witness record.** The tag's *format* is presentation and
can be changed freely, but the names it carries are read back later as evidence of who knew what.
`scene_tag: off` leaves the Information Firewall with no structured input: witness tracing falls
back to unstructured prose and whatever durable records exist, and later sessions may not be able
to recover who was present.

**It is a valid selection, and it is not silent.** The cost above is reported prominently at load
rather than blocked — same posture as the epistemics homebrew below, and for the same reason. You
are strongly advised to define a replacement record and its retrieval path in a homebrew sidecar;
you are not required to. Claiming a replacement that does not exist or cannot be retrieved *is*
invalid, because that is a broken configuration rather than a choice. See `Core_Rules/epistemics.md`, *The
witness record*, and `Core_Rules/presentation.md`, *Scene tag*.

**An epistemics homebrew is reported, not blocked.** Listing one is allowed — this is your engine —
but the compile surfaces it prominently rather than folding it in with the rest, because that is
the module whose rules the rest depend on.

**Changing `chain` or `adaptation` mid-campaign invalidates the compiled ruleset.**
`Active_Rules.md` records the hashes it was built from and refuses when they move. Recompile
deliberately rather than editing the compiled file.
