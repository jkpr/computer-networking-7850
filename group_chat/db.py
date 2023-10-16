"""A database for user IDs and passwords."""

from pathlib import Path


FILE_NAME = "users.txt"
ENCODING = "utf-8"


def user_exists(user_id: str) -> bool:
    """Check if the given user ID exists in the DB."""
    path = Path(__file__).parent / Path(FILE_NAME)
    if not path.exists():
        return False
    for line in path.read_text(encoding=ENCODING).splitlines():
        split = line.split()
        if len(split) == 2 and split[0] == user_id:
            return True
    return False


def user_and_password_exists(user_id: str, password: str) -> bool:
    """Check if the given user ID and password exist in the DB."""
    path = Path(__file__).parent / Path(FILE_NAME)
    if not path.exists():
        return False
    for line in path.read_text(encoding=ENCODING).splitlines():
        split = line.split()
        if len(split) == 2 and split[0] == user_id and split[1] == password:
            return True
    return False


def insert_new_user_and_password(user_id: str, password: str) -> bool:
    """Add a new user ID and password to the DB."""
    path = Path(__file__).parent / Path(FILE_NAME)
    if user_exists(user_id):
        return False
    record = f"{user_id} {password}\n"
    with path.open("a", encoding=ENCODING) as f:
        f.write(record)
    return True
        