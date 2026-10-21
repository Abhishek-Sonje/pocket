"""Pure integer accounting; no database or HTTP dependencies."""


def split_equal(amount, participant_ids):
    ids = sorted(participant_ids)
    if not ids or len(ids) != len(set(ids)) or amount <= 0:
        raise ValueError("A positive amount and distinct participants are required.")
    base, remainder = divmod(amount, len(ids))
    return [
        {"user_id": user_id, "share_paise": base + (index < remainder)}
        for index, user_id in enumerate(ids)
    ]


def suggest_payments(members):
    debtors = sorted(
        [[-m["net_balance_paise"], m["user_id"]] for m in members if m["net_balance_paise"] < 0],
        key=lambda pair: (-pair[0], pair[1]),
    )
    creditors = sorted(
        [[m["net_balance_paise"], m["user_id"]] for m in members if m["net_balance_paise"] > 0],
        key=lambda pair: (-pair[0], pair[1]),
    )
    result = []
    debtor = creditor = 0
    while debtor < len(debtors) and creditor < len(creditors):
        amount = min(debtors[debtor][0], creditors[creditor][0])
        result.append(
            {
                "from_user": debtors[debtor][1],
                "to_user": creditors[creditor][1],
                "amount_paise": amount,
            }
        )
        debtors[debtor][0] -= amount
        creditors[creditor][0] -= amount
        if debtors[debtor][0] == 0:
            debtor += 1
        if creditors[creditor][0] == 0:
            creditor += 1
    return result


def summarize(group_id, members, expenses, shares, settlements):
    rows = {
        m["user_id"]: {
            "user_id": m["user_id"],
            "name": m["name"],
            "paid_paise": 0,
            "share_paise": 0,
            "repayments_sent_paise": 0,
            "repayments_received_paise": 0,
        }
        for m in members
    }
    total = 0
    for expense in expenses:
        total += expense["amount_paise"]
        rows[expense["paid_by"]]["paid_paise"] += expense["amount_paise"]
    for share in shares:
        rows[share["user_id"]]["share_paise"] += share["share_paise"]
    for settlement in settlements:
        rows[settlement["from_user"]]["repayments_sent_paise"] += settlement["amount_paise"]
        rows[settlement["to_user"]]["repayments_received_paise"] += settlement["amount_paise"]
    for row in rows.values():
        row["net_balance_paise"] = (
            row["paid_paise"]
            - row["share_paise"]
            + row["repayments_sent_paise"]
            - row["repayments_received_paise"]
        )
    ordered = [rows[user] for user in sorted(rows)]
    return {
        "group_id": group_id,
        "total_expenses_paise": total,
        "total_outstanding_paise": sum(max(0, m["net_balance_paise"]) for m in ordered),
        "members": ordered,
        "suggested_payments": suggest_payments(ordered),
    }
