"""FIT protocol constants for Garmin devices."""
from datetime import datetime, timezone

FIT_EPOCH = datetime(1989, 12, 31, 0, 0, 0, tzinfo=timezone.utc)

# Garmin Device Info
MANUFACTURER_GARMIN = 1
GARMIN_PRODUCT_FENIX_7 = 3906
GARMIN_FENIX_7_SW_VERSION = 2511  # firmware 25.11
DEVICE_SERIAL = 3409674450

# Sport Types
SPORT_TRAINING = 10
SUB_SPORT_STRENGTH_TRAINING = 20

# Set Types
SET_TYPE_ACTIVE = 0
SET_TYPE_REST = 1

# Event Types
EVENT_TIMER = 0
EVENT_TYPE_START = 0
EVENT_TYPE_STOP_ALL = 9

# File Types
FILE_TYPE_ACTIVITY = 4