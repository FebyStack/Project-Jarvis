"""Voice state machine (spec §6.1): IDLE → LISTENING → THINKING → SPEAKING → FOLLOW_UP → IDLE."""
from enum import Enum, auto
from typing import Callable

from jarvis.config import LISTEN_SECONDS

FOLLOW_UP_SECONDS = 6.0


class State(Enum):
    IDLE = auto()
    LISTENING = auto()
    THINKING = auto()
    SPEAKING = auto()
    FOLLOW_UP = auto()


class Event(Enum):
    WAKE = auto()
    SPEECH_START = auto()
    SPEECH_END = auto()
    REPLY_START = auto()
    REPLY_END = auto()
    TICK = auto()
    MUTE = auto()
    UNMUTE = auto()
    CANCEL = auto()
    PUSH = auto()  # the talk key: listens from any state, even muted
    REQUEST = auto()  # a typed request on the Mac
    REPLY_PAUSE = auto()  # speech ran out, the turn goes on


# WAKE is accepted only in IDLE (and LISTENING, to restart it), so Jarvis cannot wake itself while thinking or speaking.
_WAKES = (State.IDLE, State.LISTENING)
_TRANSITIONS = {
    (State.IDLE, Event.REQUEST): State.THINKING,
    (State.FOLLOW_UP, Event.REQUEST): State.THINKING,
    (State.IDLE, Event.REPLY_START): State.SPEAKING,  # an announcement or an instant answer
    (State.FOLLOW_UP, Event.REPLY_START): State.SPEAKING,
    (State.SPEAKING, Event.REPLY_PAUSE): State.THINKING,
    (State.LISTENING, Event.SPEECH_END): State.THINKING,
    (State.THINKING, Event.REPLY_START): State.SPEAKING,
    (State.THINKING, Event.REPLY_END): State.IDLE,  # the reply ended without speech (empty or failed)
    (State.SPEAKING, Event.REPLY_END): State.FOLLOW_UP,
    (State.FOLLOW_UP, Event.SPEECH_START): State.LISTENING,
    (State.LISTENING, Event.CANCEL): State.IDLE,
    (State.THINKING, Event.CANCEL): State.IDLE,
    (State.SPEAKING, Event.CANCEL): State.IDLE,
    (State.FOLLOW_UP, Event.CANCEL): State.IDLE,
}


class StateMachine:
    def __init__(self, clock: Callable[[], float]):
        self.clock = clock
        self.state = State.IDLE
        self.muted = False
        self._follow_up_since = self._listening_since = 0.0
        self._speech_seen = False

    @property
    def mic_open(self) -> bool:
        return self.state is not State.SPEAKING and (not self.muted or self.state is State.LISTENING)

    def on(self, event: Event) -> State:
        now = self.clock()
        if self.state is State.FOLLOW_UP and now - self._follow_up_since >= FOLLOW_UP_SECONDS:
            self.state = State.IDLE
        if self.state is State.LISTENING and not self._speech_seen and now - self._listening_since >= LISTEN_SECONDS:
            self.state = State.IDLE
        if event is Event.MUTE:
            self.muted = True
            if self.state in (State.LISTENING, State.FOLLOW_UP):
                self.state = State.IDLE
        elif event is Event.UNMUTE:
            self.muted = False
        elif event is Event.PUSH or (event is Event.WAKE and not self.muted and self.state in _WAKES):
            self.state, self._listening_since, self._speech_seen = State.LISTENING, now, False
        elif not (self.muted and event is Event.WAKE):
            self.state = _TRANSITIONS.get((self.state, event), self.state)
            self._speech_seen |= event is Event.SPEECH_START  # also entering LISTENING from the follow-up window
            if self.state is State.FOLLOW_UP and event is Event.REPLY_END:
                self._follow_up_since = now
                if self.muted:  # no follow-up window while the mic is off
                    self.state = State.IDLE
        return self.state
