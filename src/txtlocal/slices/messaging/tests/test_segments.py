import pytest

from txtlocal.slices.messaging.segments import (
    GSM7_PART,
    MAX_CHARS,
    MAX_PARTS_CEILING,
    Encoding,
    encoding_of,
    segments_of,
)


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("", Encoding.GSM7),
        ("Hello, world", Encoding.GSM7),
        ("€100 [today]", Encoding.GSM7),
        ("Hello 你好", Encoding.UCS2),
        ("😀", Encoding.UCS2),
    ],
    ids=["empty", "ascii", "extension-table", "one-cjk-char-flips", "emoji"],
)
def test_encoding_of(body: str, expected: Encoding) -> None:
    assert encoding_of(body) is expected


@pytest.mark.parametrize(
    ("body", "encoding", "expected"),
    [
        ("", Encoding.GSM7, 0),
        ("a" * 160, Encoding.GSM7, 1),
        ("a" * 161, Encoding.GSM7, 2),
        ("a" * 306, Encoding.GSM7, 2),
        ("a" * 307, Encoding.GSM7, 3),
        ("€" * 80, Encoding.GSM7, 1),
        ("€" * 81, Encoding.GSM7, 2),
        ("你" * 70, Encoding.UCS2, 1),
        ("你" * 71, Encoding.UCS2, 2),
        ("你" * 134, Encoding.UCS2, 2),
        ("你" * 135, Encoding.UCS2, 3),
        ("😀" * 35, Encoding.UCS2, 1),
        ("😀" * 36, Encoding.UCS2, 2),
    ],
    ids=[
        "empty-body-is-zero-parts",
        "gsm-160-fits-one",
        "gsm-161-needs-two",
        "gsm-306-fills-two",
        "gsm-307-needs-three",
        "euro-costs-two-units-80-fit",
        "euro-81-overflow",
        "ucs2-70-fits-one",
        "ucs2-71-needs-two",
        "ucs2-134-fills-two",
        "ucs2-135-needs-three",
        "emoji-is-two-units-35-fit",
        "emoji-36-overflow",
    ],
)
def test_segments_of(body: str, encoding: Encoding, expected: int) -> None:
    assert segments_of(body, encoding) == expected


def test_max_chars_is_eight_gsm_parts() -> None:
    assert MAX_CHARS == MAX_PARTS_CEILING * GSM7_PART == 1224
