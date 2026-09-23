import pytest

from txtlocal.slices.analytics.model import CODE_LENGTH, is_valid_code

VALID_CODE = "ab3de5fgh7"


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (VALID_CODE, True),
        (VALID_CODE[:-1], False),
        (f"{VALID_CODE}x", False),
        ("ab3de5fgl7", False),
        ("ab3de5fgo7", False),
        ("ab3de5fg07", False),
        ("ab3de5fg17", False),
        ("AB3DE5FGH7", False),
        ("", False),
    ],
    ids=[
        "ten-lowercase-alphanumerics-is-valid",
        "nine-characters-is-too-short",
        "eleven-characters-is-too-long",
        "contains-l-is-invalid",
        "contains-o-is-invalid",
        "contains-0-is-invalid",
        "contains-1-is-invalid",
        "uppercase-is-invalid",
        "empty-is-invalid",
    ],
)
def test_is_valid_code(code: str, expected: bool) -> None:
    assert is_valid_code(code) is expected


def test_valid_code_is_exactly_the_configured_length() -> None:
    assert len(VALID_CODE) == CODE_LENGTH
