# SCXRD review record

This review concerns the operable, declared workflow in [the guide](SCXRD_WORKFLOW.md).
A GUI score does not qualify diffraction intensities, automatic space-group
assignment, absorption correction or final refinement. Scientific evidence and
remaining limits are in [validation](SCXRD_VALIDATION.md).

## Method and evidence

Codex implemented and inspected the change. A separate read-only Codex reviewer
and the authenticated local Claude CLI independently reviewed code and actual
headless screenshots. Claude reports identify `claude-opus-5-5`; generated JSON
and full prose remain in ignored `desktop/artifacts/scxrd-review/`. No review
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

## Final assessment

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
`desktop/artifacts/scxrd-review`, `scxrd-gui` and `scxrd-measured` locally.

Measured intensity Rint remains approximately 59%; a complete operable sequence
and improved spot geometry do not qualify that reduction for structure accuracy.
