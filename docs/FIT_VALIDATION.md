# FIT File Validation Guide

## What is the FIT SDK?
The FIT SDK is Garmin's official toolkit for working with FIT files. We use its FitCSVTool to validate our generated files because it mirrors what Garmin Connect expects and catches format and schema issues early.

## Common Validation Errors

### Invalid CRC
The FIT file checksum does not match the expected value. FIT files use CRC-16 calculated over the full file, including the 14-byte header. A mismatch usually means a byte was written incorrectly or the checksum was computed over the wrong data.

### Missing required fields
Strength training activities must include core messages and fields or Garmin Connect will reject the upload. Required messages typically include:
- `file_id`
- `file_creator`
- `device_info`
- `event` (start/stop)
- `sport`
- `session`
- `set`
- `activity`
If any required fields are missing in these messages, validation will fail.

### Wrong field types
FIT fields have strict base types like `uint32`, `uint16`, `uint8`, `sint16`, and `string`. If a field is written with the wrong base type or size, FitCSVTool will report a type mismatch and the file may be rejected even if it parses.

### Incorrect message sequence
Message order matters. For strength workouts, the correct sequence starts with `file_id`, then `file_creator`, `device_info`, `event` (start), `sport`, `workout` and related workout messages, followed by interleaved `set` and `record` messages, then `session`, `event` (stop), and `activity`. Deviations can cause validation or upload failures.

## Interpreting FitCSVTool Output
FitCSVTool produces a CSV that includes message definitions, data rows, and field/value pairs. Errors are reported with the message name, field index, and description. Use the CSV to confirm that required messages appear, field values look sane, and message counts match expectations.

## Debugging Workflow
1. Generate the FIT file.
2. Run validation with FitCSVTool.
3. If it fails, use the comparison tool to find differences.
4. Fix the encoder or message ordering.
5. Repeat until validation passes.

Official FIT documentation: https://developer.garmin.com/fit/
