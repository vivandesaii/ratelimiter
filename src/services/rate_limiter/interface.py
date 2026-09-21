from abc import ABC, abstractmethod


class RateLimiterInterface(ABC):
    @abstractmethod
    def allow_request(self, timestamp: float) -> bool: ...
