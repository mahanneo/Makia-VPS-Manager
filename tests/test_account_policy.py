import pytest
from app.system_ops import validate_user_password, OperationError

def test_four_digit_pin_allowed():
    validate_user_password("1234")

def test_short_pin_rejected():
    with pytest.raises(OperationError):
        validate_user_password("123")

@pytest.mark.parametrize("malicious", [
    "goodpin\notheruser:hijack",
    "1234\rotheruser:hijack",
    "1234\x00",
    "1234\tother",
    "1234\x7f"
])
def test_manual_ssh_password_rejects_control_characters(malicious):
    with pytest.raises(OperationError, match="control characters"):
        validate_user_password(malicious)


def test_manual_ssh_password_allows_safe_nonascii_and_punctuation():
    validate_user_password("correct horse:پاسورد!")
