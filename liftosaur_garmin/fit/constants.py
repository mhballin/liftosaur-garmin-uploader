"""FIT protocol constants for Garmin devices."""
from datetime import datetime, timezone

FIT_EPOCH = datetime(1989, 12, 31, 0, 0, 0, tzinfo=timezone.utc)

# Garmin Device Info
MANUFACTURER_GARMIN = 1
GARMIN_PRODUCT_FENIX_7 = 3906
GARMIN_FENIX_7_SW_VERSION = 2511  # firmware 25.11
DEVICE_SERIAL = 0

# Sport Types
SPORT_TRAINING = 10
SUB_SPORT_STRENGTH_TRAINING = 20

# Set Types
SET_TYPE_REST = 0
SET_TYPE_ACTIVE = 1

# Split Types (FIT profile split_type enum)
SPLIT_TYPE_ACTIVE = 3
SPLIT_TYPE_REST = 4

# Event Types
EVENT_TIMER = 0
EVENT_TYPE_START = 0
EVENT_TYPE_STOP = 1
EVENT_TYPE_STOP_ALL = 9
EVENT_SESSION = 8
EVENT_ACTIVITY = 26

# File Types
FILE_TYPE_ACTIVITY = 4
