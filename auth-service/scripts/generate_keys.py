#!/usr/bin/env python3
"""Script to generate RSA key pair for JWT signing"""

import argparse
import os
from pathlib import Path

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_rsa_keys(output_dir: str = "./keys", key_size: int = 2048) -> None:
    """
    Generate RSA key pair and save to files
    
    Args:
        output_dir: Directory to save keys
        key_size: Size of RSA key in bits (default: 2048)
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    print(f"Generating RSA key pair ({key_size} bits)...")

    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend(),
    )

    # Get public key
    public_key = private_key.public_key()

    # Save private key
    private_key_path = output_path / "private_key.pem"
    with open(private_key_path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    # Save public key
    public_key_path = output_path / "public_key.pem"
    with open(public_key_path, "wb") as f:
        f.write(
            public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )

    # Set restrictive permissions
    os.chmod(private_key_path, 0o600)
    os.chmod(public_key_path, 0o644)

    print(f"✓ Private key saved to: {private_key_path}")
    print(f"✓ Public key saved to: {public_key_path}")
    print(f"✓ Permissions set: private_key (600), public_key (644)")
    print("\nKeys generated successfully!")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Generate RSA key pair for JWT signing"
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        default="./keys",
        help="Output directory for keys (default: ./keys)",
    )
    parser.add_argument(
        "--key-size",
        "-s",
        type=int,
        default=2048,
        choices=[2048, 4096],
        help="RSA key size in bits (default: 2048)",
    )

    args = parser.parse_args()

    generate_rsa_keys(output_dir=args.output_dir, key_size=args.key_size)


if __name__ == "__main__":
    main()
