"""Interactive client for the CMPT 352 chatroom protocol."""

from __future__ import annotations

import argparse
import queue
import re
import socket
import threading
from typing import Optional

# start with python chatroom_client.py [host] [port] --username Alice

MAX_LINE_BYTES = 8192
MAX_MESSAGE_CHARS = 1000
MAX_USERNAME_CHARS = 16
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9]+$")

STATUS_MESSAGES = {
    100: "joined the chatroom",
    101: "username is already in use",
    102: "username is longer than 16 characters",
    103: "username contains an invalid character",
    104: "username is missing",
    200: "exited the chatroom",
    300: "public message accepted",
    301: "public message is longer than 1000 characters",
    400: "private message accepted",
    401: "recipient is not in the chatroom",
    402: "private message is longer than 1000 characters",
    403: "recipient username is invalid",
    500: "malformed command or invalid session state",
}


def valid_username(username: str) -> bool:
    """Return whether username meets the protocol's username requirements."""
    return (
        bool(username)
        and len(username) <= MAX_USERNAME_CHARS
        and USERNAME_PATTERN.fullmatch(username) is not None
    )


def valid_message(message: str) -> bool:
    """Return whether message meets the protocol's message requirements."""
    return (
        len(message) <= MAX_MESSAGE_CHARS
        and "\r" not in message
        and "\n" not in message
    )


def format_incoming(line: str) -> str:
    """Format a server push for display without changing its protocol content."""
    if line.startswith("PUBLIC "):
        sender, _, message = line[7:].partition(" ")
        return f"[public] {sender}: {message}"
    if line.startswith("PRIVATE "):
        sender, _, message = line[8:].partition(" ")
        return f"[private] {sender}: {message}"
    if line.startswith("JOINED "):
        return f"* {line[7:]} joined the chatroom"
    if line.startswith("LEFT "):
        return f"* {line[5:]} left the chatroom"
    return line


class ChatClient:
    """TCP client that separates status replies from asynchronous server pushes."""

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self._reader: Optional[threading.Thread] = None
        self._send_lock = threading.Lock()
        self._status_codes: queue.Queue[Optional[int]] = queue.Queue()
        self._closed = threading.Event()

    def connect(self) -> None:
        self.socket = socket.create_connection((self.host, self.port))
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def send_command(self, command: str) -> int:
        if "\r" in command or "\n" in command:
            raise ValueError("commands cannot contain carriage returns or line feeds")
        if len(command.encode("utf-8")) + 2 > MAX_LINE_BYTES:
            raise ValueError("command exceeds the protocol's 8192-byte line limit")
        if self.socket is None:
            raise ConnectionError("client is not connected")
        with self._send_lock:
            self.socket.sendall(command.encode("utf-8") + b"\r\n")
        status = self._status_codes.get()
        if status is None:
            raise ConnectionError("server closed the connection before replying")
        return status

    def close(self) -> None:
        self._closed.set()
        if self.socket is not None:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self.socket.close()
            self.socket = None

    def _read_loop(self) -> None:
        assert self.socket is not None
        buffer = bytearray()
        try:
            while not self._closed.is_set():
                chunk = self.socket.recv(4096)
                if not chunk:
                    break
                buffer.extend(chunk)
                if len(buffer) > MAX_LINE_BYTES and b"\r\n" not in buffer:
                    raise ConnectionError("server sent an overlong protocol line")
                while True:
                    end = buffer.find(b"\r\n")
                    if end < 0:
                        break
                    line_bytes = bytes(buffer[:end])
                    del buffer[: end + 2]
                    self._handle_line(line_bytes)
        except (ConnectionError, OSError, UnicodeDecodeError) as error:
            if not self._closed.is_set():
                print(f"\nConnection error: {error}")
        finally:
            self._closed.set()
            self._status_codes.put(None)

    def _handle_line(self, line_bytes: bytes) -> None:
        line = line_bytes.decode("utf-8")
        if len(line_bytes) == 3 and line.isdecimal():
            status = int(line)
            self._status_codes.put(status)
            description = STATUS_MESSAGES.get(status, "unknown status")
            print(f"\n[status {status:03d}] {description}")
            return
        print(f"\n{format_incoming(line)}")


def print_help() -> None:
    print(
        "Commands:\n"
        "  public <message>             send a message to everyone\n"
        "  private <user> <message>     send a message to one user\n"
        "  exit                         leave and disconnect\n"
        "  help                         show this help"
    )


def run_client(host: str, port: int, username: str) -> None:
    client = ChatClient(host, port)
    try:
        client.connect()
        status = client.send_command(f"JOIN {username}")
        if status != 100:
            return

        print_help()
        while not client._closed.is_set():
            try:
                command = input("> ")
            except EOFError:
                command = "exit"
            if not command:
                continue
            if command == "help":
                print_help()
                continue
            if command == "exit":
                client.send_command("EXIT")
                break
            if command.startswith("public "):
                message = command[7:]
                if not valid_message(message):
                    print("Message must be at most 1000 characters and contain no CR/LF.")
                    continue
                client.send_command(f"PUBLIC {message}")
                continue
            if command.startswith("private "):
                arguments = command[8:]
                recipient, separator, message = arguments.partition(" ")
                if not separator or not valid_username(recipient):
                    print("Private messages require a valid recipient username.")
                    continue
                if not valid_message(message):
                    print("Message must be at most 1000 characters and contain no CR/LF.")
                    continue
                client.send_command(f"PRIVATE {recipient} {message}")
                continue
            print("Unknown command. Type 'help' for available commands.")
    except (ConnectionError, OSError, ValueError) as error:
        print(f"Client error: {error}")
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Chatroom protocol client")
    parser.add_argument("host", nargs="?", default="127.0.0.1")
    parser.add_argument("port", nargs="?", type=int, default=3500)
    parser.add_argument("-u", "--username", help="username to join with")
    arguments = parser.parse_args()

    username = arguments.username or input("Username: ")
    if not valid_username(username):
        parser.error("username must be 1-16 ASCII letters or digits")
    run_client(arguments.host, arguments.port, username)


if __name__ == "__main__":
    main()
