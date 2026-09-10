from temporalio import activity


@activity.defn
async def print_hello() -> str:
    """Print a message from the worker process and return it as the result."""
    message = "Hello there"
    print(message, flush=True)
    return message
