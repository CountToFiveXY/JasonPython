from temporalio import activity


@activity.defn
async def print_hello() -> str:
    """Print a message from the worker process and return it as the result."""
    message = "Hello there"
    print(message, flush=True)
    return message


@activity.defn
async def compose_greeting(name: str) -> str:
    """Example side effect executed and retried by a Temporal worker."""
    return f"Hello, {name}!"
