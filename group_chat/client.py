import re
import socket
import threading

from command import Command, LoginCommand, NewUserCommand, SendAllCommand, SendDirectCommand, WhoCommand
from server_message import ServerMessage

from settings import SERVER_PORT


HOST = "127.0.0.1"
PORT = 65432


class Client:

    def __init__(self, server, port, version):
        self.server = server
        self.port = port
        self.version = version
        self.socket = None
        self.current_user = None
    
    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server, self.port))
            print(f"Connected to chat server at {self.server} port {self.port}")
            print(f"Running chat client version {self.version}")
            print(f"Type help<Enter> to see chat commands")
            threads = [
                threading.Thread(target=self.main_loop, daemon=True),
                threading.Thread(target=self.receive_messages, daemon=True),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        except ConnectionError:
            print("The chat client is unable to connect to the chat server.")
            print(f"Is the server running at {self.server}, port {self.port}?")
        except KeyboardInterrupt:
            self.socket.close()

    def main_loop(self):
        while True:
            try:
                raw_command = input()
                match raw_command.split():
                    case ["help"] | ["h"]:
                        self.print_all_help()
                    case ["login", user_id, password]:
                        command = LoginCommand(self.socket, user_id, password)
                        if command.validate() and not self.current_user:
                            command.request()
                        elif self.current_user:
                            print(f"Already logged in as '{self.current_user}'. Logout first")
                        else:
                            self.print_help(command)
                    case ["newuser", user_id, password]:
                        command = NewUserCommand(self.socket, user_id, password)
                        if command.validate() and not self.current_user:
                            command.request()
                        elif self.current_user:
                            print(f"Already logged in as '{self.current_user}'. Logout first")
                        else:
                            self.print_help(command)
                    case ["send", *the_rest] if the_rest and self.version == 1:
                        message = raw_command.split(maxsplit=1)[-1]
                        command = SendAllCommand(self.socket, message)
                        if command.validate() and self.current_user:
                            command.request()
                        elif not self.current_user:
                            print(f"You must be logged in first to do that.")
                        else:
                            self.print_help(command)
                    case ["send", "all", *the_rest] if the_rest and self.version == 2:
                        message = raw_command.split(maxsplit=2)[-1]
                        command = SendAllCommand(self.socket, message)
                        if command.validate() and self.current_user:
                            command.request()
                        elif not self.current_user:
                            print(f"You must be logged in first to do that.")
                        else:
                            self.print_help(command)
                    case ["send", user_id, *the_rest] if the_rest and self.version == 2:
                        message = raw_command.split(maxsplit=2)[-1]
                        command = SendDirectCommand(self.socket, user_id, message)
                        if command.validate() and self.current_user:
                            command.request()
                        elif not self.current_user:
                            print(f"You must be logged in first to do that.")
                        else:
                            self.print_help(command)
                        command = SendDirectCommand(self.socket, user_id, message)
                    case ["who"]:
                        command = WhoCommand(self.socket)
                        if self.current_user:
                            command.request()
                        else:
                            print(f"You must be logged in first to do that.")
                    case ["logout"]:
                        break
                    case _:
                        if raw_command:
                            print(f"Unknown command '{raw_command}'")
            except OSError:
                print("Server has disconnected. Good-bye!")
                break
        self.socket.close()

    def receive_messages(self):
        while True:
            try:
                server_message = ServerMessage.from_socket(self.socket)
                if not server_message:
                    break
                print(f"{server_message.preamble} {server_message.message}")
                if server_message.identifier == LoginCommand.identifier and server_message.success:
                    self.current_user = re.search(r"'(.+)'", server_message.message).group(1)
            except (OSError, KeyboardInterrupt):
                break
        self.socket.close()

    def print_all_help(self):
        print()
        print("Usage:")
        print("    help")
        print("        Show this help message.")
        print("    logout")
        print("        Exit the chat program.")
        for command in [
            LoginCommand, NewUserCommand, SendAllCommand, SendDirectCommand, WhoCommand
        ]:
            print(command.help())

    def print_help(self, command: Command):
        print("Usage:")
        print(command.help())


if __name__ == "__main__":
    version = 2
    client = Client(HOST, PORT, version=version)
    client.connect()