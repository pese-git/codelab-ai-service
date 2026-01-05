"""Security utilities for RSA keys management"""

import os
from pathlib import Path

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import logger, settings


class RSAKeyManager:
    """Manager for RSA key pair"""

    def __init__(self):
        self._private_key = None
        self._public_key = None
        self._kid = "2024-01-key-1"  # Key ID for JWKS

    def load_keys(self) -> None:
        """Load RSA keys from files"""
        try:
            # Load private key
            private_key_path = Path(settings.private_key_path)
            if not private_key_path.exists():
                logger.warning(f"Private key not found at {private_key_path}")
                logger.info("Generating new RSA key pair...")
                self.generate_keys()
                return

            with open(private_key_path, "rb") as f:
                self._private_key = serialization.load_pem_private_key(
                    f.read(),
                    password=None,
                    backend=default_backend(),
                )

            # Load public key
            public_key_path = Path(settings.public_key_path)
            with open(public_key_path, "rb") as f:
                self._public_key = serialization.load_pem_public_key(
                    f.read(),
                    backend=default_backend(),
                )

            logger.info("RSA keys loaded successfully")

        except Exception as e:
            logger.error(f"Failed to load RSA keys: {e}")
            raise

    def generate_keys(self, key_size: int = 2048) -> None:
        """
        Generate new RSA key pair
        
        Args:
            key_size: Size of the RSA key in bits (default: 2048)
        """
        try:
            # Generate private key
            self._private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size,
                backend=default_backend(),
            )

            # Get public key
            self._public_key = self._private_key.public_key()

            # Save keys
            self.save_keys()

            logger.info(f"Generated new RSA key pair ({key_size} bits)")

        except Exception as e:
            logger.error(f"Failed to generate RSA keys: {e}")
            raise

    def save_keys(self) -> None:
        """Save RSA keys to files"""
        try:
            # Ensure directories exist
            private_key_path = Path(settings.private_key_path)
            public_key_path = Path(settings.public_key_path)

            private_key_path.parent.mkdir(parents=True, exist_ok=True)
            public_key_path.parent.mkdir(parents=True, exist_ok=True)

            # Save private key
            with open(private_key_path, "wb") as f:
                f.write(
                    self._private_key.private_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption(),
                    )
                )

            # Save public key
            with open(public_key_path, "wb") as f:
                f.write(
                    self._public_key.public_bytes(
                        encoding=serialization.Encoding.PEM,
                        format=serialization.PublicFormat.SubjectPublicKeyInfo,
                    )
                )

            # Set restrictive permissions
            os.chmod(private_key_path, 0o600)
            os.chmod(public_key_path, 0o644)

            logger.info("RSA keys saved successfully")

        except Exception as e:
            logger.error(f"Failed to save RSA keys: {e}")
            raise

    @property
    def private_key(self):
        """Get private key"""
        if self._private_key is None:
            self.load_keys()
        return self._private_key

    @property
    def public_key(self):
        """Get public key"""
        if self._public_key is None:
            self.load_keys()
        return self._public_key

    @property
    def kid(self) -> str:
        """Get key ID"""
        return self._kid

    def get_public_key_pem(self) -> str:
        """Get public key in PEM format"""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()

    def get_private_key_pem(self) -> str:
        """Get private key in PEM format"""
        return self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()


# Global instance
rsa_key_manager = RSAKeyManager()
