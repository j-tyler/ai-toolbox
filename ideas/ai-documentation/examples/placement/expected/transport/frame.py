# map
# owns: message frame representation
# format: message frame header, diagram above transport.frame.Frame
# end map

from dataclasses import dataclass


# packet-beta
# %% format: message frame header
# %% selected view; omits: the variable-length payload beginning at byte 8; omissions do not establish absence
# %% Bit offsets count from the frame start. length and request_id use big-endian byte order.
# %% length is the payload size in bytes, excluding these 8 header bytes.
# %% definition: transport.frame.Frame (transport/frame.py)
# %% codecs: transport.encoder.encode (transport/encoder.py), transport.decoder.decode (transport/decoder.py)
# 0-7: "version"
# 8-15: "flags"
# 16-31: "length"
# 32-63: "request_id"
@dataclass(frozen=True)
class Frame:
    version: int
    flags: int
    request_id: int
    payload: bytes
