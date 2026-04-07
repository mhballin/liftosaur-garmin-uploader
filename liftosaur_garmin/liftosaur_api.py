"""Liftosaur API client and workout history normalization helpers."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib import error, parse, request

from .exercise.duration import estimate_time_under_tension
from .exercise.mapping import lookup_exercise
from .fit.utils import parse_iso

logger = logging.getLogger(__name__)

LIFTOSAUR_API_BASE_URL = "https://www.liftosaur.com/api/v1"
DEFAULT_HISTORY_PAGE_SIZE = 200
DEFAULT_REST_SECONDS = 90
DEFAULT_WARMUP_REST_SECONDS = 45

_BODYWEIGHT_PATTERN = re.compile(r"^(bodyweight|bw)$", re.IGNORECASE)
_SET_PATTERN = re.compile(
    r"^(?P<count>\d+)x(?P<reps>\d+(?:\.\d+)?)"
    r"(?:\s+(?:(?P<weight>-?\d+(?:\.\d+)?)\s*(?P<unit>kg|lb|lbs)|(?P<bodyweight>bodyweight|bw)))?$",
    re.IGNORECASE,
)


class LiftosaurApiError(RuntimeError):
    """Raised when Liftosaur API access or normalization fails."""


def get_configured_api_key(config: dict, override: str | None = None) -> str | None:
    """Return the Liftosaur API key from CLI override or profile config."""
    candidate = (override or config.get("liftosaur_api_key") or "").strip()
    return candidate or None


def fetch_history_rows(
    api_key: str,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
    base_url: str = LIFTOSAUR_API_BASE_URL,
) -> list[dict]:
    """Fetch Liftosaur history records and normalize them into workout rows."""
    records = fetch_history_records(
        api_key=api_key,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        base_url=base_url,
    )
    rows: list[dict] = []
    skipped = 0
    for record in records:
        try:
            rows.extend(parse_history_record(record))
        except LiftosaurApiError as exc:
            record_id = record.get("id", "unknown")
            logger.warning("Skipping Liftosaur record %s: %s", record_id, exc)
            skipped += 1
    logger.info(
        "Liftosaur API returned %s record(s); normalized %s row(s)%s",
        len(records),
        len(rows),
        f" ({skipped} skipped)" if skipped else "",
    )
    return rows


def fetch_history_records(
    api_key: str,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int | None = None,
    base_url: str = LIFTOSAUR_API_BASE_URL,
) -> list[dict[str, Any]]:
    """Fetch raw Liftosaur history records, following pagination."""
    cursor: str | int | None = None
    remaining = limit
    records: list[dict[str, Any]] = []

    while True:
        params: dict[str, str] = {}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        page_size = DEFAULT_HISTORY_PAGE_SIZE
        if remaining is not None:
            page_size = min(page_size, max(remaining, 1))
        params["limit"] = str(page_size)
        if cursor is not None:
            params["cursor"] = str(cursor)

        url = f"{base_url}/history?{parse.urlencode(params)}"
        payload = _request_json("GET", url, api_key)
        data = payload.get("data")
        if not isinstance(data, dict):
            raise LiftosaurApiError("Liftosaur API response did not include a data object.")

        page_records = data.get("records")
        if not isinstance(page_records, list):
            raise LiftosaurApiError("Liftosaur API response did not include a records array.")

        for record in page_records:
            if isinstance(record, dict):
                records.append(record)

        if remaining is not None:
            remaining -= len(page_records)
            if remaining <= 0:
                break

        has_more = bool(data.get("hasMore"))
        next_cursor = data.get("nextCursor")
        if not has_more or next_cursor in {None, ""}:
            break
        cursor = next_cursor

    return records


def parse_history_record(record: dict[str, Any]) -> list[dict]:
    """Convert one Liftosaur history record into CSV-like set rows."""
    text = record.get("text")
    if not isinstance(text, str) or not text.strip():
        raise LiftosaurApiError("Record is missing workout text.")

    workout_start, header, exercise_block = _split_history_text(text)
    day_name = _extract_quoted_field(header, "dayName") or "Workout"
    duration_seconds = _extract_duration_seconds(header)
    record_id = record.get("id")

    parsed_sets: list[dict[str, Any]] = []
    exercise_lines = [line.strip() for line in exercise_block.splitlines() if line.strip()]
    if not exercise_lines:
        raise LiftosaurApiError("Workout text contains no exercise lines.")

    for line in exercise_lines:
        parsed_sets.extend(_parse_exercise_line(line))

    if not parsed_sets:
        raise LiftosaurApiError("Workout text contained no parsable sets.")

    completed_times = _estimate_completed_times(
        workout_start=workout_start,
        parsed_sets=parsed_sets,
        duration_seconds=duration_seconds,
    )
    workout_datetime = _format_iso(workout_start)

    rows: list[dict] = []
    for parsed_set, completed_time in zip(parsed_sets, completed_times):
        rows.append(
            {
                "Workout DateTime": workout_datetime,
                "Exercise": parsed_set["exercise"],
                "Is Warmup Set?": "1" if parsed_set["is_warmup"] else "0",
                "Completed Reps": str(parsed_set["reps"]),
                "Completed Weight Value": _format_number(parsed_set["weight_value"]),
                "Completed Weight Unit": parsed_set["weight_unit"],
                "Completed Reps Time": _format_iso(completed_time),
                "Day Name": day_name,
                "Is AMRAP?": "0",
                "Target Muscles": "",
                "__source": "liftosaur_api",
                "__source_id": str(record_id) if record_id is not None else "",
            }
        )

    return rows


def _request_json(method: str, url: str, api_key: str) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "User-Agent": "liftosaur-garmin-uploader",
    }
    req = request.Request(url, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise LiftosaurApiError(_format_http_error(exc.code, body)) from exc
    except error.URLError as exc:
        reason = getattr(exc, "reason", exc)
        raise LiftosaurApiError(f"Liftosaur API request failed: {reason}") from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LiftosaurApiError("Liftosaur API returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise LiftosaurApiError("Liftosaur API returned an unexpected response shape.")
    return payload


def _format_http_error(status_code: int, body: str) -> str:
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, dict):
        error_obj = payload.get("error")
        if isinstance(error_obj, dict):
            code = error_obj.get("code") or "api_error"
            message = error_obj.get("message") or "Liftosaur API request failed."
            return f"Liftosaur API error ({status_code}, {code}): {message}"

    if status_code == 401:
        return "Liftosaur API rejected the request: missing or invalid API key."
    if status_code == 403:
        return "Liftosaur API rejected the request: an active Liftosaur subscription is required."
    return f"Liftosaur API request failed with status {status_code}."


def _split_history_text(text: str) -> tuple[datetime, str, str]:
    match = re.search(r"\s*/\s*exercises:\s*\{", text, re.IGNORECASE)
    if match is None:
        raise LiftosaurApiError("Workout text is missing the exercises block.")

    header = text[:match.start()].strip()
    body = text[match.end():].strip()
    if not body.endswith("}"):
        raise LiftosaurApiError("Workout text has an unterminated exercises block.")
    body = body[:-1].strip()

    if not header:
        raise LiftosaurApiError("Workout text is missing the workout header.")

    timestamp_text = header.split("/", 1)[0].strip()
    try:
        workout_start = parse_iso(timestamp_text)
    except ValueError as exc:
        raise LiftosaurApiError(f"Invalid workout timestamp: {timestamp_text}") from exc

    return workout_start, header, body


def _extract_quoted_field(header: str, field_name: str) -> str | None:
    match = re.search(rf"(?:^|/)\s*{re.escape(field_name)}:\s*\"([^\"]*)\"", header)
    if match is None:
        return None
    return match.group(1).strip() or None


def _extract_duration_seconds(header: str) -> int | None:
    match = re.search(r"(?:^|/)\s*duration:\s*(\d+)s", header)
    if match is None:
        return None
    return int(match.group(1))


def _parse_exercise_line(line: str) -> list[dict[str, Any]]:
    parts = [part.strip() for part in line.split("/") if part.strip()]
    if len(parts) < 2:
        raise LiftosaurApiError(f"Could not parse exercise line: {line}")

    exercise_name = _normalize_exercise_name(parts[0])
    working_specs: list[tuple[int, int, float, str]] = []
    warmup_specs: list[tuple[int, int, float, str]] = []
    rest_seconds = DEFAULT_REST_SECONDS

    for part in parts[1:]:
        lower = part.lower()
        if lower.startswith("warmup:"):
            warmup_specs = _parse_set_group(part.split(":", 1)[1].strip())
            continue
        if lower.startswith("target:"):
            rest_seconds = _extract_rest_seconds(part) or rest_seconds
            continue
        if not working_specs:
            working_specs = _parse_set_group(part)

    if not working_specs and not warmup_specs:
        raise LiftosaurApiError(f"Exercise line contained no set specs: {line}")

    parsed_sets: list[dict[str, Any]] = []
    warmup_rest = min(DEFAULT_WARMUP_REST_SECONDS, rest_seconds)
    for reps, weight_value, weight_unit, is_warmup in _expand_specs(warmup_specs, True):
        parsed_sets.append(
            {
                "exercise": exercise_name,
                "reps": reps,
                "weight_value": weight_value,
                "weight_unit": weight_unit,
                "is_warmup": is_warmup,
                "rest_after_seconds": warmup_rest,
            }
        )
    for reps, weight_value, weight_unit, is_warmup in _expand_specs(working_specs, False):
        parsed_sets.append(
            {
                "exercise": exercise_name,
                "reps": reps,
                "weight_value": weight_value,
                "weight_unit": weight_unit,
                "is_warmup": is_warmup,
                "rest_after_seconds": rest_seconds,
            }
        )
    return parsed_sets


def _normalize_exercise_name(raw_name: str) -> str:
    name = raw_name.strip()
    if "," in name:
        primary, _, detail = name.partition(",")
        if primary.strip() and detail.strip().lower() in {
            "barbell",
            "dumbbell",
            "machine",
            "cable",
            "smith machine",
            "bodyweight",
        }:
            return primary.strip()
    return name


def _parse_set_group(group_text: str) -> list[tuple[int, int, float, str]]:
    specs: list[tuple[int, int, float, str]] = []
    for item in group_text.split(","):
        spec_text = item.strip()
        if not spec_text:
            continue
        match = _SET_PATTERN.match(spec_text)
        if match is None:
            raise LiftosaurApiError(f"Unsupported set spec: {spec_text}")
        count = int(match.group("count"))
        reps = int(float(match.group("reps")))
        bodyweight = match.group("bodyweight")
        if bodyweight and _BODYWEIGHT_PATTERN.match(bodyweight):
            weight_value = 0.0
            weight_unit = "lb"
        else:
            weight_value = float(match.group("weight") or 0)
            raw_unit = (match.group("unit") or "lb").lower()
            weight_unit = "kg" if raw_unit == "kg" else "lb"
        specs.append((count, reps, weight_value, weight_unit))
    return specs


def _expand_specs(
    specs: list[tuple[int, int, float, str]],
    is_warmup: bool,
) -> list[tuple[int, float, str, bool]]:
    expanded: list[tuple[int, float, str, bool]] = []
    for count, reps, weight_value, weight_unit in specs:
        for _ in range(count):
            expanded.append((reps, weight_value, weight_unit, is_warmup))
    return expanded


def _extract_rest_seconds(target_text: str) -> int | None:
    match = re.search(r"(\d+)s\b", target_text)
    if match is None:
        return None
    return int(match.group(1))


def _estimate_completed_times(
    workout_start: datetime,
    parsed_sets: list[dict[str, Any]],
    duration_seconds: int | None,
) -> list[datetime]:
    if not parsed_sets:
        return []

    active_durations: list[float] = []
    base_rest_durations: list[float] = []
    for index, parsed_set in enumerate(parsed_sets):
        category_id, _ = lookup_exercise(parsed_set["exercise"])
        active_duration = estimate_time_under_tension(parsed_set["reps"], category_id)
        active_durations.append(active_duration)
        if index < len(parsed_sets) - 1:
            base_rest_durations.append(float(parsed_set["rest_after_seconds"]))

    estimated_total = sum(active_durations) + sum(base_rest_durations)
    rest_scale = 1.0
    if duration_seconds and sum(base_rest_durations) > 0 and duration_seconds > estimated_total:
        extra = duration_seconds - sum(active_durations)
        rest_scale = max(extra / sum(base_rest_durations), 1.0)

    completed_times: list[datetime] = []
    cursor = workout_start
    for index, active_duration in enumerate(active_durations):
        cursor = cursor + timedelta(seconds=active_duration)
        completed_times.append(cursor)
        if index < len(base_rest_durations):
            cursor = cursor + timedelta(seconds=base_rest_durations[index] * rest_scale)

    return completed_times


def _format_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")