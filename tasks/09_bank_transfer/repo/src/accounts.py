"""Account storage for the ledger."""


class UnknownAccount(Exception):
    """Raised when an account id is not in the store."""


class InsufficientFunds(Exception):
    """Raised when an account does not hold enough to cover a debit."""


class AccountStore:
    """Keeps a balance for each account id."""

    def __init__(self):
        self._balances = {}

    def open(self, account_id, starting_balance=0):
        self._balances[account_id] = float(starting_balance)

    def balance(self, account_id):
        if account_id not in self._balances:
            raise UnknownAccount(account_id)
        return self._balances[account_id]

    def credit(self, account_id, amount):
        self._balances[account_id] = self.balance(account_id) + float(amount)

    def debit(self, account_id, amount):
        self._balances[account_id] = self.balance(account_id) - float(amount)
