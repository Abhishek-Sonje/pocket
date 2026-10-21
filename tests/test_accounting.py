"""Also runnable without installed dependencies: python -m unittest tests.test_accounting."""

import random
import unittest

from app.accounting import split_equal, suggest_payments, summarize


class AccountingTests(unittest.TestCase):
    def test_splits(self):
        self.assertEqual(
            [s["share_paise"] for s in split_equal(10000, [3, 1, 2])], [3334, 3333, 3333]
        )
        self.assertEqual([s["share_paise"] for s in split_equal(1, [3, 2, 1])], [1, 0, 0])
        self.assertEqual(split_equal(43, [2]), [{"user_id": 2, "share_paise": 43}])

    def test_worked_trip(self):
        members = [{"user_id": i, "name": str(i)} for i in (1, 2, 3)]
        expenses = [
            {"paid_by": i, "amount_paise": amount}
            for i, amount in [(1, 120000), (2, 60000), (3, 30000)]
        ]
        shares = (
            split_equal(120000, [1, 2, 3]) + split_equal(60000, [2, 3]) + split_equal(30000, [1])
        )
        repayments = [{"from_user": 2, "to_user": 1, "amount_paise": 6000}]
        summary = summarize(1, members, expenses, shares, repayments)
        self.assertEqual(
            [m["net_balance_paise"] for m in summary["members"]], [44000, -4000, -40000]
        )
        self.assertEqual(summary["total_expenses_paise"], 210000)
        self.assertEqual(
            summary["suggested_payments"],
            [
                {"from_user": 3, "to_user": 1, "amount_paise": 40000},
                {"from_user": 2, "to_user": 1, "amount_paise": 4000},
            ],
        )

    def test_generated_invariants(self):
        rng = random.Random(42)
        for _ in range(500):
            count = rng.randint(1, 30)
            amount = rng.randint(1, 2**63 - 1)
            shares = split_equal(amount, list(range(count)))
            self.assertEqual(sum(s["share_paise"] for s in shares), amount)
            self.assertLessEqual(
                max(s["share_paise"] for s in shares) - min(s["share_paise"] for s in shares), 1
            )
            nets = [-s["share_paise"] for s in shares]
            nets[rng.randrange(count)] += amount
            members = [{"user_id": i, "net_balance_paise": value} for i, value in enumerate(nets)]
            payments = suggest_payments(members)
            self.assertEqual(payments, suggest_payments(list(reversed(members))))
            for payment in payments:
                self.assertGreater(payment["amount_paise"], 0)
                self.assertNotEqual(payment["from_user"], payment["to_user"])
                nets[payment["from_user"]] += payment["amount_paise"]
                nets[payment["to_user"]] -= payment["amount_paise"]
            self.assertTrue(all(value == 0 for value in nets))

    def test_empty_and_cycles(self):
        self.assertEqual(summarize(1, [], [], [], [])["suggested_payments"], [])
        self.assertEqual(
            suggest_payments([{"user_id": i, "net_balance_paise": 0} for i in range(3)]), []
        )


if __name__ == "__main__":
    unittest.main()
