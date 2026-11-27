"""Temporal connection settings shared by clients and workers."""

import os

TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "127.0.0.1:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "default")
TEMPORAL_ORDER_NAMESPACE = os.getenv("TEMPORAL_ORDER_NAMESPACE", "order")
TEMPORAL_PAYOUT_NAMESPACE = os.getenv("TEMPORAL_PAYOUT_NAMESPACE", "payout")
PAYOUT_NEXUS = os.getenv("PAYOUT_NEXUS", "payout-nexus")
TEMPORAL_TASK_QUEUE = os.getenv("TEMPORAL_TASK_QUEUE", "utility-api")
TEMPORAL_ORDER_TASK_QUEUE = os.getenv("TEMPORAL_ORDER_TASK_QUEUE", "order-queue")
TEMPORAL_PAYOUT_TASK_QUEUE = os.getenv("TEMPORAL_PAYOUT_TASK_QUEUE", "payout-queue")
