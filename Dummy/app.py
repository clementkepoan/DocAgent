"""
Application entry point.
"""

from auth import login_user


def main():
    username = input("Username: ")
    password = input("Password: ")

    if login_user(username, password):
        print("Login successful")
    else:
        print("Login failed")


if __name__ == "__main__":
    main()
