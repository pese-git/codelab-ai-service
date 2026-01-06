"""JWKS (JSON Web Key Set) service"""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.security import rsa_key_manager


class JWKSService:
    """Service for generating JWKS (JSON Web Key Set)"""

    def get_jwks(self) -> dict:
        """
        Get JWKS (JSON Web Key Set) for public key distribution
        
        Returns:
            JWKS dictionary with public keys
        """
        public_key = rsa_key_manager.public_key

        # Get public key numbers
        public_numbers = public_key.public_numbers()

        # Convert to base64url encoding (without padding)
        n = self._int_to_base64url(public_numbers.n)
        e = self._int_to_base64url(public_numbers.e)

        jwks = {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "kid": rsa_key_manager.kid,
                    "alg": "RS256",
                    "n": n,
                    "e": e,
                }
            ]
        }

        return jwks

    def _int_to_base64url(self, value: int) -> str:
        """
        Convert integer to base64url encoded string
        
        Args:
            value: Integer value to encode
            
        Returns:
            Base64url encoded string (without padding)
        """
        # Convert integer to bytes
        value_bytes = value.to_bytes(
            (value.bit_length() + 7) // 8,
            byteorder="big",
        )

        # Encode to base64url (without padding)
        encoded = base64.urlsafe_b64encode(value_bytes).decode("utf-8")
        return encoded.rstrip("=")


# Global instance
jwks_service = JWKSService()
