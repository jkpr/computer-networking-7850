"""
All messages and commands passed between client and server.

Each subclass of Command implements the command design pattern, meaning
it stores all relevant information needed to check for validity and to
be able to execute.
"""

from abc import ABC, abstractmethod

from .validation import validate_user_and_password


class Command(ABC):
    """
    Command base class, encapsulating basic rules of communication.

    Each command is represented as a UTF-8 string.

    - The first character (the identifier) represents the command type.
    - Each command type has 0, 1, or 2 different fields. Each field has
      a key.
    - The length of each field is sent as a string of fixed width,
      padded with " " (space), e.g. width of four bytes: "   1" or
      "  24".
    - After the headers, the field bytes are sent in order.

    Example:

    The "newuser" command has identifier N and sends two fields for the
    user_id and the password. An example might be:

    "N   6  10myusermypassword" (encoded to bytes with UTF-8).

    This is sent from the client and meant to create a new user with
    username "myuser" and password "mypassword".
    """
    ENCODING = "utf-8"
    HEADER_WIDTH = 4
    MAX_MESSAGE_SIZE = 1024

    identifier = "_"
    keys = []

    def __init__(self, socket, *args, server=None, client=None, **kwargs):
        self.socket = socket
        self.server = server
        self.client = client
        if not kwargs and len(args) == len(self.keys):
            for arg, key in zip(args, self.keys):
                setattr(self, key, arg)
        elif not args:
            for key in self.keys:
                setattr(self, key, kwargs[key])

    @staticmethod
    def read(socket, count):
        """Read a certain number of bytes from a socket."""
        chunks = []
        total_received = 0
        while total_received < count:
            chunk = socket.recv(min(count - total_received, Command.MAX_MESSAGE_SIZE))
            chunks.append(chunk)
            total_received += len(chunk)
        return b''.join(chunks)
    
    @abstractmethod
    def execute(self):
        """Execute the command."""
        ...

    @staticmethod
    def get_help() -> str:
        """Return help string for this command, if applicable."""
        return ""

    def validate(self) -> bool:
        """Check if this this command is valid."""
        return True

    def request(self, with_lock=False):
        """Send a command over the socket."""
        if with_lock and self.server:
            with self.server.locks[self.socket.fileno()]:
                self.socket.sendall(self.get_request_payload())
        else:
            self.socket.sendall(self.get_request_payload())

    def get_request_payload(self):
        """Represent the command as a byte array for the socket."""
        values = [getattr(self, key).encode(self.ENCODING) for key in self.keys]
        headers = [
            f"{len(byte_value):>{self.HEADER_WIDTH}}".encode(self.ENCODING) for byte_value in values
        ]
        return b''.join([self.identifier.encode(self.ENCODING), *headers, *values])
        
    @classmethod
    def from_socket(cls, socket, server=None, client=None):
        """
        Recreate this command object from the socket.

        Presumably, the first byte (the identifier) has been read
        already from the socket.
        """
        header_size = len(cls.keys) * cls.HEADER_WIDTH
        header_bytes = cls.read(socket, header_size)
        kwargs = {}
        for i, key in enumerate(cls.keys):
            header = header_bytes[(i*cls.HEADER_WIDTH):(i*cls.HEADER_WIDTH + cls.HEADER_WIDTH)]
            count = int(header.decode(cls.ENCODING))
            value_bytes = cls.read(socket, count)
            kwargs[key] = value_bytes.decode(cls.ENCODING)
        return cls(socket, **kwargs, server=server, client=client)
    
    def __repr__(self):
        values = [getattr(self, key) for key in self.keys]
        args = []
        for key, value in zip(self.keys, values):
            args.append(f"{key}={value!r}")
        return f"{self.__class__.__name__}({', '.join(args)})"


class ConnectCommand(Command):
    """
    Communicate to the server which client software version is running.

    Client to server command.
    """

    identifier = "C"
    keys = ["version"]

    def execute(self):
        if int(self.version) != self.server.version:
            message = f"Server is running version {self.server.version}. Update client to correct version."
            DisconnectCommand(self.socket, message=message, server=self.server).request(with_lock=True)
            self.server.disconnect(self.socket)
        
    def validate(self):
        return self.version in ["1", "2"]


class DisconnectCommand(Command):
    """
    Tell the client to disconnect.

    Server to client command.
    """
    identifier = "X"
    keys = ["message"]

    def execute(self):
        self.client.disconnect()
        self.client.print(self.message)


class LoginCommand(Command):
    """
    Login to the server.

    Client to server command.
    """
    identifier = "A"
    keys = ["user_id", "password"]

    def execute(self):
        authenticated = self.server.authenticate(self.user_id, self.password)
        if authenticated:
            self.server.broadcast(f"{self.user_id} joins.")
            self.server.login(self.user_id, self.socket)
            self.server.print(f"{self.user_id} login")
            UserIdCommand(self.socket, self.user_id, server=self.server).request(with_lock=True)
        else:
            message = f"Denied. User name or password incorrect."
            PrintCommand(self.socket, message, server=self.server).request(with_lock=True)
    
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
    """
    Create a new user for group chat.

    Client to server command.
    """
    identifier = "N"
    keys = ["user_id", "password"]

    def execute(self):
        created = self.server.create_user(self.user_id, self.password)
        if created:
            message = "New user account created. Please login."
            self.server.print("New user account created.")
        else:
            message = "Denied. User account already exists."
        PrintCommand(self.socket, message, server=self.server).request(with_lock=True)
    
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


class PrintCommand(Command):
    """
    Print the message in the payload.

    Server to client command.
    """
    identifier = "P"
    keys = ["message"]

    def execute(self):
        self.client.print(self.message)


class SendAllCommand(Command):
    """
    Broadcast the message in the payload to all logged in users.

    Client to server command.
    """
    identifier: str = "S"
    keys = ["message"]

    def execute(self):
        from_user_id = self.server.get_user_by_socket(self.socket)
        full_message = f"{from_user_id}: {self.message}"
        self.server.print(full_message)
        for user_id, client_socket in self.server.current_users.items():
            if self.server.version == 2 and from_user_id == user_id:
                continue
            PrintCommand(client_socket, full_message, server=self.server).request(with_lock=True)
    
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
    """
    Send a direct message to the specified user.

    Client to server command.
    """
    identifier = "D"
    keys = ["user_id", "message"]

    def execute(self):
        from_user_id = self.server.get_user_by_socket(self.socket)
        client_socket = self.server.current_users.get(self.user_id)
        self.server.print(f"{from_user_id} (to {self.user_id}): {self.message}")
        if client_socket:
            message = f"{from_user_id}= {self.message}"
            to_socket = client_socket
        else:
            message = "That user is not logged in."
            to_socket = self.socket
        PrintCommand(to_socket, message, server=self.server).request(with_lock=True)

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

class UserIdCommand(Command):
    """
    Announce to the client what user ID is logged in.

    Server to client command.
    """
    identifier = "U"
    keys = ["user_id"]

    def execute(self):
        self.client.set_current_user(self.user_id)
        self.client.print("login confirmed")

class WhoCommand(Command):
    """
    Request a list of logged in users.

    Client to server command.
    """
    identifier = "W"

    def execute(self):
        connected_users = self.server.get_all_connected_users()
        connected_users_formatted = ", ".join(connected_users)
        PrintCommand(self.socket, connected_users_formatted, server=self.server).request(with_lock=True)

    
    @staticmethod
    def help() -> str:
        return (
            "    who                        -- version 2\n"
            "        List currently connected users.\n"
            "        - You must be logged in to check who is connected."
        )


ALL_CLIENT_TO_SERVER_COMMANDS = [
    ConnectCommand,
    LoginCommand,
    NewUserCommand,
    SendAllCommand,
    SendDirectCommand,
    WhoCommand,
]


COMMAND_LOOKUP = {command.identifier: command for command in ALL_CLIENT_TO_SERVER_COMMANDS}
