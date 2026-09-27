import os


KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "127.0.0.1:9092",
)
KAFKA_ORDER_TOPIC = os.getenv("KAFKA_ORDER_TOPIC", "order-status")
KAFKA_SCHEDULER_TOPIC = os.getenv("KAFKA_SCHEDULER_TOPIC", "scheduler-control")
KAFKA_ORDER_CONSUMER_GROUP = os.getenv(
    "KAFKA_ORDER_CONSUMER_GROUP",
    "utility-api-order-worker",
)
KAFKA_SCHEDULER_CONSUMER_GROUP = os.getenv(
    "KAFKA_SCHEDULER_CONSUMER_GROUP",
    "utility-api-scheduler",
)
