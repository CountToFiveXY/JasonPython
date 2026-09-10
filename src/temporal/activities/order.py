from temporalio import activity


@activity.defn
async def complete_order(order_id: str) -> str:
    """Run the backend work that follows a successful order signal."""
    result = f"Order {order_id} completed"
    print(result, flush=True)
    return result
