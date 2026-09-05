# Select a layout before placing it

These are focused selection comparisons, not another artifact-generation run.
The complete supplied artifact document for the retained case is
[`placement/artifacts.md`](../placement/artifacts.md#packet-diagrams).

| Code to inspect | Decision and evidence |
|---|---|
| [`small_frame.py`](small_frame.py) | Omit a new packet diagram. The complete short encoder and decoder are adjacent: `data[2:4]`, `data[4:8]`, the length check and the return show offsets, byte order and payload origin in one open file. This is the original compact shape; its accurate layout was allowable as a supplied placement candidate, but a generator can reject the redundant redraw. |
| [`frame.proto`](frame.proto) | Omit a layout redraw. The protobuf declaration is the format source of truth. Its numbered tags are field identifiers, not fixed byte offsets; a packet with the handwritten codec's offsets would be false for this schema. No protobuf runtime is needed to inspect this declaration. |
| [`transport/frame.py`](../placement/before/transport/frame.py), [`encoder.py`](../placement/before/transport/encoder.py), [`decoder.py`](../placement/before/transport/decoder.py) | Retain the supplied handwritten header. The definition has no `length` field or wire widths. Encoding synthesizes length and serializes the fields; decoding establishes offset slices and rejects a total-length mismatch. Reading the definition alone cannot recover that contract. |

The retained diagram preserves the eight-byte origin, field widths, big-endian
interpretation, and length excluding the header. Its definition owner and both
codecs point to one full copy. It omits the variable payload explicitly without
shifting the header fields.

This resolves the small example's generation ambiguity through different,
inspectable source structure. It does not claim that the guides gained a new
exception for every handwritten codec, or that merely splitting a file always
makes a diagram useful. The question remains whether the collected contract
adds information at the reader's location.
