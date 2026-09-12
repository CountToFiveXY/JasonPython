from fastapi import APIRouter, Depends, status

from src.dependencies import get_order_service
from src.schemas import OrderRequest, OrderResponse
from src.services import OrderService


router = APIRouter(prefix="/v1/order", tags=["Orders"])


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    request: OrderRequest,
    order_service: OrderService = Depends(get_order_service),
) -> OrderResponse:
    order = await order_service.create(request.user_id)
    return OrderResponse(**order.model_dump(), workflow_id=order.id)
