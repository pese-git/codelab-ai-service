"""Cryptography utilities"""

import hashlib
import secrets

from passlib.context import CryptContext

# Password hashing context with bcrypt
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12,  # Cost factor
)


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt
    
    Args:
        password: Plain text password
        
    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash (constant-time comparison)
    
    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against
        
    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def hash_token_jti(jti: str) -> str:
    """
    Hash a JWT jti claim using SHA-256
    
    Args:
        jti: JWT ID to hash
        
    Returns:
        Hexadecimal hash string (64 characters)
    """
    return hashlib.sha256(jti.encode()).hexdigest()


def generate_secret(length: int = 32) -> str:
    """
    Generate a cryptographically secure random secret
    
    Args:
        length: Length of the secret in bytes
        
    Returns:
        Hexadecimal secret string
    """
    return secrets.token_hex(length)


def constant_time_compare(a: str, b: str) -> bool:
    """
    Compare two strings in constant time to prevent timing attacks
    
    Args:
        a: First string
        b: Second string
        
    Returns:
        True if strings are equal, False otherwise
    """
    return secrets.compare_digest(a.encode(), b.encode())
