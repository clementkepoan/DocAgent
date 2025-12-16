"""
Authentication logic.
"""

from database import Database


def login_user(username: str, password: str) -> bool:
    """
    Authenticate a user.
    """
    db = Database()
    db.connect()

    if not db.is_connected():
        return False

    # Dummy authentication logic
    return username == "admin" and password == "password"
