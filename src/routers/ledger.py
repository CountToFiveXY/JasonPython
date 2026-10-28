"""Ledger API backed by the shared Firestore client."""

from fastapi import APIRouter, Depends, HTTPException, Response
from google.api_core.exceptions import GoogleAPICallError

from src.dependencies import get_ledger_service
from src.repositories.ledger import ExpenseNotFoundError
from src.schemas.ledger import ExpenseCreate, ExpenseList, ExpenseResponse, ExpenseUpdate
from src.services.ledger import LedgerService

router = APIRouter(prefix="/v1/ledger/expenses", tags=["Ledger"])


def translate_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ExpenseNotFoundError):
        return HTTPException(404, str(exc))
    if isinstance(exc, GoogleAPICallError):
        return HTTPException(503, "Firestore is unavailable. Please refresh before retrying a save.")
    return HTTPException(422, "Invalid expense data or ID. Expected MM-DD-YYYY:counter and a positive amount with at most two decimal places.")


@router.get("", response_model=ExpenseList)
def list_expenses(service: LedgerService = Depends(get_ledger_service)):
    try:
        return service.list()
    except (ValueError, GoogleAPICallError) as exc:
        raise translate_error(exc) from exc


@router.post("", response_model=ExpenseResponse, status_code=201)
def create_expense(expense: ExpenseCreate, service: LedgerService = Depends(get_ledger_service)):
    try:
        return service.create(expense)
    except (ValueError, GoogleAPICallError) as exc:
        raise translate_error(exc) from exc


@router.patch("/{identifier}", response_model=ExpenseResponse)
def rename_expense(identifier: str, expense: ExpenseUpdate, service: LedgerService = Depends(get_ledger_service)):
    try:
        return service.rename(identifier, expense.description)
    except (ExpenseNotFoundError, ValueError, GoogleAPICallError) as exc:
        raise translate_error(exc) from exc


@router.delete("/{identifier}", status_code=204)
def delete_expense(identifier: str, service: LedgerService = Depends(get_ledger_service)):
    try:
        service.delete(identifier)
        return Response(status_code=204)
    except (ValueError, GoogleAPICallError) as exc:
        raise translate_error(exc) from exc
