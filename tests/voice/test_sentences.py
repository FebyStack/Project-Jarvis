from jarvis.voice.sentences import Splitter, speakable


def test_sentences_come_out_as_they_complete():
    s = Splitter()
    assert s.feed("Right. I'll che") == ["Right."]
    assert s.feed("ck now. ") == ["I'll check now."]
    assert s.flush() == []


def test_numbers_and_times_do_not_split():
    assert Splitter().feed("It's 3.5 GB at 10:05. ") == ["It's 3.5 GB at 10:05."]


def test_a_long_first_sentence_starts_at_a_clause_break():
    s = Splitter()
    assert s.feed("Well, " + "x" * 60) == ["Well,"]  # only the first chunk of a reply may do this
    assert s.feed(" and so, " + "y" * 80) == []


def test_flush_gives_the_tail():
    s = Splitter()
    assert s.feed("No full stop") == [] and s.flush() == ["No full stop"]


def test_a_newline_ends_a_chunk():
    assert Splitter().feed("- one\n- two\n") == ["- one", "- two"]


def test_speakable():
    assert speakable("**Done** — see `notes.md` at https://example.com/a?b=1") == "Done — see notes.md at a link"
    assert speakable("```") == "" and speakable("  \n ") == ""
