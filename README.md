# Chatroom client

This is a Python client for the TCP chatroom server in `chatroom_server`. It
uses the protocol's UTF-8 and CRLF line format and handles pushed messages on a
background reader thread, so pushed messages do not get confused with status
replies.

Start the Rust server, then run:

```text
python chatroom_client.py [host] [port] --username Alice
```

The defaults are `127.0.0.1` and port `3500`. Interactive commands are:

- `public <message>`
- `private <username> <message>`
- `exit`
- `help`

Run the focused tests from this directory with:

```text
python -m unittest -v
```
