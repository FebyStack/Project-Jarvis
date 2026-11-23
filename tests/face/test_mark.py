import math

from jarvis.daemon.names import NAMES
from jarvis.face.mark import Mark, curve, mark


def test_a_name_always_gets_the_same_mark():
    assert mark("Nova") == mark("Nova") == Mark(5, 0.35, (0.7117670855789375, 0.36815538909255385, 5.129631754689584), -1)


def test_every_name_in_the_list_has_its_own_mark():
    assert len({mark(n) for n in NAMES}) == len(NAMES)


def test_a_curve_is_closed_and_inside_the_unit_circle():
    for name in NAMES:
        m = mark(name)
        assert 3 <= m.petals <= 7 and 0.30 <= m.depth <= 0.50 and m.way in (1, -1)
        for layer in range(3):
            c = curve(m, layer)
            assert len(c) == 73 and c[0] == c[-1]
            assert all(math.hypot(x, y) <= 1 + 1e-9 for x, y in c)
