import time

class SimpleTTLCache:
    def __init__(self, ttl=60):
        self.ttl = ttl
        self.cache = {}

    def get(self, key):
        if key in self.cache:
            val, expiry = self.cache[key]
            if time.time() < expiry:
                return val
            else:
                del self.cache[key]
        return None

    def set(self, key, value):
        self.cache[key] = (value, time.time() + self.ttl)
        
    def clear(self, key_prefix=None):
        if key_prefix is None:
            self.cache.clear()
        else:
            keys_to_delete = [k for k in self.cache.keys() if str(k).startswith(str(key_prefix))]
            for k in keys_to_delete:
                del self.cache[k]

# Global instances for caching
summary_cache = SimpleTTLCache(ttl=120) # 2 minutes for devices summary
dashboard_cache = SimpleTTLCache(ttl=300) # 5 minutes for dashboard metrics
