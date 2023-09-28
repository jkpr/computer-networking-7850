import socket
import threading
from collections import defaultdict

import db
from command import COMMAND_LOOKUP, Command
from server_message import ServerMessage


HOST = "127.0.0.1"
PORT = 65432


class Server:

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.connections = []
        self.current_users = {}
        self.send_locks = defaultdict(threading.Semaphore)
        self.server_socket = None

    def get_user_by_socket(self, client_socket: socket.socket) -> str | None:
        for user_id, current_socket in self.current_users.items():
            if current_socket is client_socket:
                return user_id
        return None

    def accept_connections(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen()
        print(f"Chat server running on {self.host}, port {self.port}")
        while True:
            try:    
                client_socket, client_address = self.server_socket.accept()
                print(f"Accepted connection from {client_address}")
                self.connections.append(client_socket)
                threading.Thread(target=self.handle_client, args=[client_socket]).start()
            except KeyboardInterrupt:
                break
        print("Shutting down server")
        self.server_socket.close()
        self.disconnect_all()

    def disconnect(self, client_socket):
        if client_socket.fileno() < 0:
            return
        print(f"Client disconnected: {client_socket.getpeername()}")
        if client_socket in self.connections:
            self.connections.remove(client_socket)
        username_to_remove = self.get_user_by_socket(client_socket)
        self.current_users.pop(username_to_remove, None)
        client_socket.close()
    
    def disconnect_all(self):
        for client_socket in self.connections:
            print(f"Client disconnected: {client_socket.getpeername()}")
            client_socket.close()

    def handle_client(self, client_socket):
        while True:
            try:
                command_type = client_socket.recv(1).decode(Command.ENCODING)
                if not command_type:
                    break
                elif command_type not in COMMAND_LOOKUP:
                    raise ValueError(f"Unrecognized command_type: {command_type}")
                command = COMMAND_LOOKUP[command_type].from_socket(client_socket)
                print(f"Received from {client_socket.getpeername()}: {command!r}")
                command.execute(server)
            except (KeyboardInterrupt, OSError) as err:
                # print(repr(err))
                # return
                break
        self.disconnect(client_socket)
    
    def authenticate(self, user_id: str, password: str) -> bool:
        return db.user_and_password_exists(user_id, password)
    
    def login(self, user_id: str, client_socket: socket.socket):
        self.current_users[user_id] = client_socket

    def create_user(self, user_id: str, password: str) -> bool:
        return db.insert_new_user_and_password(user_id, password)
    
    def get_all_connected_users(self) -> list[str]:
        return sorted(self.current_users, key=str.lower)
    
    def is_user_connected(self, user_id) -> bool:
        return user_id in self.current_users
    
    def broadcast(self, server_message: ServerMessage):
        for client_socket in self.current_users.values():
            self.send(client_socket, server_message)

    def direct_message(self, user_id: str, server_message: ServerMessage):
        client_socket = self.current_users.get(user_id)
        if client_socket:
            self.send(client_socket, server_message)

    def send(self, client_socket: socket.socket, server_message: ServerMessage):
        with self.send_locks[id(socket)]:
            client_socket.sendall(server_message.to_bytes())


if __name__ == "__main__":
    server = Server(HOST, PORT)
    server.accept_connections()
