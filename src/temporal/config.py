"""Temporal connection settings shared by clients and workers."""

import os

TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "127.0.0.1:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
TEMPORAL_ORDER_NAMESPACE = os.getenv("TEMPORAL_ORDER_NAMESPACE", "order")
TEMPORAL_PAYOUT_NAMESPACE = os.getenv("TEMPORAL_PAYOUT_NAMESPACE", "payout")
TEMPORAL_GREETING_NEXUS_ENDPOINT = os.getenv("TEMPORAL_GREETING_NEXUS_ENDPOINT", "payout-greeting")
