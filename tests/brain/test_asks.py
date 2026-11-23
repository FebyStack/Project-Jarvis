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


async def test_answer_stays_on_its_channel(asks):
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


async def test_an_unknown_reply_is_refused_and_answers_nothing(asks):
    t = asyncio.create_task(asks.ask(ASK, "mac", "r1")); await asyncio.sleep(0)
    for reply in ("nope", "Yes ", ""):
        with pytest.raises(ValueError):
            asks.answer(reply)
    assert not t.done()
    assert await t is False                                      # still only a timeout


async def test_on_change_fires_on_open_and_close(trusted):
    calls = []
    asks = Asks(trusted, {"mac": 0.05, "phone": 0.2}, lambda: calls.append(len(asks.pending())))
    t = asyncio.create_task(asks.ask(ASK, "mac", "r1")); await asyncio.sleep(0)
    assert calls == [1]
    asks.answer("yes", ask_id=asks.pending()[0].id); await t
    assert calls == [1, 0]


async def test_a_bare_answer_never_guesses_between_open_questions(asks, trusted):
    """Review finding 10: with two questions open, a yes or an always could land on the one Febriel did not mean."""
    old = asyncio.create_task(asks.ask(ASK, "mac", "m1")); await asyncio.sleep(0)
    new = asyncio.create_task(asks.ask(Decision("ask", "write x", "write:/x"), "mac", "m2")); await asyncio.sleep(0)
    assert asks.answer("always", channel="mac") is None and asks.answer("yes", channel="mac") is None
    assert not old.done() and not new.done() and not trusted.contains("write:/x")
    assert asks.answer("yes", ask_id=asks.pending()[1].id).request_id == "m2"           # the HUD answers by id
    assert asks.answer("no", channel="mac").request_id == "m1"                          # one left: no doubt
    await asyncio.gather(old, new)


async def test_question_ids_never_repeat_across_restarts(trusted):
    """Review finding 14: a HUD still showing an old question must not answer a new one."""
    ids = set()
    for _ in range(3):                                   # three jarvisd starts
        a = Asks(trusted, {"mac": 0.05, "phone": 0.2}, lambda: None)
        t = asyncio.create_task(a.ask(ASK, "mac", "r")); await asyncio.sleep(0)
        ids.add(a.pending()[0].id); a.answer("no"); await t
    assert len(ids) == 3


async def test_an_ask_remembers_which_agent_asked_and_until_when(trusted):
    asks = Asks(trusted, {"mac": 60.0, "phone": 600.0}, lambda: None, clock=lambda: 10.0)
    t = asyncio.create_task(asks.ask(ASK, "phone", "r1", "t1")); await asyncio.sleep(0)
    a = asks.pending()[0]
    assert a.agent_id == "t1" and a.until == 610.0
    asks.answer("no"); await t


async def test_an_answered_question_is_not_pending_even_before_its_waiter_resumes(asks):
    """The final review's M5: a stopped worker's row must not read needs_you for one more loop tick."""
    t = asyncio.create_task(asks.ask(ASK, "mac", "r1", "t1")); await asyncio.sleep(0)
    asks.answer("no", ask_id=asks.pending()[0].id)
    assert asks.pending() == [] and not t.done()
    await t
