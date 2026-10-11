"""Shared security rules."""

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72  # bcrypt ignores everything past 72 bytes


def validate_password_strength(password: str) -> str:
    """Pydantic validator: length, one letter and one digit; raises ValueError otherwise."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f'Password must have at least {MIN_PASSWORD_LENGTH} characters.')
    if len(password.encode('utf-8')) > MAX_PASSWORD_BYTES:
        raise ValueError(f'Password must have at most {MAX_PASSWORD_BYTES} bytes.')
    if not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        raise ValueError('Password must contain at least one letter and one digit.')
    return password
