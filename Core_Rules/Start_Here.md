---
name: Start Here
type: rules-reference
keywords: [entry, router, load order, rules, campaign, profile, modules, start]
description: Entry point to the GM ruleset — what the layers are, what to load and in what order, and where a campaign says which rules are in force. Instruction files point here; this file points at everything else.
---

START HERE
==========

**This is the entry point to the ruleset.** It is deliberately short and deliberately stable: it
says what exists and what order to load it in, and nothing else. The rules themselves live in the
modules it names.

> **Why this file exists.** Every instruction file used to name a rules file directly, so every
> change to the rules broke every route into them. This file is the single stable address. Point at
> it once; it absorbs restructures so the things pointing at it never have to change.

---

## The layers

Five, and they are separate because they change for different reasons and answer to different
people.

| Layer | File | What it governs | Changes when |
|---|---|---|---|
| **Doctrine** | `gm_rules.md` | How to GM — prose, pacing, choices, NPCs, consequences, content | Taste changes. Selectable per campaign |
| **Epistemics** | `epistemics.md` | What may be known, by whom, on what basis | Almost never. The floor under everything |
| **Presentation** | `presentation.md` | What the player sees and how it is rendered | Preference changes. The only host-coupled layer |
| **Operating procedure** | `operating_procedure.md` | The harness — session lifecycle, checkpoints, files, version control | The installation changes |
| **The active system** | a module chain under `Game_Systems/` | What resolves how, what a condition is, what recovery requires | The campaign changes |

The first four ship fixed. **The fifth is chosen per campaign**, which is what the campaign profile
is for.

---

## Loading, in order

**1. Read this file.** You are doing that.

**2. Find the campaign profile.** `Campaign_Profile.md`, in the campaign's own directory. It is the
manifest naming which rules are in force, which edition, which adaptation profile, which homebrew
sidecars, which setting, and every doctrine or presentation selection differing from the shipped
default. Format: `Templates/Campaign_Profile_Template.md`.

**Every variable input below is named by that file.** The four fixed modules are named here instead,
because they do not vary — that is what makes this file a stable address.

> **A campaign with no profile is not an error.** The shipped defaults are then in force: Baseline
> alone, doctrine and presentation exactly as their modules declare them, and the setting is the one
> whose directory the campaign sits under. A profile is only needed to *change* something, so
> campaigns that predate this mechanism keep running untouched and nothing has to be migrated.
>
> One exception while the profile split is incomplete: per-campaign judgements recorded in
> `World_Building/Project_Profile.md` — notably which campaigns run skill trees — remain
> authoritative until they move into profiles of their own.

**3. Resolve the rules. Two branches, and only one of them runs.**

**(a) The profile's `compiled_ruleset` names a build, and it is fresh.** That file alone is the ruleset —
every layer, doctrine and epistemics included. Load nothing else from this directory. Loading a
module beside a compile that already contains it means running two copies of the same rule and
resolving conflicts that were resolved at build time.

> **Check freshness first, before accepting this branch.** A compiled ruleset records the inputs it
> was built from and refuses when they have moved. If they have moved, stop and recompile. Do **not**
> fall through to branch (b) — that changes the campaign's rules mid-stream without telling anyone,
> which is the failure the refusal exists to prevent.

**(b) `compiled_ruleset` is empty, or there is no profile.** Load the four fixed modules —
`gm_rules.md`, `epistemics.md`, `presentation.md`, `operating_procedure.md` — then the system chain.

- **With a profile:** the chain in the order it gives, lowest first, then its adaptation profile.
- **With no profile:** `Game_Systems/Baseline/baseline.md` alone. Baseline is the default chain, and
  naming it here is what makes the no-profile case a real instruction rather than an implication.
  Where `World_Building/Project_Profile.md` records that this campaign runs skill trees, also load
  `Game_Systems/Baseline/skill_trees.md` — that record is the campaign's `skill_trees: on` until the
  profile split moves it, and an exception nothing acts on is not an exception.

Treat that result as **provisional** where the chain is longer than one module: a manifest alone
cannot express that a site extends or partitions rather than overriding, so an unresolved chain
silently discards material it should have kept.

**4. Load the setting.** The profile names which one. **With no profile, it is the setting whose
directory the campaign sits under** — a campaign at `World_Building/[Setting]/Scenarios/[Campaign]/`
belongs to `[Setting]`, and that derivation is the rule rather than a guess.

Its prose register — period, tone, how the fantastic sits in everyday life — is in that setting's
own `World_Building/[Setting]/Setting_Profile.md`, and its world state is that setting's own
`World_State_Register.md`. These are **per setting**, shared by every campaign in it; they are not
recorded per campaign. A setting with no profile has no recorded register: say so once, and do not
invent one.

**5. Load the scenario**, if one is in play. `scenario_prep.md` gives the order: the scenario
package first, then the scenario file, the PC sheet, active NPC files, location files for the
opening scene, the most recent session summary, and the calendar.

### When a configuration is invalid

Several rules here and in the modules declare a configuration **invalid** or say a load **refuses**.
They are not duplicated in this file, because a second copy drifts from the first. **The set is not
closed** — a module may declare its own. Those that exist today: a stale compiled ruleset; a chain or
adaptation changed mid-campaign, which staleness the compiled ruleset also refuses; a chain longer
than one module with no adaptation profile; a system asked for an edition it does not implement; a
sidecar claiming a replacement witness record that does not exist or cannot be retrieved.

**What they share is the response, and it is the same one every time:**

1. **Stop before play.** Do not begin a session on a configuration that did not load.
2. **Say which condition failed and where**, naming the file and the setting involved. "Something
   is wrong with the profile" is not a report.
3. **Never substitute a default and continue.** This is the rule the refusals exist for. Falling
   back to shipped behaviour changes a campaign's rules without telling anyone, and the resulting
   session looks entirely normal — which is what makes it worse than stopping.

*This is the same shape as `operating_procedure.md` > Tool availability and `epistemics.md` >
Never assert what you did not obtain: disclose the gap, never paper over it with something that
resembles the real answer.*

**An invalid configuration is a pre-play stop, not a failed session.** Report it plainly so the
player can decide how to repair it. Some repairs are trivial and some are not — a missing adaptation
profile needs the substantive ruling the refusal exists to protect — which is exactly why the
decision is theirs rather than something the GM works around.

---

## Where things are

| Looking for | Go to |
|---|---|
| How to write a scene, run an NPC, apply a consequence | `gm_rules.md` |
| Whether a character can know something | `epistemics.md` |
| The status block, choice format, the scene tag | `presentation.md` |
| Checkpoints, session lifecycle, file layout, commits | `operating_procedure.md` |
| Preparing a scenario and handing it to a session | `scenario_prep.md` |
| Post-session consolidation into world files | `Scenario_Extraction_Rules.md` |
| What resolves how, conditions, recovery, equipment | the active system named by the profile |
| Document structures — checkpoints, sheets, packages, logs | `Templates/` |
| Where a *new* file belongs | `World_Building/Project_Profile.md` |

---

## Two things that are easy to get wrong

**The campaign profile selects; it does not contain.** It names a setting rather than restating the
setting's register, and it names a module chain rather than restating rules. Anything shared by more
than one campaign belongs where it is shared from, or two campaigns drift apart while both look
correct.

**A capability named anywhere in these rules is an example, not a guarantee.** Tool names,
signatures and availability belong to the host. Check the live surface rather than assuming, and
where something is missing, say so once and fall back to a named alternative. Never emit output
shaped like a tool's and present it as the tool's — see `epistemics.md`, *Never assert what you did
not obtain*.
