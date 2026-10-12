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


def test_a_transfer_conserves_the_total():
    store = _store()
    before = store.balance("alice") + store.balance("bob")
    transfer(store, "alice", "bob", 42)
    assert store.balance("alice") + store.balance("bob") == before


def test_balances_are_decimals():
    store = _store()
    assert isinstance(store.balance("alice"), Decimal)


def test_two_small_deposits_are_exact():
    store = AccountStore()
    store.open("alice", 0)
    store.credit("alice", "0.1")
    store.credit("alice", "0.2")
    assert store.balance("alice") == Decimal("0.3")


def test_many_small_deposits_stay_exact():
    store = AccountStore()
    store.open("alice", 0)
    for _ in range(10):
        store.credit("alice", "0.1")
    assert store.balance("alice") == Decimal("1.0")


def test_transferring_the_whole_balance_is_allowed():
    store = _store()
    transfer(store, "alice", "bob", 100)
    assert store.balance("alice") == Decimal("0")
    assert store.balance("bob") == Decimal("100")


def test_insufficient_funds_raises():
    store = _store()
    with pytest.raises(InsufficientFunds):
        transfer(store, "alice", "bob", 500)


def test_insufficient_funds_leaves_both_balances_unchanged():
    store = _store()
    with pytest.raises(InsufficientFunds):
        transfer(store, "alice", "bob", 500)
    assert store.balance("alice") == Decimal("100")
    assert store.balance("bob") == Decimal("0")


def test_a_zero_amount_is_rejected_and_changes_nothing():
    store = _store()
    with pytest.raises(ValueError):
        transfer(store, "alice", "bob", 0)
    assert store.balance("alice") == Decimal("100")
    assert store.balance("bob") == Decimal("0")


def test_a_negative_amount_is_rejected_and_changes_nothing():
    store = _store()
    with pytest.raises(ValueError):
        transfer(store, "alice", "bob", -50)
    assert store.balance("alice") == Decimal("100")
    assert store.balance("bob") == Decimal("0")


def test_transferring_to_the_same_account_is_rejected_and_changes_nothing():
    store = _store()
    with pytest.raises(ValueError):
        transfer(store, "alice", "alice", 30)
    assert store.balance("alice") == Decimal("100")


def test_an_unknown_account_raises_and_changes_nothing():
    store = _store()
    with pytest.raises(UnknownAccount):
        transfer(store, "alice", "nobody", 10)
    assert store.balance("alice") == Decimal("100")

    with pytest.raises(UnknownAccount):
        transfer(store, "nobody", "bob", 10)
    assert store.balance("bob") == Decimal("0")
