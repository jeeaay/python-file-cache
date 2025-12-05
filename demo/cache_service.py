import os
from dotenv import load_dotenv

# Load environment variables
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, '..', '.env'))

class Cache:
    def __init__(self):
        self.cache_type = os.getenv('CACHE_TYPE', 'file')
        self.cache_instance = self._init_cache()

    def _init_cache(self):
        if self.cache_type == 'redis':
            return self._init_redis()
        elif self.cache_type == 'file':
            return self._init_file()
        else:
            raise ValueError(f"Unsupported cache type: {self.cache_type}")

    def _init_redis(self):
        import redis
        redis_url = os.getenv('CACHE_REDIS_URL', 'redis://localhost:6379/0')
        return redis.from_url(redis_url)

    def _init_file(self):
        from filecaching import FileCache
        cache_dir = os.path.join(BASE_DIR, '..', 'cache')
        os.makedirs(cache_dir, exist_ok=True)
        return FileCache(cache_dir)

    def cache(self, key, value=None, expiration_seconds=None):
        if value is None:
            # Get cache
            if self.cache_type == 'redis':
                result = self.cache_instance.get(key)
                return result.decode('utf-8') if result else result
            else:
                return self.cache_instance.cache(key)
        else:
            # Set cache
            if self.cache_type == 'redis':
                if expiration_seconds:
                    return self.cache_instance.setex(key, expiration_seconds, value)
                else:
                    return self.cache_instance.set(key, value)
            else:
                return self.cache_instance.cache(key, value, expiration_seconds)

    def __call__(self, key, value=None, expiration_seconds=None):
        # Allow instance to be called like a function
        if expiration_seconds is None:
            # Get cache
            return self.cache(key, value)
        else:
            # Set cache
            return self.cache(key, value, expiration_seconds)

    def rm(self, key):
        if self.cache_type == 'redis':
            return self.cache_instance.delete(key)
        else:
            return self.cache_instance.rm(key)

# Create a singleton instance
cache = Cache()
