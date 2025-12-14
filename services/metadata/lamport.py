"""
Lamport Logical Clock Implementation

Provides total ordering of events in the distributed system.
Used for resolving conflicts when two concurrent requests arrive.
"""

import threading


class LamportClock:
    """
    Lamport Logical Clock for establishing happened-before relationships.
    
    Rules:
    1. Increment clock before each local event
    2. When sending a message, include current clock value
    3. When receiving a message, update clock to max(local, received) + 1
    """
    
    def __init__(self):
        self.time = 0
        self.lock = threading.Lock()
    
    def increment(self):
        """Increment clock for local event and return new time"""
        with self.lock:
            self.time += 1
            return self.time
    
    def update(self, received_time):
        """Update clock on message reception"""
        with self.lock:
            self.time = max(self.time, received_time) + 1
            return self.time
    
    def get_time(self):
        """Get current clock value"""
        with self.lock:
            return self.time
