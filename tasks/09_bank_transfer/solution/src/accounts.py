"""Account storage for the ledger."""

from decimal import Decimal


class UnknownAccount(Exception):
    """Raised when an account id is not in the store."""


class InsufficientFunds(Exception):
    """Raised when an account does not hold enough to cover a debit."""


def to_decimal(amount):
    """Convert an int, string or Decimal to an exact Decimal.

    Going through str() matters: building a Decimal straight from a float would
    faithfully copy the float's rounding error, while the string form of one
    tenth is exactly one tenth.
    """
    if isinstance(amount, Decimal):
        return amount
    return Decimal(str(amount))


class AccountStore:
    """Keeps a balance for each account id."""

    def __init__(self):
        self._balances = {}

    def open(self, account_id, starting_balance=0):
        self._balances[account_id] = to_decimal(starting_balance)

    def balance(self, account_id):
        if account_id not in self._balances:
            raise UnknownAccount(account_id)
        return self._balances[account_id]

    def credit(self, account_id, amount):
        self._balances[account_id] = self.balance(account_id) + to_decimal(amount)

    def debit(self, account_id, amount):
        self._balances[account_id] = self.balance(account_id) - to_decimal(amount)
