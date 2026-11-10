from jarvis.brain.trusted import TrustedList


def test_trusted_file_is_hand_editable(tmp_path):
    f = tmp_path / "trusted.txt"; f.write_text("# mine\n\nshell:git push\n")
    t = TrustedList(f)
    assert t.contains("shell:git push") and not t.contains("# mine")
    t.add("shell:git push"); t.add("screen:Mail:send")
    assert f.read_text().count("shell:git push") == 1 and t.contains("screen:Mail:send")
