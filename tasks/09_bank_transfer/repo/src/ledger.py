"""Moving money between accounts."""

from src.accounts import InsufficientFunds


def transfer(store, source, destination, amount):
    """Move `amount` from `source` to `destination`."""
    store.debit(source, amount)

    if amount <= 0:
        raise ValueError("transfer amount must be positive")
    if source == destination:
        raise ValueError("cannot transfer to the same account")
    if store.balance(source) < 0:
        raise InsufficientFunds(source)

    store.credit(destination, amount)
