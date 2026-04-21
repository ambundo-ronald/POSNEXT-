import unittest

from pos_next.payment_reconciliation import reconcile_change_against_payments


class TestPartialPaymentChangeReconciliation(unittest.TestCase):
    def test_reconciles_change_against_bank_payment(self):
        payments, unreconciled = reconcile_change_against_payments(
            payments=[
                {"mode_of_payment": "Bank", "amount": 270, "type": "Bank"},
            ],
            outstanding_amount=250,
        )

        self.assertEqual(unreconciled, 0)
        self.assertEqual(payments[0]["amount"], 250)

    def test_applies_change_to_last_eligible_payment(self):
        payments, unreconciled = reconcile_change_against_payments(
            payments=[
                {"mode_of_payment": "Cash", "amount": 100, "type": "Cash"},
                {"mode_of_payment": "Bank", "amount": 170, "type": "Bank"},
            ],
            outstanding_amount=250,
        )

        self.assertEqual(unreconciled, 0)
        self.assertEqual(payments[0]["amount"], 100)
        self.assertEqual(payments[1]["amount"], 150)

    def test_leaves_non_cash_bank_overpayment_unreconciled(self):
        payments, unreconciled = reconcile_change_against_payments(
            payments=[
                {"mode_of_payment": "Card", "amount": 270, "type": "Card"},
            ],
            outstanding_amount=250,
        )

        self.assertEqual(payments[0]["amount"], 270)
        self.assertEqual(unreconciled, 20)
