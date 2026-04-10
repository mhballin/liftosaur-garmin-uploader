# Exercise Mapping Research

This note summarizes external research used to validate exercise mappings for Garmin FIT strength activities.

## Primary sources

- Garmin FIT SDK overview: Profile.xlsx is the authoritative reference for FIT messages, enums, and field values.
- Garmin FIT SDK Java enums shipped inside FitCSVTool.jar: used to confirm category IDs and exercise subtype IDs.
- Garmin developer forum discussions: strength encoding guidance and notes that many Garmin Connect exercise names do not have a perfect one-to-one match with FIT enum constants.
- Garmin Connect community exercise list: user-extracted list of visible Garmin exercise names used as a secondary sanity check for naming coverage.

## Validation principles

1. Prefer an exact Garmin FIT enum match when one exists.
2. Prefer a Garmin Connect-visible exercise name that is also present in the FIT SDK.
3. When no exact match exists, choose the closest Garmin exercise that should preserve the right muscle graphic and general movement pattern.
4. Avoid broad substring matching because it collapses specific variants into generic lifts.

## Confirmed exact or near-exact mappings

- Incline Bench Press, Dumbbell -> Bench Press category / Incline Dumbbell Bench Press subtype.
- Sumo Squat -> Squat category / Sumo Squat subtype.
- Cable Pull Through -> Chop category / Cable Pull-through subtype.
- Hip Abductor, Cable -> Hip Stability category / Standing Cable Hip Abduction subtype.
- Side Hip Abductor, Leverage Machine -> Hip Stability category / Standing Hip Abduction subtype.
- Leg Extension -> Banded Exercises category / Leg Extension subtype.
- Seated Leg Press -> Squat category / Leg Press subtype.
- Lying Leg Curl -> Leg Curl category / Leg Curl subtype.

## Best-fit approximations

- Glute Kickback -> Hip Stability category / Standing Rear-leg Raise subtype.
  Garmin public exercise lists do not appear to expose an exact Glute Kickback entry in the FIT strength enums used here.
- Chest Fly, Cable -> Flye category / Cable Crossover subtype.
  Garmin public naming clearly includes Cable Crossover, while a direct Chest Fly, Cable FIT subtype was not found.

## Supporting observations from Garmin forums

- Garmin developers and users treat Profile.xlsx as the canonical source for FIT profile definitions.
- Community strength-encoding discussions report that many Garmin Connect editor names do not map cleanly to ExerciseCategory and FooExerciseName constants.
- A practical recommendation from the forum is to choose the closest Garmin exercise constant so Garmin Connect displays the correct muscle graphic and exercise title behavior.

## Remaining caution

- Garmin Connect UI names, Garmin FIT enum names, and exercise titles shown in exported activity files are related but not always identical.
- Where an exact FIT enum was unavailable, mappings are intentionally best-fit rather than guaranteed canonical.
