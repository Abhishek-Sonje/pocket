from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, Response

from app import models as m, schemas as s, services

router = APIRouter()
GroupId = Annotated[int, Path(gt=0, le=2**63 - 1)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


def engine(request: Request):
    return request.app.state.engine


Database = Annotated[object, Depends(engine)]


@router.post("/users", response_model=s.Named, status_code=201)
def create_user(body: s.NamedRequest, db: Database):
    return services.create_named(db, m.users, body.name)


@router.get("/users", response_model=list[s.Named])
def users(db: Database):
    return services.list_named(db, m.users)


@router.post("/groups", response_model=s.Named, status_code=201)
def create_group(body: s.NamedRequest, db: Database):
    return services.create_named(db, m.groups, body.name)


@router.get("/groups", response_model=list[s.Named])
def groups(db: Database):
    return services.list_named(db, m.groups)


@router.post("/groups/{group_id}/members", response_model=s.Membership, status_code=201)
def add_member(group_id: GroupId, body: s.MemberRequest, db: Database):
    return services.add_member(db, group_id, body.user_id)


@router.get("/groups/{group_id}/members", response_model=list[s.Member])
def members(group_id: GroupId, db: Database):
    return services.list_members(db, group_id)


@router.post("/groups/{group_id}/expenses", response_model=s.Expense, status_code=201)
def create_expense(group_id: GroupId, body: s.ExpenseRequest, response: Response, db: Database):
    result, replay = services.create_financial(db, group_id, body, expense=True)
    response.status_code = 200 if replay else 201
    return result


@router.post("/groups/{group_id}/settlements", response_model=s.Settlement, status_code=201)
def create_settlement(group_id: GroupId, body: s.SettlementRequest, response: Response, db: Database):
    result, replay = services.create_financial(db, group_id, body, expense=False)
    response.status_code = 200 if replay else 201
    return result


@router.get("/groups/{group_id}/expenses", response_model=s.Page[s.Expense])
def expenses(group_id: GroupId, db: Database, limit: Limit = 50, offset: Offset = 0):
    return services.history(db, group_id, m.expenses, limit, offset)


@router.get("/groups/{group_id}/settlements", response_model=s.Page[s.Settlement])
def settlements(group_id: GroupId, db: Database, limit: Limit = 50, offset: Offset = 0):
    return services.history(db, group_id, m.settlements, limit, offset)


@router.get("/groups/{group_id}/balances", response_model=s.Balances)
def balances(group_id: GroupId, db: Database):
    return services.balances(db, group_id)


@router.get("/groups/{group_id}/settlement-suggestions", response_model=s.Suggestions)
def suggestions(group_id: GroupId, db: Database):
    summary = services.balances(db, group_id)
    return {"group_id": group_id, "suggestions": summary["suggested_payments"]}
