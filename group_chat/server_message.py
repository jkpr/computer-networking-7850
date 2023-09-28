from dataclasses import dataclass

ENCODING = "utf-8"
HEADER_WIDTH = 4


class PreambleStyle:
    NORMAL = "A"


class Preamble:
    DM_FORMAT = "[{who}]"
    PUBLIC_FORMAT = "({who})"
    FROM_SERVER = DM_FORMAT.format(who="SERVER")

    @staticmethod
    def dm_from(who):
        return Preamble.DM_FORMAT.format(who=who)
    
    @staticmethod
    def public_from(who):
        return Preamble.PUBLIC_FORMAT.format(who=who)


@dataclass
class ServerMessage:
    """
    Every response knows:
    
    Two four byte fields to know the lengths of those fields

    2. Preamble
    3. Message
    
    """
    identifier: str
    success: bool
    preamble: str
    message: str
    
    def to_bytes(self):
        fixed_items = [item.encode(ENCODING) for item in (self.identifier, str(int(self.success)))]
        variable_items = [item.encode(ENCODING) for item in (self.preamble, self.message)]
        headers = [
            f"{len(item):>{HEADER_WIDTH}}".encode(ENCODING) for item in variable_items
        ]
        return b''.join([*fixed_items, *headers, *variable_items])
    
    @staticmethod
    def socket_read_bytes(socket, count):
        chunks = []
        total_received = 0
        while total_received < count:
            chunk = socket.recv(min(count - total_received, 1024))
            if not chunk:
                return None
            chunks.append(chunk)
            total_received += len(chunk)
        return b''.join(chunks)

    @classmethod
    def from_socket(cls, socket):
        chunk = cls.socket_read_bytes(socket, 2)
        if not chunk:
            return None
        identifier = chr(chunk[0])
        success = bool(int(chr(chunk[1])))
        header_lengths = cls.socket_read_bytes(socket, 2*HEADER_WIDTH)
        preamble_length = int(header_lengths[:4].decode(ENCODING))
        message_length = int(header_lengths[4:].decode(ENCODING))
        body_bytes = cls.socket_read_bytes(socket, preamble_length + message_length)
        preamble = body_bytes[:preamble_length].decode(ENCODING)
        message = body_bytes[preamble_length:].decode(ENCODING)
        return cls(identifier, success, preamble, message)
