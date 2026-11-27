from temporalio import activity


@activity.defn
async def compose_payout_result(name: str) -> str:
    """Example side effect executed and retried by a Temporal worker."""
    return f"Hello, {name}!"
