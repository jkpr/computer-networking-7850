import argparse
import socket
import threading

from command import (
    Command,
    ConnectCommand,
    DisconnectCommand,
    LoginCommand,
    NewUserCommand,
    PrintCommand,
    SendAllCommand,
    SendDirectCommand,
    UserIdCommand,
    WhoCommand,
)

from settings import HOST, SERVER_PORT


class Client:

    def __init__(self, server, port, version, debug):
        self.server = server
        self.port = port
        self.version = version
        self.debug = debug
        self.socket = None
        self.current_user = None
    
    def main(self):
        version_text = {1: "One", 2: "Two"}.get(self.version)
        print(f"My chat room client. Version {version_text}.")
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server, self.port))
            if self.debug:
                print(f"Connected to chat server at {self.server} port {self.port}")
                print(f"Running chat client version {self.version}")
            threads = [
                threading.Thread(target=self.input_loop, daemon=True),
                threading.Thread(target=self.receive_messages, daemon=True),
            ]
            ConnectCommand(self.socket, str(self.version)).request()
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        except ConnectionError:
            print("The chat client is unable to connect to the chat server.")
            print(f"Is the server running at {self.server}, port {self.port}?")
        except KeyboardInterrupt:
            pass
        finally:
            self.disconnect()

    def disconnect(self):
        self.socket.close()

    def input_loop(self):
        while True:
            if self.socket.fileno() < 0:
                break
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
                    case ["send"]:
                        if not self.current_user:
                            print("Denied. Please login first.")
                    case ["who"]:
                        command = WhoCommand(self.socket)
                        if self.current_user:
                            command.request()
                        else:
                            print(f"You must be logged in first to do that.")
                    case ["logout"]:
                        if self.version == 1 and self.current_user:
                            print(f"{self.current_user} left")
                        break
                    case _:
                        if raw_command:
                            print(f"Unknown command '{raw_command}'. Type help<Enter> to see chat commands")
            except OSError:
                print("Server has disconnected. Good-bye!")
                break
        self.disconnect()

    def receive_messages(self):
        receive_commands = [
            DisconnectCommand,
            PrintCommand,
            UserIdCommand,
        ]
        receive_commands_lookup = {command.identifier: command for command in receive_commands}
        while True:
            try:
                command_type = self.socket.recv(1).decode(Command.ENCODING)
                if not command_type:
                    break
                elif command_type not in receive_commands_lookup:
                    raise ValueError(f"Unrecognized command_type: {command_type}")
                command = receive_commands_lookup[command_type].from_socket(self.socket, client=self)
                command.execute()
            except (KeyboardInterrupt, OSError):
                break

    def print(self, message):
        print(message)

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

    def set_current_user(self, current_user):
        self.current_user = current_user


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="My chat room client",
        description="Run a group chat client",
    )
    parser.add_argument("--version", "-v", type=int, choices=[1, 2], default=2, help="Which version of the software")
    parser.add_argument("--host", "-H", default=HOST, help="Which host address or host name to use")
    parser.add_argument("--port", "-p", default=SERVER_PORT, help="Which port to use")
    parser.add_argument("--debug", "-d", action="store_true", help="Which port to use")
    args = parser.parse_args()
    client = Client(HOST, SERVER_PORT, version=args.version, debug=args.debug)
    client.main()