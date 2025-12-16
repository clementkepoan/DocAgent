"""
Database utilities.
"""

class Database:
    def __init__(self):
        self.connected = False

    def connect(self):
        """Establish a database connection."""
        self.connected = True

    def is_connected(self) -> bool:
        """Return True if database is connected."""
        return self.connected
