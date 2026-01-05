"""Rate limiting service using Redis"""

import redis.asyncio as aioredis

from app.core.config import logger, settings


class RateLimiter:
    """Rate limiter service using Redis"""

    def __init__(self):
        self._redis: aioredis.Redis | None = None

    async def get_redis(self) -> aioredis.Redis:
        """Get Redis connection"""
        if self._redis is None:
            self._redis = await aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def check_rate_limit_ip(
        self,
        ip_address: str,
        limit: int | None = None,
        window: int = 60,
    ) -> tuple[bool, int]:
        """
        Check rate limit for IP address
        
        Args:
            ip_address: Client IP address
            limit: Maximum requests allowed (default from settings)
            window: Time window in seconds (default: 60)
            
        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        if limit is None:
            limit = settings.rate_limit_per_ip

        key = f"rate_limit:ip:{ip_address}"
        redis = await self.get_redis()

        try:
            # Increment counter
            current = await redis.incr(key)

            # Set expiration on first request
            if current == 1:
                await redis.expire(key, window)

            # Check if limit exceeded
            is_allowed = current <= limit
            remaining = max(0, limit - current)

            if not is_allowed:
                logger.warning(
                    f"Rate limit exceeded for IP {ip_address}: {current}/{limit} in {window}s"
                )

            return is_allowed, remaining

        except Exception as e:
            logger.error(f"Rate limiter error (IP): {e}")
            # Fail open - allow request if Redis is down
            return True, limit

    async def check_rate_limit_username(
        self,
        username: str,
        limit: int | None = None,
        window: int = 3600,
    ) -> tuple[bool, int]:
        """
        Check rate limit for username
        
        Args:
            username: Username
            limit: Maximum requests allowed (default from settings)
            window: Time window in seconds (default: 3600 = 1 hour)
            
        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        if limit is None:
            limit = settings.rate_limit_per_username

        key = f"rate_limit:username:{username}"
        redis = await self.get_redis()

        try:
            # Increment counter
            current = await redis.incr(key)

            # Set expiration on first request
            if current == 1:
                await redis.expire(key, window)

            # Check if limit exceeded
            is_allowed = current <= limit
            remaining = max(0, limit - current)

            if not is_allowed:
                logger.warning(
                    f"Rate limit exceeded for username {username}: {current}/{limit} in {window}s"
                )

            return is_allowed, remaining

        except Exception as e:
            logger.error(f"Rate limiter error (username): {e}")
            # Fail open - allow request if Redis is down
            return True, limit

    async def reset_rate_limit_ip(self, ip_address: str) -> None:
        """Reset rate limit for IP address"""
        key = f"rate_limit:ip:{ip_address}"
        redis = await self.get_redis()
        await redis.delete(key)
        logger.debug(f"Rate limit reset for IP: {ip_address}")

    async def reset_rate_limit_username(self, username: str) -> None:
        """Reset rate limit for username"""
        key = f"rate_limit:username:{username}"
        redis = await self.get_redis()
        await redis.delete(key)
        logger.debug(f"Rate limit reset for username: {username}")

    async def close(self) -> None:
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()


# Global instance
rate_limiter = RateLimiter()
