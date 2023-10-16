"""
Group chat server.

Supports version 1 (echo server) and version 2 (full group chat).
"""

import argparse
import socket
import threading
from collections import defaultdict

from .db import insert_new_user_and_password, user_and_password_exists
from .command import COMMAND_LOOKUP, Command, DisconnectCommand, PrintCommand
from .settings import HOST, SERVER_PORT, MAX_CONNECTIONS


class Server:

    def __init__(self, host, port, version, max_connections, debug):
        self.host = host
        self.port = port
        self.version = version
        self.max_connections = max_connections
        self.debug = debug
        self.connections = []
        self.current_users = {}
        self.locks = defaultdict(threading.Semaphore)
        self.server_socket = None

    def get_user_by_socket(self, client_socket: socket.socket) -> str | None:
        """Return the user ID for a given socket or None if not found."""
        for user_id, current_socket in self.current_users.items():
            if current_socket is client_socket:
                return user_id
        return None

    def accept_connections(self):
        """Start to run the server by accepting connections."""
        version_text = {1: "One", 2: "Two"}.get(self.version)
        print(f"My chat room server. Version {version_text}.")
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        if self.debug:
            print(f"Chat server running on {self.host}, port {self.port}")
        while True:
            try:    
                client_socket, client_address = self.server_socket.accept()
                if self.debug:
                    print(f"Accepted connection from {client_address}")
                if self.version == 2 and len(self.connections) < self.max_connections or self.version == 1:
                    self.connections.append(client_socket)
                    threading.Thread(target=self.handle_client, args=[client_socket]).start()
                else:
                    message = "Server cannot accept new connections. Try later."
                    DisconnectCommand(client_socket, message, server=self).request(with_lock=True)
                    self.disconnect(client_socket)
            except KeyboardInterrupt:
                break
        print("Shutting down server")
        self.server_socket.close()
        self.disconnect_all()

    def disconnect(self, client_socket):
        """Disconnect a client socket."""
        if client_socket.fileno() < 0:
            return
        if self.debug:
            print(f"Client disconnected: {client_socket.getpeername()}")
        if client_socket in self.connections:
            self.connections.remove(client_socket)
        username_to_remove = self.get_user_by_socket(client_socket)
        self.current_users.pop(username_to_remove, None)
        client_socket.close()
        if username_to_remove:
            self.print(f"{username_to_remove} logout")
            self.broadcast(f"{username_to_remove} left")
    
    def disconnect_all(self):
        """Disconnect all sockets in preparation for shutting down."""
        for client_socket in self.connections:
            if self.debug:
                print(f"Client disconnected: {client_socket.getpeername()}")
            client_socket.close()

    def handle_client(self, client_socket):
        """Handle a client's messages and react."""
        while True:
            try:
                command_type = client_socket.recv(1).decode(Command.ENCODING)
                if not command_type:
                    break
                elif command_type not in COMMAND_LOOKUP:
                    raise ValueError(f"Unrecognized command_type: {command_type}")
                command = COMMAND_LOOKUP[command_type].from_socket(client_socket, server=self)
                if self.debug:
                    print(f"Received from {client_socket.getpeername()}: {command!r}")
                command.execute()
            except (KeyboardInterrupt, OSError):
                break
        self.disconnect(client_socket)
    
    def authenticate(self, user_id: str, password: str) -> bool:
        """Check if the given user ID and password exist in the DB."""
        return user_and_password_exists(user_id, password)
    
    def login(self, user_id: str, client_socket: socket.socket):
        """Associate the given user ID with the given client socket."""
        self.current_users[user_id] = client_socket

    def create_user(self, user_id: str, password: str) -> bool:
        """Create a new user in the DB."""
        return insert_new_user_and_password(user_id, password)
    
    def get_all_connected_users(self) -> list[str]:
        """Return a list of all connected users IDs."""
        return sorted(self.current_users, key=str.lower)
    
    def is_user_connected(self, user_id) -> bool:
        """Check if the given user ID is currently connected."""
        return user_id in self.current_users
    
    def broadcast(self, message: str):
        """Send a message to all connected users."""
        for socket in self.current_users.values():
            PrintCommand(socket, message, server=self).request(with_lock=True)

    def print(self, message):
        """Print a message for server logs."""
        print(message)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="My chat room server",
        description="Run a group chat server",
    )
    parser.add_argument("--version", "-v", type=int, choices=[1, 2], default=2, help="Which version of the software")
    parser.add_argument("--host", "-H", default=HOST, help="Which host address or host name to use")
    parser.add_argument("--port", "-p", default=SERVER_PORT, help="Which port to use")
    parser.add_argument("--max-connections", "-m", default=MAX_CONNECTIONS, type=int, help="Only applies to version 2")
    parser.add_argument("--debug", "-d", action="store_true", help="Show debug information")
    args = parser.parse_args()
    max_connections = None if args.version == 1 else args.max_connections
    server = Server(args.host, args.port, args.version, max_connections, args.debug)
    server.accept_connections()
