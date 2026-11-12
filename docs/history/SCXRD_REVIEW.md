# SCXRD review record

This review concerns the operable, declared workflow in [the guide](../architecture/SCXRD_WORKFLOW.md).
A GUI score does not qualify diffraction intensities, automatic space-group
assignment, absorption correction or final refinement. Scientific evidence and
remaining limits are in [validation](../parity/SCXRD_VALIDATION.md).

## Method and evidence

Codex implemented and inspected the change. A separate read-only Codex reviewer
and the authenticated local Claude CLI independently reviewed code and actual
headless screenshots. Claude reports identify `claude-opus-5-5`; generated JSON
and full prose remain in ignored `artifacts/scxrd-review/`. No review
score was prescribed. The rubric defines 9 as no material defect observed in
supported, exercised GUI paths, with clear scope/recovery and no severe or
moderate unresolved usability finding. It does not mean perfection.

The GUI probe uses the real native stdio processor, unavailable Python, Chromium
and WebKit, nine stages at three viewport/text sizes, keyboard entry/navigation,
manual cell choice, track exclusion and Undo, masks and Escape, frame browsing,
independent readout/contrast, preserved drafts, recipe saving and candidate
search. Axe checks each of the nine stage views. A separate measured-data probe
checks the MgSiO3 image, geometry/scaling controls and stopping a real background
operation. No native windows or user previews were opened/closed by the checks.

## Findings and action

Claude round 1 scored GUI 6.5, usability 6.0 and interaction 5.5. Fixes included
committed numeric drafts and errors, explicit exclusion controls, stable image
selector and actions, SC-owned history and readout, cell cards, human-readable
states, table paging, responsive controls, a marker legend and mask preview/
Escape/removal. Both reviewers' numerical/file findings were also addressed:
original-count variance, gain units, gap detection, diamond decisions, aperture
support, overload defaults, source/PONI protection and HKLF4 precision guards.

Claude round 2 scored GUI 8, usability 8 and interaction 8.5. Its P2 findings were:

- Extra Exclude header in the intensity table: removed; rows/headers now match.
- Loading labeled as processing: workspace updates have separate text; the
  retained-stage/stop explanation appears only during actual processing.
- Cell decision lacked a visible verb: candidate buttons now say Use cell or
  Selected cell; singular and ambiguous-cell prompts differ.
- Scroll position was unclear: a visible More controls below button appears
  only when content remains below the current view and scrolls to it.
- Poor intensity agreement lacked a warning: scaling now shows an advisory when
  Rint exceeds 20%, explicitly described as an advisory, not acceptance physics.
- Accessibility evidence covered one stage: Axe now checks all nine stages in
  both engines. Stable empty-state capture waits for an enabled Load action.

Additional fixes remove mixed stage/frame progress scales, retain structural
results when only acquisition confirmation changes, explain blocked keyboard
Undo, keep Geometry/Intensities selected when inspecting a marker, use a Save
icon and stronger export controls, and review candidates before proceeding to
Export. The artifact folder's earlier debug/failure captures are excluded from
current evidence; successful reports identify the exercised paths.

## Initial summation-mode assessment (historical)

Claude round 3 returned 8.5/8.5/9.0 and identified a regression from the header
fix: the Tracks table had also lost its required Exclude header. It is restored;
the GUI probe now checks every row against its column headers. Scroll-cue
measurement now happens before paint, measured screenshots wait for layout, and
loading/disabled controls and status messages have been polished.

Claude round 4 verified the final source, screenshots and table regression guard.
It found no remaining P1/P2 issue and scored all three areas **9.0/10**. It
retained minor polish suggestions (label-tone consistency, caption wording,
optional warning badge on the Scaling tab and the persistent last-action line).
These are recorded rather than represented as universal perfection.

| Reviewer | GUI | Usability | User interaction |
|---|---:|---:|---:|
| Implementing Codex, source and actual-output review | 9.0 | 9.0 | 9.0 |
| Separate Codex reviewer, final focused confirmation | 9.2 | 9.1 | 9.1 |
| Claude, final independent round 4 | 9.0 | 9.0 | 9.0 |

All reviewers found no remaining major or moderate issue within the reviewed
scope. Current evidence: 54 stage/layout captures, zero Axe violations across
18 stage checks, explicit row/header consistency guards, candidate-search/CIF
operability, same-executable exact reflection replay, original-count photon
budget, powder-state preservation and measured cancellation. Automated checks
passed: 383 backend tests (two existing ignores), 175 frontend tests, 47 host
tests, production frontend build, Clippy with warnings denied and resource
staging. Existing Calibration, Integration and Map headless regressions also
passed in both engines. Full review prose/JSON and screenshots remain in
`artifacts/scxrd-review`, `scxrd-gui` and `scxrd-measured` locally.

At this initial assessment, summation Rint was approximately 59%. That result
is retained as a negative control; the corrected native-protocol evidence below
supersedes it.


## Native protocol correction (2026-11-12)

The separate Codex reviewer and authenticated local Claude CLI reviewed the
native coordinator adapter, protocol boundary, persistence and current GUI.
All failed/intermediate reports are retained under ignored
`artifacts/scxrd-rint-comparison/`. Initial Claude GUI scores were
provisional because its read permissions did not include the external evidence;
a subsequent invocation explicitly grants read access to the source/evidence.
No scores are inferred from inaccessible screenshots.

Findings fixed include: native checkpoints at every stage; authoritative signed
observation eligibility; original-count moving shadows and exactly-once flipping;
atomic checkpoint assessment/commit; protocol algorithm/control validation;
frame-range agreement; independent search provenance; prior entry before indexing;
inspection/export of the same applied effective document; explicit incompatible
metric recovery; readable native quality reasons with raw flags retained; frozen
control explanations; local Stop and keyboard peak-chart navigation. Unsupported
protocols and manual decisions are rejected explicitly rather than ignored.

The actual fresh GUI probe drives raw-frame load, protocol and calibration,
a/b/c entry before indexing, group/elements, declared mask overrides and
confirmation, then automatic reduction/search. It verifies the changed opening
in the inspected document before restoring the frozen setting, export/inspect
equality, undo, 27 layouts, nine Axe views and local Stop after native masks finish.
The saved-recipe replay is a separate exercised path. The source and array audit
confirms identical measured inputs and all 54 archived arrays in the matched
optimized native builds. This array count follows standalone archive conventions,
including duplicated centres and derived angular support; it does not mean 54
statistically independent measurements. Independent reviewers verified the actual
archives. Broader accuracy and final refinement remain outside the rating scope.


### Final correction review and scores

Claude's initial overall 9 did not imply 9 in every dimension. Separate scores
were 8/8/9; that follow-up and the subsequent rendered 8/8/9 review are retained.
Their remaining findings drove collapsed protocol/support details, a larger
immediately visible results area, global all/usable/excluded observation views,
filtered paging, compact expandable readable reasons, plain-language history,
actual space-group symbols, stronger disabled controls and clearer setup/recovery.
These are view changes; the observation vectors, signed native eligibility and
exports are preserved. A regression checks that filtering retains negative and
MISMATCH observations according to authoritative native eligibility.

Claude then inspected eight new actual native-worker screenshots and the final
receipt (`claude-observations-final.json/.md`). It explicitly scored every
requested dimension 9/10 with no remaining material defect. A separate Codex
reviewer independently inspected the new views and source, including projection
filtering. The implementing Codex inspected source, actual screenshots and the
independent archive comparison.

| Reviewer | GUI | Usability | User interaction |
|---|---:|---:|---:|
| Implementing Codex | 9.0 | 9.0 | 9.0 |
| Separate Codex reviewer | 9.3 | 9.2 | 9.2 |
| Claude Opus 5.5, final rendered review | 9.0 | 9.0 | 9.0 |

Evidence: final fresh setup and candidate search, 27 measured layouts, nine
WCAG A/AA Axe views with zero violations, global observation filters/paging,
inspected/exported effective-protocol equality, protocol Undo and Undo after a
stopped rerun restoring both reduction and candidate. The analytical summation
workflow independently passes 54 Chromium/WebKit layouts and 18 Axe views.
The final native source archive matches all 54 standalone arrays exactly in
`stage-comparison-final-observations.json` under the declared matched build.
Final focused SC tests (31 passed, two local diagnostic probes ignored), frontend
176 tests, strict TypeScript production build, Clippy with warnings denied,
prior full backend suite and 47 host tests pass. Resource staging passes.

Optional polish remains: the compact table can show only a few rows at once;
empty filters/pagers could be hidden; stage terminology and duplicate last-action
text could be more consistent; expanded rows could align numerical cells at the
top; some setup text could change after confirmation. These do not alter the
supported procedure and were not represented as universal perfection. No native
OS-dialog or general diffraction/structure qualification follows from the scores.
