# HR Merge Replacement Design

This document proposes a deferred heart-rate replacement workflow for Liftosaur Garmin Uploader. The goal is to preserve Liftosaur's accurate strength structure while borrowing heart-rate data from a separate Garmin-recorded workout, such as a Run or Cardio activity started on the watch during the same gym session. The current best-fit architecture is not a true Garmin-side merge. Instead, it is a replacement pipeline: upload the Liftosaur workout first, later detect a nearby Garmin activity once the watch syncs, extract its HR stream, rebuild a new strength FIT with that HR data, upload the replacement, and then remove the superseded activities when safe.

## Why This Feature Exists

Users want Garmin metrics that depend on heart rate, especially calories, Training Effect, Training Load, and Body Battery impact. The current generated strength FIT files do not include a real HR stream, so Garmin has limited information for deriving those metrics. Some users already work around this by starting a separate workout on their watch while lifting. That watch activity captures heart rate well enough, but its set and rep data is poor. Liftosaur has the inverse profile: excellent set structure, no real HR stream. The feature therefore exists to combine the strengths of both records.

## Summary Recommendation

The recommended implementation is a deferred replacement workflow with one-time opt-in.

The user enables HR merge once in setup or config. After that:

1. A new Liftosaur workout arrives and is uploaded immediately using the current strength FIT flow.
2. The upload is marked as pending HR reconciliation.
3. The background watcher periodically checks Garmin for activities that occurred near the same time.
4. If exactly one suitable Garmin activity is found, the tool downloads its HR data.
5. The tool rebuilds the Liftosaur strength FIT with the recovered HR stream.
6. The tool uploads the rebuilt FIT as the final activity.
7. Only after successful replacement does the tool delete the temporary or superseded activities according to policy.

This preserves responsiveness for the normal workflow while supporting delayed watch sync, including cases where the watch does not reach Garmin Connect until one or two days later.

## Non-Goal

This is not a true post-upload Garmin activity merge. The research found no reliable evidence that Garmin Connect supports mutating an existing uploaded activity in place or merging two existing activities server-side. The working assumption should be that Garmin activities are effectively immutable once uploaded. The plan therefore focuses on replacement, not mutation.

## Research Basis

The feature has external precedent at the workflow level, but not at the Garmin-platform mutation level.

What appears established:

- Local HR merging from one workout source into another is technically feasible.
- Replacement workflows exist in adjacent fitness tooling: merge data locally, delete the old activity, upload the corrected one.
- Garmin activity upload is already supported in this repo.

What does not appear established:

- Publicly supported Garmin Connect API for merging two existing activities.
- Publicly supported Garmin Connect API for mutating an activity's HR stream after upload.
- Clear precedent for fully automated Garmin-side activity replacement in community tooling.

This means the proposed feature is plausible, but only if Garmin activity read and delete operations are available through the chosen client library or reachable through stable reverse-engineered endpoints.

## Current Codebase Reality

The codebase already contains some of the right scaffolding for a deferred workflow.

Existing strengths:

- Upload tracking already exists in `liftosaur_garmin/history.py`.
- Persistent profile config already exists in `liftosaur_garmin/config.py`.
- A background watcher already exists in `liftosaur_garmin/templates/watch_and_process.py.template`.
- The FIT generation path is already centralized through `liftosaur_garmin/workout_builder.py` and `liftosaur_garmin/fit/encoder.py`.
- The project TODO already anticipates deferred HR merge in `TODO.MD`.

Current blocker:

- The Garmin adapter layer in `liftosaur_garmin/garmin_client.py` is upload-oriented. It currently supports authentication, session resume, FIT upload, and weight lookup, but not activity listing, activity download, or activity deletion.

That adapter gap is the critical feasibility gate.

## Product Decisions Captured So Far

These decisions are based on the current discussion and should be treated as defaults unless changed later.

- Approval model: one-time opt-in, then automatic reconciliation in the background.
- Delete policy: automatic deletion after successful replacement.
- Backfill window: 48 hours.
- Architecture preference: replacement workflow if Garmin in-place merge is unsupported.

A key implication follows from those choices: because the watcher is non-interactive, there can be no per-workout prompt inside the background loop. Any approval UX must be setup-time, config-driven, or handled through a separate manual-review command.

## Proposed User Experience

### Initial Setup

The user enables a config option such as HR merge or replacement mode. Setup explains the behavior in plain terms:

- the tool will try to find a Garmin activity near the Liftosaur workout time
- if a match is found, it will rebuild the Liftosaur activity with HR data
- if replacement succeeds, it may automatically delete the source watch activity and the earlier temporary upload
- delayed sync is supported for up to 48 hours
- ambiguous matches may require manual review

### Normal Flow

1. User performs a workout in Liftosaur.
2. User also starts a watch workout, likely Run, Cardio, or Strength, to capture HR.
3. Liftosaur data is exported or synced into this tool.
4. The current system uploads the strength workout immediately.
5. The history entry is marked pending HR reconciliation.
6. Later, when the watch activity syncs to Garmin Connect, the watcher sees a candidate in the matching window.
7. The tool downloads the source activity's HR stream.
8. The tool generates a new FIT file with Liftosaur structure plus Garmin HR samples.
9. The tool uploads the replacement FIT.
10. If upload and validation succeed, the tool deletes obsolete activities and marks reconciliation complete.

### Delayed Sync Flow

This is the same as the normal flow except the source watch activity may not appear until hours or days later. The watcher will continue retrying until the 48-hour window expires.

### Failure Flow

If no activity appears, if multiple activities match, if HR download fails, or if the replacement upload fails, the system should not guess. It should record the state and either retry later or stop with a manual-review reason.

## Matching Model

The matcher needs to be explicit and conservative.

### Inputs

- Liftosaur workout start time
- Liftosaur workout end time or estimated duration
- configurable time window around the workout start, initially 5-10 minutes but likely a profile-level setting
- Garmin activity summary metadata, including start time, duration, type, and id

### Recommended Matching Rule

Primary candidate rule:

- choose Garmin activities whose start time falls within a configurable threshold of the Liftosaur workout start time

Suggested default:

- start within plus or minus 10 minutes of Liftosaur workout start

Secondary tie-breakers:

- overlap duration with the Liftosaur workout window
- preferred activity types if defined later
- closest start-time distance

Hard stop conditions:

- no candidates in window
- more than one equally plausible candidate
- activity exists but does not expose HR data
- candidate is already known to have been consumed by a prior replacement

Ambiguous matches should be deferred to manual review rather than auto-resolved.

## Replacement Workflow In Detail

### Stage 1: Initial Upload

The current flow remains mostly unchanged.

On successful upload of a Liftosaur-generated FIT:

- create or update history entry for that workout
- mark it as pending HR reconciliation if the profile has HR merge enabled
- store enough metadata to revisit the workout later

Recommended stored fields:

- workout datetime key
- upload timestamp
- source type and source id if known
- workout start and end times
- pending flag
- first-attempt time
- retry count
- timeout deadline
- preliminary Garmin upload id if the upload endpoint returns one, otherwise null
- merge status enum such as pending, matched, rebuilt, replaced, expired, failed_manual_review
- failure reason if applicable

### Stage 2: Background Reconciliation

Each watcher pass should, after its normal CSV and API sync work, inspect pending workouts and attempt reconciliation.

Per pending item:

1. Skip if expired.
2. Query Garmin for recent activities around the workout time.
3. Apply matching rules.
4. If exactly one candidate matches, download the activity payload or at least the HR stream.
5. Build a merged representation.
6. Validate the resulting FIT file.
7. Upload the replacement.
8. Delete superseded activities only if the replacement upload clearly succeeded.
9. Mark the item complete.

### Stage 3: Cleanup

Deletion order matters. A safe sequence is:

1. Upload replacement FIT.
2. Confirm upload success and, if possible, capture replacement activity id.
3. Delete the watch-source activity.
4. Delete the first-pass Liftosaur upload.
5. Persist final state.

If any step after replacement upload fails, the system should stop and record enough context for cleanup. It should never delete source activities before the replacement exists.

## Data Model Changes

### Config Additions

The profile config in `liftosaur_garmin/config.py` should gain fields along these lines:

- `hr_merge_enabled`
- `hr_merge_match_window_minutes`
- `hr_merge_backfill_hours`
- `hr_merge_auto_delete_source`
- `hr_merge_auto_delete_temporary_upload`
- `hr_merge_preferred_activity_types` if activity-type filtering becomes useful later
- `heart_rate_fallback_bpm` for the earlier fallback-HR phase

### History Additions

The history structure in `liftosaur_garmin/history.py` should be extended to support pending and completed reconciliation state.

Recommended fields per workout:

- `hr_merge_status`
- `hr_merge_enabled_for_upload`
- `hr_merge_retry_count`
- `hr_merge_next_retry_at`
- `hr_merge_deadline_at`
- `matched_source_activity_id`
- `matched_source_activity_type`
- `replacement_activity_id`
- `initial_uploaded_activity_id`
- `hr_merge_failure_reason`
- `hr_merge_last_attempt_at`

The state needs to support idempotency. If the watcher runs multiple times, it should not re-consume the same source activity or upload duplicates blindly.

## New Module Responsibility

A dedicated module, likely `liftosaur_garmin/hr_merge.py`, should own all HR replacement logic.

Suggested responsibilities:

- search for candidate Garmin activities in a time window
- decide whether a candidate is safe to use
- download HR data or the original FIT payload
- transform downloaded data into the shape needed by the current builder or encoder
- request a rebuilt strength FIT that includes HR records
- orchestrate replacement upload and cleanup
- manage retry timing and timeout behavior
- return explicit, inspectable statuses rather than opaque booleans

This separation matters because the replacement flow will be stateful and failure-prone. It should not be spread across the CLI, watcher, and uploader in ad hoc conditionals.

## Garmin Adapter Requirements

This is the most important technical gate.

The adapter layer in `liftosaur_garmin/garmin_client.py` will need new capabilities beyond upload.

Minimum required methods:

- list activities in a date or time range
- fetch activity details sufficient to obtain a heart-rate stream, ideally the original FIT file or a sample stream endpoint
- delete an activity by id

Preferred method contract shape:

- explicit return types or structured dicts for activity summaries
- stable fields like activity id, type, start time, duration, and source device when available
- error reporting that distinguishes auth failure, endpoint unsupported, activity not found, and malformed payload

Open risk:

- the currently supported libraries may not expose all of these operations cleanly
- if one adapter can do it and the other cannot, the feature may need to be limited to a single Garmin client backend

The project should not move into FIT-level implementation until this capability is proven.

## FIT Merge Strategy

If the Garmin API gate is cleared, the next hard problem is generating a valid merged FIT.

The safest approach is to treat the existing Liftosaur-generated strength FIT as canonical and inject HR record data into that structure. The new merged file should preserve the current message ordering and semantics as much as possible while adding the HR-bearing records Garmin expects.

Important constraints from the current project:

- the custom encoder in `liftosaur_garmin/fit/encoder.py` is intentional and should not be replaced
- message order matters for Garmin validation
- the project already validates output using FitCSVTool

Open FIT questions to answer during design or spike work:

- does Garmin require per-second record messages for the relevant metrics, or will coarser HR sampling still produce useful calorie and training metrics
- how should HR samples be aligned to Liftosaur set timestamps if the watch activity starts earlier or ends later than the structured lifting workout
- should non-HR data from the watch activity be discarded entirely, or selectively preserved if helpful
- what happens if the watch activity only samples HR every 10-15 seconds

The first implementation should stay narrow: use only the HR stream, map it conservatively onto the Liftosaur workout duration, and avoid trying to fuse extra watch metrics unless they are required.

## Backfill and Retry Behavior

The backfill path is a first-class requirement, not an edge case.

Recommended behavior:

- every newly uploaded Liftosaur workout is eligible for reconciliation if HR merge is enabled
- retries should happen on every watcher run until either the workout is reconciled or the deadline passes
- the default deadline should be 48 hours after initial upload
- after expiry, the system should mark the workout expired rather than leaving it indefinitely pending

Recommended retry states:

- pending_waiting_for_watch_sync
- pending_candidate_search
- pending_manual_review
- replacement_uploaded_cleanup_incomplete
- complete
- expired
- failed_unsupported_api

This will make support and debugging much easier than a single boolean flag.

## Safety Rules

Because deletion is destructive, the workflow needs clear guarantees.

Mandatory rules:

- never delete the source watch activity before the replacement upload succeeds
- never delete the first-pass Liftosaur upload before the replacement upload succeeds
- if replacement upload succeeds but later cleanup fails, preserve enough ids to allow retry or manual cleanup
- if activity matching is ambiguous, do not guess
- if the downloaded watch payload has no usable HR data, do not replace anything
- if Garmin API support is partial or unstable, fail closed and leave the original activities untouched

## CLI and Operational Surface

Even with automatic background behavior, the user needs observability and manual controls.

Recommended additions to `liftosaur_garmin/cli.py`:

- a setup option to enable HR merge and choose delete behavior
- a status command to list pending and failed reconciliations
- a force command to run reconciliation now for pending items
- a manual review or resolve command for ambiguous matches
- a disable flag for one-off uploads where replacement is undesirable

This is especially important because the watcher is non-interactive. Without inspection commands, debugging background replacement would be painful.

## Verification Plan

The feature should be treated as successful only if it passes both technical and Garmin-behavior validation.

### Feasibility Validation

- prove that the chosen Garmin backend can list activities in the required time window
- prove that it can download HR-bearing data for a chosen activity
- prove that it can delete a test activity non-interactively

### Matching Validation

- verify single-match behavior with a clean watch-plus-Liftosaur pair
- verify ambiguity behavior with multiple nearby watch activities
- verify no-match behavior when the watch never syncs

### FIT Validation

- validate every rebuilt FIT with `python -m liftosaur_garmin validate <file.fit>`
- compare the merged structure against a real Garmin strength FIT where useful

### Garmin Product Validation

- confirm the final activity shows an HR graph in Garmin Connect
- confirm calories improve compared to no-HR uploads
- confirm Training Effect and Training Load behavior is acceptable if those metrics appear
- confirm the final activity still behaves like a strength workout rather than degrading into a generic cardio record

### Failure Validation

- simulate watch sync arriving late
- simulate replacement upload failure
- simulate delete failure after successful replacement upload
- confirm the system preserves originals until replacement is safe

## Scope Boundaries

Included in this proposal:

- matching a nearby Garmin activity by time
- downloading HR data from that activity
- rebuilding a Liftosaur strength FIT with HR
- delayed retry and 48-hour backfill
- optional automatic cleanup after confirmed success

Excluded from this first proposal:

- true server-side Garmin activity merge
- combining multiple source watch activities into one replacement
- preserving every sensor stream from the watch activity beyond what is needed for HR-based Garmin metrics
- heart-rate data from third-party files or services not already in Garmin, unless a later `--hr-file` path is added
- multi-user coordination beyond the existing profile model

## Main Risks

### Risk 1: Garmin API Support Is Incomplete

This is the single largest risk. If activity list, download, and delete cannot all be done reliably through a supported backend, the feature should not proceed in its current form.

### Risk 2: Garmin May Not Credit Metrics As Expected

Even with a valid merged FIT, Garmin may not compute all desired metrics unless the file shape closely resembles a native device-generated workout. Calories are the most likely win. Training Effect and other derived metrics may be more sensitive.

### Risk 3: Cleanup Semantics Are Tricky

If the replacement succeeds but one delete call fails, the user may see duplicates temporarily. The system must be explicit about that and provide cleanup tools.

### Risk 4: Matching False Positives

Users may record multiple gym-adjacent activities on the same day. The matching rules must be conservative enough to avoid attaching the wrong HR stream to the wrong lifting workout.

## Implementation Recommendation

The work should start with a strict Phase 0 feasibility spike and only proceed if it passes.

Recommended execution order:

1. prove Garmin list, download, and delete capabilities against the current adapter ecosystem
2. define final state model for history and config
3. design the matcher and replacement state machine
4. prototype HR extraction from a real downloaded activity
5. prototype FIT rebuild and validation with injected HR
6. wire background reconciliation and cleanup
7. add user-facing status and manual-review commands
8. document risks, behavior, and troubleshooting clearly

## Decision Gate

This proposal should be approved only if the team accepts the following framing:

- the feature is a replacement workflow, not a true merge
- the first milestone is an API capability spike, not product implementation
- deletion is allowed only after confirmed replacement success
- unresolved ambiguity falls back to manual review

If those constraints are acceptable, the idea is worth pursuing. If the API spike fails, the best fallback is not to force this architecture. The fallback would likely be either a manual `--hr-file` import path or a read-only local HR analytics feature outside Garmin replacement.

## Short Conclusion

This feature is plausible, useful, and aligned with how users actually work around the HR gap today. The codebase already has the right shape for deferred reconciliation, but the Garmin adapter layer is not yet capable of supporting it. The right next step is to validate whether Garmin activity read and delete operations are truly available. If that gate passes, a conservative replacement pipeline with one-time opt-in and 48-hour backfill is the most coherent design.
