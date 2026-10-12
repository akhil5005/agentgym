"""Moving money between accounts."""

from src.accounts import InsufficientFunds, to_decimal


def transfer(store, source, destination, amount):
    """Move `amount` from `source` to `destination`, or change nothing at all."""
    amount = to_decimal(amount)

    # Every check happens before the first balance is touched. Validating
    # halfway through is what loses money: the debit has already landed by the
    # time the exception is raised, and nothing puts it back.
    if source == destination:
        raise ValueError("cannot transfer to the same account")
    if amount <= 0:
        raise ValueError("transfer amount must be positive")

    source_balance = store.balance(source)  # raises UnknownAccount
    store.balance(destination)  # raises UnknownAccount

    if source_balance < amount:
        raise InsufficientFunds(source)

    # Only now, with nothing left that can fail, do we move the money.
    store.debit(source, amount)
    store.credit(destination, amount)
