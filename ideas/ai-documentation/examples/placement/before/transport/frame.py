from dataclasses import dataclass


@dataclass(frozen=True)
class Frame:
    version: int
    flags: int
    request_id: int
    payload: bytes
