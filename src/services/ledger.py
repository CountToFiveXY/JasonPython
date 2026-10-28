"""Ledger use cases, keeping Firestore details out of HTTP handlers."""

from src.repositories.ledger import LedgerRepository
from src.schemas.ledger import ExpenseCreate, ExpenseList, ExpenseResponse


class LedgerService:
    def __init__(self, repository: LedgerRepository):
        self.repository = repository

    def list(self) -> ExpenseList:
        return ExpenseList(expenses=self.repository.list())

    def create(self, expense: ExpenseCreate) -> ExpenseResponse:
        return ExpenseResponse(**self.repository.create(float(expense.amount), expense.description))

    def rename(self, identifier: str, description: str) -> ExpenseResponse:
        return ExpenseResponse(**self.repository.rename(identifier, description))

    def delete(self, identifier: str) -> None:
        self.repository.delete(identifier)
