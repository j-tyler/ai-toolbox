from transport.frame import Frame


def decode(data: bytes) -> Frame:
    if len(data) < 8:
        raise ValueError("Frame is shorter than its 8-byte header")
    version = data[0]
    flags = data[1]
    length = int.from_bytes(data[2:4], "big")
    request_id = int.from_bytes(data[4:8], "big")
    if len(data) != 8 + length:
        raise ValueError("Payload size does not match the header length")
    return Frame(version, flags, request_id, data[8:])
