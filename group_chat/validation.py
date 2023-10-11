USER_ID_MIN_LEN = 3
USER_ID_MAX_LEN = 32
PASSWORD_MIN_LEN = 4
PASSWORD_MAX_LEN = 8


def validate_user_and_password(user_id: str, password: str) -> bool:
    good_user_id_len = len(user_id) in range(USER_ID_MIN_LEN, USER_ID_MAX_LEN + 1)
    good_password_len = len(password) in range(PASSWORD_MIN_LEN, PASSWORD_MAX_LEN + 1)
    no_spaces = [item.split()[0] == item for item in (user_id, password)]
    return good_user_id_len and good_password_len and no_spaces
