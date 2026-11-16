import pytest

from jarvis.daemon.state import StateMachine


@pytest.fixture
def sm(clock):
    return StateMachine(clock)
