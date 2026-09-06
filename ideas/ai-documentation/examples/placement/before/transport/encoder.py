from transport.frame import Frame


def encode(frame: Frame) -> bytes:
    return (
        bytes((frame.version, frame.flags))
        + len(frame.payload).to_bytes(2, "big")
        + frame.request_id.to_bytes(4, "big")
        + frame.payload
    )
