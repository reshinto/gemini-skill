"""Raw HTTP backend package — urllib-based implementation of the Transport
Protocol.

Modules:
    client.py    — Low-level urllib functions (api_call, stream, upload).
    transport.py — RawHttpTransport class wrapping the functions in client.py
                   into the Transport Protocol shape the coordinator expects.
"""
