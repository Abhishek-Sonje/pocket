from typing import Annotated, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Id = Annotated[int, Field(strict=True, gt=0, le=2**63 - 1)]
Money = Annotated[int, Field(strict=True, gt=0, le=2**63 - 1)]
Name = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=100)
]
Description = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=500)
]


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NamedRequest(Request):
    name: Name


class MemberRequest(Request):
    user_id: Id


class ExpenseRequest(Request):
    paid_by: Id
    recorded_by: Id
    amount_paise: Money
    description: Description
    participant_ids: list[Id] | None = None
    request_id: UUID | None = None

    @model_validator(mode="after")
    def participants(self):
        if "participant_ids" in self.model_fields_set:
            if not self.participant_ids or len(self.participant_ids) != len(
                set(self.participant_ids)
            ):
                raise ValueError(
                    "Select at least one participant, without duplicates; omit the field for all members."
                )
        return self


class SettlementRequest(Request):
    from_user: Id
    to_user: Id
    recorded_by: Id
    amount_paise: Money
    request_id: UUID | None = None

    @model_validator(mode="after")
    def different_parties(self):
        if self.from_user == self.to_user:
            raise ValueError("Sender and recipient must be different members.")
        return self


class Named(BaseModel):
    id: int
    name: str


class Membership(BaseModel):
    group_id: int
    user_id: int
    joined_at: str


class Member(Membership):
    name: str


class Share(BaseModel):
    user_id: int
    share_paise: int


class Financial(BaseModel):
    id: int
    group_id: int
    recorded_by: int
    amount_paise: int
    created_at: str


class Expense(Financial):
    paid_by: int
    description: str
    shares: list[Share]


class Settlement(Financial):
    from_user: int
    to_user: int


class Payment(BaseModel):
    from_user: int
    to_user: int
    amount_paise: int


class MemberBalance(BaseModel):
    user_id: int
    name: str
    paid_paise: int
    share_paise: int
    repayments_sent_paise: int
    repayments_received_paise: int
    net_balance_paise: int


class Balances(BaseModel):
    group_id: int
    total_expenses_paise: int
    total_outstanding_paise: int
    members: list[MemberBalance]
    suggested_payments: list[Payment]


class Suggestions(BaseModel):
    group_id: int
    suggestions: list[Payment]


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorDetail
