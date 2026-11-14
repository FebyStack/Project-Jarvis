import asyncio
from unittest.mock import ANY

import pytest

from jarvis.brain.asks import Asks
from jarvis.brain.gate import Decision
from jarvis.brain.trusted import TrustedList

ASK = Decision("ask", "rm outside the free areas: ~/Documents/a.txt", "shell:rm:~/Documents")


@pytest.fixture
def trusted(tmp_path):
    return TrustedList(tmp_path / "trusted.txt")


@pytest.fixture
def asks(trusted):
    return Asks(trusted, {"mac": 0.05, "phone": 0.2}, lambda: None)


async def test_yes_no_and_timeout(asks):
    t = asyncio.create_task(asks.ask(ASK, "mac", "r1")); await asyncio.sleep(0)
    assert asks.pending()[0].question == "rm outside the free areas: ~/Documents/a.txt. Yes or no?"
    asks.answer("yes"); assert await t is True
    t = asyncio.create_task(asks.ask(ASK, "mac", "r2")); await asyncio.sleep(0); asks.answer("no"); assert await t is False
    assert await asks.ask(ASK, "mac", "r3") is False            # nobody answered in 0.05 s
    assert asks.history() == [("r1", ANY, True), ("r2", ANY, False), ("r3", ANY, False)]


async def test_answer_goes_to_the_oldest_on_its_channel(asks):
    a = asyncio.create_task(asks.ask(ASK, "phone", "p1")); b = asyncio.create_task(asks.ask(ASK, "mac", "m1")); await asyncio.sleep(0)
    assert asks.answer("yes", channel="mac").request_id == "m1"
    assert await b is True and not a.done()


async def test_late_answer_answers_nothing(asks):
    await asks.ask(ASK, "mac", "r1")
    assert asks.answer("yes", channel="mac") is None


async def test_always_is_remembered_unless_the_pattern_is_empty(asks, trusted):
    t = asyncio.create_task(asks.ask(ASK, "mac", "r1")); await asyncio.sleep(0); asks.answer("always"); await t
    assert trusted.contains("shell:rm:~/Documents")
    t = asyncio.create_task(asks.ask(Decision("ask", "edit Jarvis's own code", ""), "mac", "r2")); await asyncio.sleep(0)
    asks.answer("always"); assert await t is True
    assert trusted._patterns() == {"shell:rm:~/Documents"}


async def test_on_change_fires_on_open_and_close(trusted):
    calls = []
    asks = Asks(trusted, {"mac": 0.05, "phone": 0.2}, lambda: calls.append(len(asks.pending())))
    t = asyncio.create_task(asks.ask(ASK, "mac", "r1")); await asyncio.sleep(0)
    assert calls == [1]
    asks.answer("yes", ask_id=asks.pending()[0].id); await t
    assert calls == [1, 0]
