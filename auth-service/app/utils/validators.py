"""Input validation utilities"""

import re


def validate_email(email: str) -> tuple[bool, str | None]:
    """
    Validate email format
    
    Args:
        email: Email address to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not email:
        return False, "Email is required"

    # Basic email regex
    email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    if not re.match(email_regex, email):
        return False, "Invalid email format"

    if len(email) > 255:
        return False, "Email is too long (max 255 characters)"

    return True, None


def validate_password(password: str) -> tuple[bool, str | None]:
    """
    Validate password strength
    
    Requirements:
    - Minimum 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    
    Args:
        password: Password to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not password:
        return False, "Password is required"

    if len(password) < 8:
        return False, "Password must be at least 8 characters long"

    if len(password) > 72:
        return False, "Password is too long (max 72 characters for bcrypt)"

    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"

    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"

    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit"

    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character"

    return True, None


def validate_username(username: str) -> tuple[bool, str | None]:
    """
    Validate username format
    
    Requirements:
    - Minimum 3 characters
    - Maximum 255 characters
    - Alphanumeric and underscores only
    
    Args:
        username: Username to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not username:
        return False, "Username is required"

    if len(username) < 3:
        return False, "Username must be at least 3 characters long"

    if len(username) > 255:
        return False, "Username is too long (max 255 characters)"

    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        return False, "Username can only contain letters, numbers, and underscores"

    return True, None


def validate_scope(scope: str) -> tuple[bool, str | None]:
    """
    Validate scope format
    
    Args:
        scope: Space-separated scopes
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not scope:
        return True, None  # Empty scope is allowed

    # Split by space
    scopes = scope.split()

    # Validate each scope
    scope_regex = r"^[a-zA-Z0-9_:.-]+$"

    for s in scopes:
        if not re.match(scope_regex, s):
            return False, f"Invalid scope format: {s}"

        if len(s) > 100:
            return False, f"Scope is too long: {s}"

    return True, None


def validate_client_id(client_id: str) -> tuple[bool, str | None]:
    """
    Validate client_id format
    
    Args:
        client_id: Client ID to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not client_id:
        return False, "Client ID is required"

    if len(client_id) < 3:
        return False, "Client ID must be at least 3 characters long"

    if len(client_id) > 255:
        return False, "Client ID is too long (max 255 characters)"

    # Allow alphanumeric, hyphens, and underscores
    if not re.match(r"^[a-zA-Z0-9_-]+$", client_id):
        return False, "Client ID can only contain letters, numbers, hyphens, and underscores"

    return True, None
