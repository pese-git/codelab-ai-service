"""User service for user management"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import logger
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.utils.crypto import hash_password, verify_password


class UserService:
    """Service for user management operations"""

    async def create_user(
        self,
        db: AsyncSession,
        user_data: UserCreate,
    ) -> User:
        """
        Create a new user
        
        Args:
            db: Database session
            user_data: User creation data
            
        Returns:
            Created user
            
        Raises:
            ValueError: If user already exists
        """
        # Check if user already exists
        existing_user = await self.get_by_username(db, user_data.username)
        if existing_user:
            raise ValueError(f"User with username '{user_data.username}' already exists")

        existing_email = await self.get_by_email(db, user_data.email)
        if existing_email:
            raise ValueError(f"User with email '{user_data.email}' already exists")

        # Hash password
        password_hash = hash_password(user_data.password)

        # Create user
        user = User(
            username=user_data.username,
            email=user_data.email,
            password_hash=password_hash,
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        logger.info(f"User created: {user.id} ({user.username})")

        return user

    async def get_by_id(self, db: AsyncSession, user_id: str) -> User | None:
        """
        Get user by ID
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            User or None if not found
        """
        result = await db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_username(self, db: AsyncSession, username: str) -> User | None:
        """
        Get user by username
        
        Args:
            db: Database session
            username: Username
            
        Returns:
            User or None if not found
        """
        result = await db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_email(self, db: AsyncSession, email: str) -> User | None:
        """
        Get user by email
        
        Args:
            db: Database session
            email: Email address
            
        Returns:
            User or None if not found
        """
        result = await db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def authenticate(
        self,
        db: AsyncSession,
        username: str,
        password: str,
    ) -> User | None:
        """
        Authenticate user by username/email and password
        
        Args:
            db: Database session
            username: Username or email
            password: Plain text password
            
        Returns:
            User if authentication successful, None otherwise
        """
        # Try to find user by username or email
        user = await self.get_by_username(db, username)
        if not user:
            user = await self.get_by_email(db, username)

        if not user:
            logger.warning(f"Authentication failed: user not found ({username})")
            return None

        # Check if user is active
        if not user.is_active:
            logger.warning(f"Authentication failed: user inactive ({username})")
            return None

        # Verify password
        if not verify_password(password, user.password_hash):
            logger.warning(f"Authentication failed: invalid password ({username})")
            return None

        # Update last login time
        user.last_login_at = datetime.utcnow()
        await db.commit()

        logger.info(f"Authentication successful: {user.id} ({user.username})")

        return user

    async def update_user(
        self,
        db: AsyncSession,
        user_id: str,
        user_data: UserUpdate,
    ) -> User | None:
        """
        Update user
        
        Args:
            db: Database session
            user_id: User ID
            user_data: User update data
            
        Returns:
            Updated user or None if not found
        """
        user = await self.get_by_id(db, user_id)
        if not user:
            return None

        # Update fields
        if user_data.username is not None:
            user.username = user_data.username
        if user_data.email is not None:
            user.email = user_data.email
        if user_data.password is not None:
            user.password_hash = hash_password(user_data.password)
        if user_data.is_active is not None:
            user.is_active = user_data.is_active
        if user_data.is_verified is not None:
            user.is_verified = user_data.is_verified

        user.updated_at = datetime.utcnow()

        await db.commit()
        await db.refresh(user)

        logger.info(f"User updated: {user.id} ({user.username})")

        return user

    async def delete_user(self, db: AsyncSession, user_id: str) -> bool:
        """
        Delete user
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            True if deleted, False if not found
        """
        user = await self.get_by_id(db, user_id)
        if not user:
            return False

        await db.delete(user)
        await db.commit()

        logger.info(f"User deleted: {user_id}")

        return True


# Global instance
user_service = UserService()
