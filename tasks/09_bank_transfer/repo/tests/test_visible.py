from decimal import Decimal

from src.accounts import AccountStore, InsufficientFunds, UnknownAccount
from src.ledger import transfer

import pytest


def _store():
    store = AccountStore()
    store.open("alice", 100)
    store.open("bob", 0)
    return store


def test_a_successful_transfer_moves_the_money():
    store = _store()
    transfer(store, "alice", "bob", 30)
    assert store.balance("alice") == Decimal("70")
    assert store.balance("bob") == Decimal("30")


def test_deposits_keep_exact_decimal_amounts():
    store = AccountStore()
    store.open("alice", 0)
    store.credit("alice", "0.1")
    store.credit("alice", "0.2")
    assert store.balance("alice") == Decimal("0.3")


def test_a_rejected_transfer_leaves_balances_untouched():
    store = _store()
    with pytest.raises(InsufficientFunds):
        transfer(store, "alice", "bob", 500)
    assert store.balance("alice") == Decimal("100")
    assert store.balance("bob") == Decimal("0")


def test_an_unknown_destination_does_not_take_money_from_the_source():
    store = _store()
    with pytest.raises(UnknownAccount):
        transfer(store, "alice", "nobody", 10)
    assert store.balance("alice") == Decimal("100")
