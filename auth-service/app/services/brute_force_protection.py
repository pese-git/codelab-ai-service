"""Brute-force protection service"""

import redis.asyncio as aioredis

from app.core.config import logger, settings


class BruteForceProtection:
    """Service for brute-force attack protection"""

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

    async def record_failed_attempt(
        self,
        username: str,
        ip_address: str,
    ) -> None:
        """
        Record a failed login attempt
        
        Args:
            username: Username that failed
            ip_address: IP address of the request
        """
        redis = await self.get_redis()

        # Increment failed attempts counter
        username_key = f"failed_attempts:username:{username}"
        ip_key = f"failed_attempts:ip:{ip_address}"

        try:
            # Increment counters
            username_count = await redis.incr(username_key)
            ip_count = await redis.incr(ip_key)

            # Set expiration (reset after lockout duration)
            if username_count == 1:
                await redis.expire(username_key, settings.brute_force_lockout_duration)
            if ip_count == 1:
                await redis.expire(ip_key, settings.brute_force_lockout_duration)

            logger.warning(
                f"Failed login attempt: username={username}, ip={ip_address}, "
                f"username_count={username_count}, ip_count={ip_count}"
            )

        except Exception as e:
            logger.error(f"Failed to record failed attempt: {e}")

    async def is_locked_out(
        self,
        username: str,
        ip_address: str,
    ) -> tuple[bool, str | None]:
        """
        Check if username or IP is locked out
        
        Args:
            username: Username to check
            ip_address: IP address to check
            
        Returns:
            Tuple of (is_locked, reason)
        """
        redis = await self.get_redis()

        try:
            # Check username lockout
            username_key = f"failed_attempts:username:{username}"
            username_count = await redis.get(username_key)

            if username_count and int(username_count) >= settings.brute_force_threshold:
                ttl = await redis.ttl(username_key)
                logger.warning(
                    f"Username locked out: {username} ({username_count} attempts, {ttl}s remaining)"
                )
                return True, f"Too many failed attempts. Try again in {ttl} seconds."

            # Check IP lockout
            ip_key = f"failed_attempts:ip:{ip_address}"
            ip_count = await redis.get(ip_key)

            if ip_count and int(ip_count) >= settings.brute_force_threshold * 2:
                ttl = await redis.ttl(ip_key)
                logger.warning(
                    f"IP locked out: {ip_address} ({ip_count} attempts, {ttl}s remaining)"
                )
                return True, f"Too many failed attempts from this IP. Try again in {ttl} seconds."

            return False, None

        except Exception as e:
            logger.error(f"Failed to check lockout: {e}")
            # Fail open - allow request if Redis is down
            return False, None

    async def reset_failed_attempts(
        self,
        username: str,
        ip_address: str,
    ) -> None:
        """
        Reset failed attempts counter (on successful login)
        
        Args:
            username: Username to reset
            ip_address: IP address to reset
        """
        redis = await self.get_redis()

        try:
            username_key = f"failed_attempts:username:{username}"
            ip_key = f"failed_attempts:ip:{ip_address}"

            await redis.delete(username_key, ip_key)

            logger.debug(f"Failed attempts reset: username={username}, ip={ip_address}")

        except Exception as e:
            logger.error(f"Failed to reset failed attempts: {e}")

    async def get_failed_attempts_count(
        self,
        username: str,
    ) -> int:
        """
        Get number of failed attempts for username
        
        Args:
            username: Username to check
            
        Returns:
            Number of failed attempts
        """
        redis = await self.get_redis()

        try:
            key = f"failed_attempts:username:{username}"
            count = await redis.get(key)
            return int(count) if count else 0

        except Exception as e:
            logger.error(f"Failed to get failed attempts count: {e}")
            return 0

    async def close(self) -> None:
        """Close Redis connection"""
        if self._redis:
            await self._redis.close()


# Global instance
brute_force_protection = BruteForceProtection()
