"""FIT file binary encoder compatible with Garmin Fenix 7."""
import logging
import struct
from datetime import datetime
from .constants import *
from .utils import fit_timestamp

logger = logging.getLogger(__name__)

# Split type enum values (different from set_type!)
SPLIT_TYPE_ACTIVE_SET = 17
SPLIT_TYPE_REST_SET = 18


class FitEncoder:
    """Minimal FIT file encoder for strength training activities."""

    def __init__(self):
        self._messages = bytearray()
        # Changed: Track definitions by (global_num, field_signature) instead of just global_num
        self._definitions: dict[tuple[int, tuple], int] = {}
        self._local_count: int = 0

    def _next_local(self) -> int:
        n = self._local_count
        self._local_count += 1
        return n

    def _define(self, local: int, global_num: int,
                fields: list[tuple[int, int, int]]):
        """Write a definition message."""
        header = 0x40 | (local & 0x0F)
        data = struct.pack('<BBBHB', header, 0, 0, global_num, len(fields))
        for fdn, sz, bt in fields:
            data += struct.pack('<BBB', fdn, sz, bt)
        self._messages += data

    def _data(self, local: int, values: bytes):
        """Write a data message."""
        self._messages += struct.pack('<B', local & 0x0F) + values

    def _ensure_defined(self, global_num: int,
                        fields: list[tuple[int, int, int]]) -> int:
        """Define message type if not already defined.
        
        Fix 1.1: Now tracks field signatures to allow different layouts
        of the same message type (e.g., variable-length exercise names,
        rest vs. non-rest workout steps).
        """
        # Create a hashable signature from the fields
        field_signature = tuple(fields)
        cache_key = (global_num, field_signature)
        
        if cache_key not in self._definitions:
            local = self._next_local()
            self._define(local, global_num, fields)
            self._definitions[cache_key] = local
            logger.debug(f"Defined message {global_num} with local {local} ({len(fields)} fields)")
        
        return self._definitions[cache_key]

    def write_file_id(self, ts: datetime):
        """Message 0 - File ID"""
        fields = [
            (0, 1, 0), (1, 2, 132), (2, 2, 132),
            (3, 4, 134), (4, 4, 134),
        ]
        local = self._ensure_defined(0, fields)
        self._data(local, struct.pack(
            '<BHHII', FILE_TYPE_ACTIVITY, MANUFACTURER_GARMIN,
            GARMIN_PRODUCT_FENIX_7, DEVICE_SERIAL, fit_timestamp(ts)))

    def write_device_settings(self, ts: datetime):
        """Message 2 - Device Settings"""
        fields = [
            (0, 1, 2), (1, 4, 134), (2, 4, 134), (4, 1, 0),
            (5, 1, 1), (39, 4, 134),
        ]
        local = self._ensure_defined(2, fields)
        self._data(local, struct.pack(
            '<BIIBbI',
            0,  # active_time_zone
            0,  # utc_offset
            0,  # time_offset
            1,  # time_mode (24h)
            0,  # time_zone_offset
            fit_timestamp(ts),  # clock_time
        ))

    def write_user_profile(self):
        """Message 3 - User Profile"""
        name_bytes = b'User\x00'
        fields = [
            (0, len(name_bytes), 7), (1, 1, 0), (2, 1, 2), (3, 1, 2),
            (4, 2, 132), (5, 1, 0), (8, 1, 2), (11, 1, 2),
        ]
        local = self._ensure_defined(3, fields)
        self._data(local, struct.pack(
            f'<{len(name_bytes)}sBBBHBBB',
            name_bytes,
            0,    # gender (female)
            30,   # age
            175,  # height (1.75m)
            800,  # weight (80.0kg)
            0,    # language (english)
            60,   # resting_heart_rate
            190,  # default_max_heart_rate
        ))

    def write_zones_target(self):
        """Message 7 - Zones Target"""
        fields = [
            (1, 1, 2), (2, 1, 2), (3, 2, 132), (5, 1, 0), (7, 1, 0),
        ]
        local = self._ensure_defined(7, fields)
        self._data(local, struct.pack(
            '<BBHBB',
            190,  # max_heart_rate
            160,  # threshold_heart_rate
            250,  # functional_threshold_power
            1,    # hr_calc_type (percent_max_hr)
            1,    # pwr_calc_type (percent_ftp)
        ))

    def write_file_creator(self):
        """Message 49 - File Creator"""
        fields = [(0, 2, 132)]
        local = self._ensure_defined(49, fields)
        self._data(local, struct.pack('<H', GARMIN_FENIX_7_SW_VERSION))

    def write_activity(
        self,
        ts: datetime,
        timer_s: float,
        num_sessions: int = 1,
        local_timestamp: int | None = None,
    ):
        """Message 34 - Activity"""
        fields = [
            (253, 4, 134), (0, 4, 134), (1, 2, 132),
            (2, 1, 0), (3, 1, 0), (4, 1, 0), (5, 4, 134),
        ]
        local = self._ensure_defined(34, fields)
        local_ts = local_timestamp if local_timestamp is not None else fit_timestamp(ts)
        self._data(local, struct.pack(
            '<IIHBBBI', fit_timestamp(ts), int(timer_s * 1000),
            num_sessions, 0, EVENT_ACTIVITY, EVENT_TYPE_STOP,
            local_ts))

    def write_session(self, ts: datetime, start: datetime,
                      elapsed_s: float, timer_s: float, total_reps: int):
        """Message 18 - Session"""
        fields = [
            (253, 4, 134), (0, 1, 0), (1, 1, 0), (2, 4, 134),
            (5, 1, 0), (6, 1, 0), (7, 4, 134), (8, 4, 134),
            (9, 4, 134), (10, 4, 134), (11, 2, 132),
            (16, 1, 2), (17, 1, 2), (25, 2, 132), (26, 2, 132),
            (28, 1, 0), (48, 4, 134),
        ]
        local = self._ensure_defined(18, fields)
        self._data(local, struct.pack(
            '<IBBIBBIIIIHBBHHBI',
            fit_timestamp(ts), EVENT_SESSION, EVENT_TYPE_STOP,
            fit_timestamp(start), SPORT_TRAINING, SUB_SPORT_STRENGTH_TRAINING,
            int(elapsed_s * 1000), int(timer_s * 1000),
            0, total_reps, 0,
            64, 74, 0, 1, 0, 0
        ))

    def write_lap(self, ts: datetime, start_time: datetime,
                  elapsed_s: float, timer_s: float, total_reps: int = 0):
        """Message 19 - Lap"""
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
        local = self._ensure_defined(19, fields)
        self._data(local, struct.pack(
            '<IIIIBBBH',
            fit_timestamp(ts),
            fit_timestamp(start_time),
            int(elapsed_s * 1000),
            int(timer_s * 1000),
            0,  # manual trigger
            SPORT_TRAINING,
            SUB_SPORT_STRENGTH_TRAINING,
            total_reps
        ))

    def write_set(self, ts: datetime, duration_s: float, set_type: int,
                  category: int = 65534, exercise_name: int = 0,
                  reps: int = 0, weight_kg: float = 0.0,
                  start_time: datetime | None = None,
                  message_index: int = 0, wkt_step_index: int = 0):
        """Message 225 - Set
        
        Rest sets use a simpler field definition (no category/exercise/weight
        fields) because Garmin Connect rejects rest sets that include those.
        """
        st = fit_timestamp(start_time) if start_time else fit_timestamp(ts)

        if set_type == SET_TYPE_REST:
            # Rest sets: only timestamp, duration, set_type, start_time, message_index
            fields = [
                (254, 4, 134),  # timestamp
                (0, 4, 134),    # duration
                (5, 1, 0),      # set_type
                (6, 4, 134),    # start_time
                (11, 2, 132),   # message_index
            ]
            local = self._ensure_defined(225, fields)
            self._data(local, struct.pack(
                '<IIBIH',
                fit_timestamp(ts),
                int(duration_s * 1000),
                set_type,
                st,
                message_index,
            ))
        else:
            # Active sets: full fields
            fields = [
                (254, 4, 134),  # timestamp
                (0, 4, 134),    # duration
                (3, 2, 132),    # repetitions
                (4, 2, 132),    # weight
                (5, 1, 0),      # set_type
                (6, 4, 134),    # start_time
                (7, 2, 132),    # category
                (8, 2, 132),    # category_subtype
                (9, 1, 0),      # weight_display_unit
                (10, 2, 132),   # exercise_name (message_index)
                (11, 2, 132),   # wkt_step_index
            ]
            local = self._ensure_defined(225, fields)
            w = int(weight_kg * 16) if weight_kg > 0 else 0
            weight_unit = 1  # kilogram display
            self._data(local, struct.pack(
                '<IIHHBIHHBHH',
                fit_timestamp(ts), int(duration_s * 1000),
                reps, w, set_type, st, category, exercise_name,
                weight_unit, message_index, wkt_step_index,
            ))

    def write_split(self, ts: datetime, start_time: datetime, end_time: datetime,
                    elapsed_s: float, timer_s: float, split_type: int,
                    message_index: int, total_ascent: int = 0,
                    avg_hr: int = 64, max_hr: int = 74):
        """Message 312 - Split
        
        NOTE: split_type uses the FIT split_type enum, NOT set_type values!
        Callers pass SET_TYPE_ACTIVE (0) or SET_TYPE_REST (1) and we convert
        to the correct split_type enum: 17 = active_set, 18 = rest_set.
        """
        # Convert set_type values to split_type enum values
        if split_type == SET_TYPE_ACTIVE:
            fit_split_type = SPLIT_TYPE_ACTIVE_SET  # 17
        elif split_type == SET_TYPE_REST:
            fit_split_type = SPLIT_TYPE_REST_SET     # 18
        else:
            fit_split_type = split_type  # pass through if already correct

        fields = [
            (253, 4, 134),  # timestamp
            (0, 1, 0),      # split_type
            (1, 4, 134),    # total_elapsed_time
            (2, 4, 134),    # total_timer_time
            (3, 4, 134),    # total_distance
            (4, 4, 134),    # avg_speed
            (9, 4, 134),    # start_time
            (13, 2, 132),   # total_ascent
            (254, 2, 132),  # message_index
        ]
        local = self._ensure_defined(312, fields)
        self._data(local, struct.pack(
            '<IBIIIIIHH',
            fit_timestamp(ts), fit_split_type,
            int(elapsed_s * 1000), int(timer_s * 1000),
            0,  # total_distance
            0,  # avg_speed
            fit_timestamp(start_time),
            total_ascent, message_index,
        ))

    def write_split_summary(self, ts: datetime, total_timer_s: float,
                           num_splits: int, split_type: int,
                           avg_hr: int = 64, max_hr: int = 74,
                           message_index: int = 0):
        """Message 313 - Split Summary
        
        NOTE: Same split_type conversion as write_split.
        """
        # Convert set_type values to split_type enum values
        if split_type == SET_TYPE_ACTIVE:
            fit_split_type = SPLIT_TYPE_ACTIVE_SET  # 17
        elif split_type == SET_TYPE_REST:
            fit_split_type = SPLIT_TYPE_REST_SET     # 18
        else:
            fit_split_type = split_type

        fields = [
            (253, 4, 134),  # timestamp
            (0, 1, 0),      # split_type
            (3, 2, 132),    # num_splits
            (4, 4, 134),    # total_timer_time
            (5, 4, 134),    # total_distance
            (6, 4, 134),    # avg_speed
            (8, 2, 132),    # total_ascent
            (10, 1, 2),     # avg_heart_rate
            (11, 1, 2),     # max_heart_rate
            (13, 4, 134),   # total_calories
            (254, 2, 132),  # message_index
        ]
        local = self._ensure_defined(313, fields)
        self._data(local, struct.pack(
            '<IBHIIIHBBIH',
            fit_timestamp(ts), fit_split_type, num_splits,
            int(total_timer_s * 1000), 0, 0,  # distance, speed
            0,  # total_ascent
            avg_hr, max_hr, 0,  # calories
            message_index,
        ))

    def write_event(self, ts: datetime, event: int = EVENT_TIMER,
                    event_type: int = EVENT_TYPE_START):
        """Message 21 - Event"""
        fields = [(253, 4, 134), (0, 1, 0), (1, 1, 0),
                  (2, 1, 0), (3, 1, 0), (4, 1, 0)]
        local = self._ensure_defined(21, fields)
        self._data(local, struct.pack(
            '<IBBBBB', fit_timestamp(ts), event, event_type, 0, 0, 0))

    def write_device_info(self, ts: datetime, device_index: int = 0):
        """Message 23 - Device Info"""
        fields = [
            (253, 4, 134), (0, 4, 134), (2, 2, 132),
            (4, 2, 132), (5, 2, 132), (3, 1, 2), (25, 1, 0),
        ]
        local = self._ensure_defined(23, fields)
        self._data(local, struct.pack(
            '<IIHHHBB', fit_timestamp(ts),
            DEVICE_SERIAL if device_index == 0 else 0,
            MANUFACTURER_GARMIN, GARMIN_PRODUCT_FENIX_7,
            GARMIN_FENIX_7_SW_VERSION, device_index, 1
        ))

    def write_sport(self, name: str = "Strength"):
        """Message 12 - Sport"""
        name_bytes = name.encode('utf-8') + b'\x00'
        fields = [(0, 1, 0), (1, 1, 0), (3, len(name_bytes), 7)]
        local = self._ensure_defined(12, fields)
        self._data(local, struct.pack(
            f'<BB{len(name_bytes)}s',
            SPORT_TRAINING, SUB_SPORT_STRENGTH_TRAINING, name_bytes))

    def write_workout(self, name: str, num_steps: int):
        """Message 26 - Workout"""
        name_bytes = name.encode('utf-8') + b'\x00'
        fields = [
            (4, 1, 0), (5, 4, 134), (6, 2, 132),
            (8, len(name_bytes), 7), (11, 1, 0),
        ]
        local = self._ensure_defined(26, fields)
        self._data(local, struct.pack(
            f'<BIH{len(name_bytes)}sB',
            SPORT_TRAINING, 0, num_steps,
            name_bytes, SUB_SPORT_STRENGTH_TRAINING
        ))

    def write_workout_step(self, message_index: int, exercise_category: int,
                          exercise_name: int, reps: int, is_rest: bool = False):
        """Message 27 - Workout Step"""
        intensity = 1 if is_rest else 0
        category = 0 if is_rest else exercise_category
        subtype = 0 if is_rest else exercise_name
        fields = [
            (254, 2, 132), (1, 1, 0), (2, 4, 134), (3, 1, 0),
            (4, 4, 134), (7, 1, 0), (10, 2, 132), (11, 2, 132),
        ]
        local = self._ensure_defined(27, fields)
        self._data(local, struct.pack(
            '<HBIBIBHH',
            message_index, 0, 0, 0, 0, intensity, category, subtype
        ))

    def write_exercise_title(self, message_index: int, name: str,
                            exercise_category: int, exercise_name: int):
        """Message 264 - Exercise Title
        
        Each exercise name gets its own definition thanks to the
        fixed _ensure_defined caching (variable-length name field).
        """
        name_bytes = name.encode('utf-8') + b'\x00'
        fields = [
            (0, 2, 132), (1, 2, 132), (2, len(name_bytes), 7),
            (254, 2, 132),
        ]
        local = self._ensure_defined(264, fields)
        self._data(local, struct.pack(
            f'<HH{len(name_bytes)}sH',
            exercise_category, exercise_name, name_bytes, message_index
        ))

    def write_record(self, ts: datetime, heart_rate: int = 64):
        """Message 20 - Record"""
        fields = [(253, 4, 134), (5, 4, 136), (3, 1, 2)]
        local = self._ensure_defined(20, fields)
        self._data(local, struct.pack('<IIB', fit_timestamp(ts), 0, heart_rate))

    def build(self) -> bytes:
        """Build final FIT file with header and CRC."""
        data = bytes(self._messages)
        header = struct.pack('<BBHI4s', 14, 0x20, 2188, len(data), b'.FIT')
        header += struct.pack('<H', self._crc16(header))
        full = header + data
        result = full + struct.pack('<H', self._crc16(full))
        logger.debug(f"Built FIT file: {len(result)} bytes (header=14, data={len(data)}, crc=2)")
        return result

    @staticmethod
    def _crc16(data: bytes) -> int:
        """Calculate FIT CRC-16."""
        tbl = [
            0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
            0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400,
        ]
        crc = 0
        for b in data:
            tmp = tbl[crc & 0xF]
            crc = (crc >> 4) & 0x0FFF
            crc = crc ^ tmp ^ tbl[b & 0xF]
            tmp = tbl[crc & 0xF]
            crc = (crc >> 4) & 0x0FFF
            crc = crc ^ tmp ^ tbl[(b >> 4) & 0xF]
        return crc