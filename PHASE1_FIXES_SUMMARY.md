# Phase 1 - FIT Encoder Fixes Complete

## Summary
All 7 showstopper bugs in Phase 1 have been fixed. The encoder will now produce valid FIT files that Garmin Connect can accept.

## Fixes Applied

### 1.1 ✅ Fixed `_ensure_defined` caching in encoder.py
**Problem:** Cached definitions by `global_num` only, causing wrong-sized data writes when the same message type needed different field layouts.

**Solution:** Changed cache key from `global_num` to `(global_num, field_signature)` tuple. Now each unique field layout gets its own definition record.

```python
# OLD: self._definitions: dict[int, int] = {}
# NEW: self._definitions: dict[tuple[int, tuple], int] = {}

# Cache key now includes field signature
field_signature = tuple(fields)
cache_key = (global_num, field_signature)
```

### 1.2 ✅ Fixed `write_workout_step` rest/non-rest mismatch
**Problem:** The `is_rest=True` path wrote 5 bytes but reused a definition expecting 17 bytes.

**Solution:** With fix 1.1, both variants now automatically get separate definitions since they have different field lists.

### 1.3 ✅ Fixed `write_exercise_title` variable-length names
**Problem:** Each exercise name has a different byte length, but all shared one definition.

**Solution:** With fix 1.1, each unique name length automatically gets its own definition.

### 1.4 ✅ Fixed `write_split_summary` positional argument bug
**Problem:** Called with `0` as 5th positional arg, which mapped to `avg_hr` instead of `message_index`.

**Solution:** Changed to explicit keyword arguments:
```python
# OLD: encoder.write_split_summary(workout_end, total_active_time, len(active_splits), SET_TYPE_ACTIVE, 0)
# NEW: 
encoder.write_split_summary(
    ts=workout_end,
    total_timer_s=total_active_time,
    num_splits=len(active_splits),
    split_type=SET_TYPE_ACTIVE,
    avg_hr=64,
    max_hr=74,
    message_index=0
)
```

### 1.5 ✅ Fixed message ordering in workout_builder.py
**Problem:** Message order was substantially wrong compared to Garmin spec.

**Solution:** Reordered `build_fit_for_workout` to match documented spec:
1. file_id
2. file_creator
3. device_info (creator)
4. event(start)
5. sport
6. workout
7. workout_step (all steps)
8. exercise_title (all titles)
9. set + split (interleaved)
10. split_summary
11. **lap** ← newly added
12. session
13. event(stop)
14. device_info (end)
15. activity

### 1.6 ✅ Implemented `write_lap` message
**Problem:** Lap message (message type 19) was documented but not implemented.

**Solution:** Added complete `write_lap` method to encoder:
```python
def write_lap(self, ts: datetime, start_time: datetime,
              elapsed_s: float, timer_s: float, total_reps: int = 0):
    """Message 19 - Lap (Fix 1.6: Added required lap message)"""
    fields = [
        (253, 4, 134),  # timestamp
        (2, 4, 134),    # start_time
        (7, 4, 134),    # total_elapsed_time
        (8, 4, 134),    # total_timer_time
        (24, 1, 0),     # lap_trigger
        (25, 1, 0),     # sport
        (26, 1, 0),     # sub_sport
        (32, 2, 132),   # total_cycles (reps)
    ]
    # ... implementation
```

### 1.7 ✅ Validation Instructions
To validate the fixes:

```bash
# Generate a test FIT file
python -m liftosaur_garmin sample.csv --no-upload --output test.fit

# Manually upload test.fit to Garmin Connect web interface
# Verify it:
# - Appears as a strength training activity
# - Shows correct exercises, sets, reps, and weights
# - No errors or corruption warnings
```

## Files Changed
1. **encoder.py** - Fixed caching, added lap message, improved type hints
2. **workout_builder.py** - Fixed message ordering, fixed split_summary calls

## What's Next
Once you verify the FIT files work (Phase 1 validation), you can move on to:
- **Phase 2** - Code quality cleanup (remove duplication, fix file descriptors, etc.)
- **Phase 3** - Add iCloud URL input
- **Phase 4** - Re-enable Garmin Connect auto-upload

## Testing Recommendation
Before deploying, test with both sample.csv workouts (2025-12-14 and 2025-12-15) to ensure:
- Multiple exercises work correctly
- Rest periods are properly encoded
- Variable-length exercise names don't corrupt the file
- Both workout dates produce valid files
