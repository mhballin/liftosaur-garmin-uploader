"""FIT file binary encoder compatible with Garmin Fenix 7."""
import struct
from datetime import datetime
from .constants import *
from .utils import fit_timestamp


class FitEncoder:
    """Minimal FIT file encoder for strength training activities."""

    def __init__(self):
        self._messages = bytearray()
        self._definitions: dict[int, int] = {}
        self._local_count = 0

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
        self._definitions[global_num] = local

    def _data(self, local: int, values: bytes):
        """Write a data message."""
        self._messages += struct.pack('<B', local & 0x0F) + values

    def _ensure_defined(self, global_num: int,
                        fields: list[tuple[int, int, int]]) -> int:
        """Define message type if not already defined."""
        if global_num not in self._definitions:
            local = self._next_local()
            self._define(local, global_num, fields)
        return self._definitions[global_num]

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

    def write_file_creator(self):
        """Message 49 - File Creator"""
        fields = [(0, 2, 132)]
        local = self._ensure_defined(49, fields)
        self._data(local, struct.pack('<H', GARMIN_FENIX_7_SW_VERSION))

    def write_activity(self, ts: datetime, timer_s: float, num_sessions: int = 1):
        """Message 34 - Activity"""
        fields = [
            (253, 4, 134), (0, 4, 134), (1, 2, 132),
            (2, 1, 0), (3, 1, 0), (4, 1, 0), (5, 4, 134),
        ]
        local = self._ensure_defined(34, fields)
        self._data(local, struct.pack(
            '<IIHBBBBI', fit_timestamp(ts), int(timer_s * 1000),
            num_sessions, 0, EVENT_TIMER, EVENT_TYPE_STOP_ALL,
            fit_timestamp(ts)))

    def write_session(self, ts: datetime, start: datetime,
                      elapsed_s: float, timer_s: float, total_reps: int):
        """Message 18 - Session"""
        fields = [
            (253, 4, 134), (2, 4, 134), (7, 4, 134), (8, 4, 134),
            (9, 4, 136), (48, 2, 132), (5, 1, 0), (6, 1, 0),
            (0, 1, 0), (1, 1, 0), (11, 2, 132), (16, 1, 2),
            (17, 1, 2), (25, 1, 0), (26, 1, 0), (28, 1, 0),
        ]
        local = self._ensure_defined(18, fields)
        self._data(local, struct.pack(
            '<IIIIIHBBBBHBBBBB',
            fit_timestamp(ts), fit_timestamp(start),
            int(elapsed_s * 1000), int(timer_s * 1000),
            0, total_reps,
            SPORT_TRAINING, SUB_SPORT_STRENGTH_TRAINING,
            EVENT_TIMER, EVENT_TYPE_STOP_ALL,
            3, 64, 74, 0, 16, 0
        ))

    def write_set(self, ts: datetime, duration_s: float, set_type: int,
                  category: int = 65534, exercise_name: int = 0,
                  reps: int = 0, weight_kg: float = 0.0,
                  start_time: datetime | None = None,
                  message_index: int = 0, wkt_step_index: int = 0,
                  set_counter: int = 0):
        """Message 225 - Set"""
        fields = [
            (253, 4, 134), (0, 4, 134), (3, 2, 132), (4, 2, 132),
            (5, 1, 0), (6, 4, 134), (7, 6, 132), (8, 6, 132),
            (10, 2, 132), (254, 2, 132), (9, 2, 132), (14, 2, 132),
            (2, 6, 132),
        ]
        local = self._ensure_defined(225, fields)
        st = fit_timestamp(start_time) if start_time else fit_timestamp(ts)
        w = int(weight_kg * 16) if weight_kg > 0 else 0
        
        self._data(local, struct.pack(
            '<IIHHBI HHHHHH HHHH',
            fit_timestamp(ts), int(duration_s * 1000),
            reps, w, set_type, st,
            category, category, category,
            exercise_name, exercise_name, exercise_name,
            1, message_index, wkt_step_index, set_counter,
            0xFFFF, 0xFFFF, 0xFFFF
        ))

    def write_split(self, ts: datetime, start_time: datetime, end_time: datetime,
                    elapsed_s: float, timer_s: float, split_type: int,
                    message_index: int, avg_hr: int = 64, max_hr: int = 74):
        """Message 312 - Split"""
        fields = [
            (253, 4, 134), (0, 4, 134), (1, 4, 134), (2, 4, 136),
            (3, 4, 136), (9, 4, 134), (10, 4, 134), (11, 2, 132),
            (254, 2, 132), (13, 1, 0), (14, 1, 0), (15, 1, 0),
            (16, 1, 2), (17, 1, 2),
        ]
        local = self._ensure_defined(312, fields)
        self._data(local, struct.pack(
            '<IIIIIIIHHBBBBB',
            fit_timestamp(ts), int(elapsed_s * 1000), int(timer_s * 1000),
            0, 0, fit_timestamp(start_time), fit_timestamp(end_time),
            1 if split_type == 0 else 0, message_index, split_type,
            SPORT_TRAINING, SUB_SPORT_STRENGTH_TRAINING, avg_hr, max_hr
        ))

    def write_split_summary(self, ts: datetime, total_timer_s: float,
                           num_splits: int, split_type: int,
                           avg_hr: int = 64, max_hr: int = 74,
                           message_index: int = 0):
        """Message 313 - Split Summary"""
        fields = [
            (253, 4, 134), (0, 4, 134), (2, 4, 136), (3, 4, 136),
            (11, 2, 132), (254, 2, 132), (5, 2, 132), (13, 1, 0),
            (16, 1, 2), (17, 1, 2),
        ]
        local = self._ensure_defined(313, fields)
        self._data(local, struct.pack(
            '<IIIIHHHBBB',
            fit_timestamp(ts), int(total_timer_s * 1000),
            0, 0, 2, message_index, num_splits, split_type, avg_hr, max_hr
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
            (4, len(name_bytes), 7), (6, 2, 132),
            (5, 1, 0), (11, 1, 0), (8, 4, 134),
        ]
        local = self._ensure_defined(26, fields)
        self._data(local, struct.pack(
            f'<{len(name_bytes)}sHBBI',
            name_bytes, num_steps,
            SPORT_TRAINING, SUB_SPORT_STRENGTH_TRAINING, 32
        ))

    def write_workout_step(self, message_index: int, exercise_category: int,
                          exercise_name: int, reps: int, is_rest: bool = False):
        """Message 27 - Workout Step"""
        if is_rest:
            fields = [(254, 2, 132), (0, 1, 0), (2, 1, 0), (4, 1, 0)]
            local = self._ensure_defined(27, fields)
            self._data(local, struct.pack('<HBBB', message_index, 0, 0, 1))
        else:
            fields = [
                (254, 2, 132), (1, 4, 134), (3, 4, 134), (0, 1, 0),
                (2, 1, 0), (4, 1, 0), (5, 2, 132), (6, 2, 132),
            ]
            local = self._ensure_defined(27, fields)
            self._data(local, struct.pack(
                '<HIIBBBHH', message_index, reps, 0,
                6, 0, 0, exercise_category, exercise_name
            ))

    def write_exercise_title(self, message_index: int, name: str,
                            exercise_category: int, exercise_name: int):
        """Message 264 - Exercise Title"""
        name_bytes = name.encode('utf-8') + b'\x00'
        fields = [
            (254, 2, 132), (0, len(name_bytes), 7),
            (1, 2, 132), (2, 2, 132),
        ]
        local = self._ensure_defined(264, fields)
        self._data(local, struct.pack(
            f'<H{len(name_bytes)}sHH',
            message_index, name_bytes, exercise_category, exercise_name
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
        return full + struct.pack('<H', self._crc16(full))

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