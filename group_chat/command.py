from abc import ABC, abstractmethod

from server_message import Preamble, ServerMessage


class Command(ABC):
    ENCODING = "utf-8"
    HEADER_WIDTH = 4
    
    identifier = "_"
    keys = []

    def __init__(self, socket, *args, **kwargs):
        self.socket = socket
        if not kwargs and len(args) == len(self.keys):
            for arg, key in zip(args, self.keys):
                setattr(self, key, arg)
        elif not args:
            for key in self.keys:
                setattr(self, key, kwargs[key])
    
    @abstractmethod
    def execute(self, server):
        ...

    @staticmethod
    @abstractmethod
    def help() -> str:
        ...

    def validate(self) -> bool:
        return True

    def request(self):
        self.socket.sendall(self.request_payload())

    def request_payload(self):
        values = [getattr(self, key).encode(self.ENCODING) for key in self.keys]
        headers = [
            f"{len(byte_value):>{self.HEADER_WIDTH}}".encode(self.ENCODING) for byte_value in values
        ]
        return b''.join([self.identifier.encode(self.ENCODING), *headers, *values])
    
    @staticmethod
    def socket_read_bytes(socket, count):
        chunks = []
        total_received = 0
        while total_received < count:
            chunk = socket.recv(min(count - total_received, 1024))
            chunks.append(chunk)
            total_received += len(chunk)
        return b''.join(chunks)
        
    @classmethod
    def from_socket(cls, socket):
        header_size = len(cls.keys) * cls.HEADER_WIDTH
        header_bytes = cls.socket_read_bytes(socket, header_size)
        kwargs = {}
        for i, key in enumerate(cls.keys):
            header = header_bytes[(i*cls.HEADER_WIDTH):(i*cls.HEADER_WIDTH + cls.HEADER_WIDTH)]
            count = int(header.decode(cls.ENCODING))
            value_bytes = cls.socket_read_bytes(socket, count)
            kwargs[key] = value_bytes.decode(cls.ENCODING)
        return cls(socket, **kwargs)
    
    def __repr__(self):
        values = [getattr(self, key) for key in self.keys]
        args = []
        for key, value in zip(self.keys, values):
            args.append(f"{key}={value!r}")
        return f"{self.__class__.__name__}({', '.join(args)})"


def validate_user_and_password(user_id: str, password: str) -> bool:
    good_user_id_len = len(user_id) in range(3,33)
    good_password_len = len(password) in range(4,9)
    no_spaces = [item.split()[0] == item for item in (user_id, password)]
    return good_user_id_len and good_password_len and no_spaces


class LoginCommand(Command):
    identifier = "A"
    keys = ["user_id", "password"]

    def execute(self, server):
        authenticated = server.authenticate(self.user_id, self.password)
        if authenticated:
            server.login(self.user_id, self.socket)
            success = True
            message = f"Successfully logged in as '{self.user_id}'"
        else:
            success = False
            message = f"Unable to authenticate user '{self.user_id}'. Verify credentials or create new user?"
        server.send(self.socket, ServerMessage(
            self.identifier,
            success,
            Preamble.FROM_SERVER,
            message
        ))
    
    def validate(self) -> bool:
        return validate_user_and_password(self.user_id, self.password)

    @staticmethod
    def help() -> str:
        return (
            "    login [USER_ID] [PASSWORD]\n"
            "        Log into the chat program.\n"
            "        - Both USER_ID and PASSWORD are case-sensitive.\n"
            "        - USER_ID should be 3-32 characters.\n"
            "        - PASSWORD should be 4-8 characters.\n"
            "        - Spaces and other whitespace are not allowed in USER_ID or PASSWORD."
        )


class NewUserCommand(Command):
    identifier = "N"
    keys = ["user_id", "password"]

    def execute(self, server):
        created = server.create_user(self.user_id, self.password)
        if created:
            success = True
            message = f"Successfully created user_id '{self.user_id}'. Will you login next?"
        else:
            success = False
            message = f"Unable to create user_id '{self.user_id}' because it is already taken."
        server.send(self.socket, ServerMessage(
            self.identifier,
            success,
            Preamble.FROM_SERVER,
            message
        ))  
    
    def validate(self) -> bool:
        return validate_user_and_password(self.user_id, self.password)

    @staticmethod
    def help() -> str:
        return (
            "    newuser [USER_ID] [PASSWORD]\n"
            "        Create a new user of the chat program.\n"
            "        - Both USER_ID and PASSWORD are case-sensitive.\n"
            "        - USER_ID should be 3-32 characters.\n"
            "        - PASSWORD should be 4-8 characters.\n"
            "        - Spaces and other whitespace are not allowed in USER_ID or PASSWORD."
        )



class SendAllCommand(Command):
    identifier: str = "S"
    keys = ["message"]

    def execute(self, server):
        user_id = server.get_user_by_socket(self.socket)
        server.broadcast(ServerMessage(
            self.identifier,
            True,
            Preamble.public_from(user_id),
            self.message
        ))
    
    def validate(self) -> bool:
        return len(self.message) in range(1, 257)
    
    @staticmethod
    def help() -> str:
        return (
            "    send [MESSAGE]             --  version 1\n"
            "    send all [MESSAGE]         --  version 2\n"
            "        Send a message to all users of the chat program.\n"
            "        - You must be logged in to send messages.\n"
            "        - MESSAGE should be 1-256 characters."
        )

class SendDirectCommand(Command):
    identifier = "D"
    keys = ["user_id", "message"]

    def execute(self, server):
        if server.is_user_connected(self.user_id):
            sender_id = server.get_user_by_socket(self.socket)
            server.direct_message(self.user_id, ServerMessage(
                self.identifier,
                True,
                Preamble.dm_from(sender_id),
                self.message
            ))
        else:
            server.send(self.socket, ServerMessage(
                self.identifier,
                False,
                Preamble.FROM_SERVER,
                f"User '{self.user_id}' is not connected. Check current users with 'who' command"
            ))

    def validate(self) -> bool:
        return len(self.message) in range(1, 257) and len(self.user_id) in range(3, 33)

    @staticmethod
    def help() -> str:
        return (
            "    send [USER_ID] [MESSAGE]   -- version 2\n"
            "        Send a direct message to a user of the chat program.\n"
            "        - You must be logged in to send messages.\n"
            "        - USER_ID should be 3-32 characters.\n"
            "        - MESSAGE should be 1-256 characters."
        )

class WhoCommand(Command):
    identifier = "W"

    def execute(self, server):
        you = server.get_user_by_socket(self.socket)
        connected_users = server.get_all_connected_users()
        connected_users_formatted = "\n".join(
            [f"* {user}" if user == you else f"- {user}" for user in connected_users]
        )
        server.send(self.socket, ServerMessage(
            self.identifier,
            True,
            Preamble.FROM_SERVER,
            f"Current users (* indicates you):\n{connected_users_formatted}"
        ))
    
    @staticmethod
    def help() -> str:
        return (
            "    who                        -- version 2\n"
            "        List currently connected users.\n"
            "        - You must be logged in to check who is connected."
        )


ALL_COMMANDS = [
    LoginCommand,
    NewUserCommand,
    SendAllCommand,
    SendDirectCommand,
    WhoCommand,
]


COMMAND_LOOKUP = {command.identifier: command for command in ALL_COMMANDS}
