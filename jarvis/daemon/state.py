"""Voice state machine (spec §6.1): IDLE → LISTENING → THINKING → SPEAKING → FOLLOW_UP → IDLE."""
from enum import Enum, auto
from typing import Callable

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


# WAKE is accepted only in IDLE, so Jarvis cannot wake itself while thinking or speaking.
_TRANSITIONS = {
    (State.IDLE, Event.WAKE): State.LISTENING,
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
        self._follow_up_since = 0.0

    @property
    def mic_open(self) -> bool:
        return not self.muted and self.state is not State.SPEAKING

    def on(self, event: Event) -> State:
        if self.state is State.FOLLOW_UP and self.clock() - self._follow_up_since >= FOLLOW_UP_SECONDS:
            self.state = State.IDLE
        if event is Event.MUTE:
            self.muted = True
            if self.state in (State.LISTENING, State.FOLLOW_UP):
                self.state = State.IDLE
        elif event is Event.UNMUTE:
            self.muted = False
        elif not (self.muted and event is Event.WAKE):
            self.state = _TRANSITIONS.get((self.state, event), self.state)
            if self.state is State.FOLLOW_UP and event is Event.REPLY_END:
                self._follow_up_since = self.clock()
                if self.muted:  # no follow-up window while the mic is off
                    self.state = State.IDLE
        return self.state
