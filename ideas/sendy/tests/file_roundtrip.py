"""Verify the README's file extraction recipe using real processes and SHA-256."""
from pathlib import Path
import subprocess
import tempfile


def file_roundtrip(binary, env):
    # env is the acceptance suite's isolated store, never the user's live store.
    fixtures = {
        "no-final-newline": b"first line\nlast line",
        "trailing-newlines": b"first line\nlast line\n\n\n",
        "mixed-line-endings": b"CRLF\r\nCR\rLF\nend\r\n",
        "escaping-and-whitespace": b'  \t{"quote":"\\\"", "slash":"\\\\", "literal":"\\n"}\n$100 <>& `literal`\t ',
        "unicode-and-nul": "\ufeff世界 😀 e\u0301\u2028\u2029\x00end".encode("utf-8"),
        "long-line": b"long\\line\t" * 12000 + b"\n",
    }
    with tempfile.TemporaryDirectory(prefix="sendy-file-roundtrip-") as scratch:
        root = Path(scratch)

        def checked(command, **kwargs):
            p = subprocess.run(command, cwd=root, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, timeout=10, **kwargs)
            assert p.returncode == 0 and not p.stderr, (
                command, p.returncode, p.stdout, p.stderr)
            return p.stdout

        def checksum(path):
            return checked(["sha256sum", str(path)]).split()[0]

        for name, original in fixtures.items():
            source = root / (name + ".source")
            received = root / (name + ".received")
            returned = root / (name + ".returned")
            source.write_bytes(original)
            expected_digest = checksum(source)
            id = checked([str(binary), "create", "1"]).decode().strip()
            # File descriptors implement the README's < source > returned.
            with source.open("rb") as input_file, returned.open("wb") as output_file:
                child = subprocess.Popen([str(binary), "submit", id], cwd=root, env=env,
                                         stdin=input_file, stdout=output_file,
                                         stderr=subprocess.PIPE)
                try:
                    # Execute the documented Bash pipeline, not a Python JSON
                    # reconstruction. Positional arguments keep paths out of code.
                    checked([
                        "bash", "-c",
                        'set -o pipefail\n'
                        '"$1" wait "$2" --timeout 1 |\n'
                        '  jq -e -j --arg id "$2" \\\n'
                        "    '.results[] | select(.id == $id) | .message' > \"$3\"",
                        "sendy-file-roundtrip", str(binary), id, str(received),
                    ])
                    assert child.poll() is None, "submit did not stay blocked"
                    assert checksum(received) == expected_digest, (name, "receive SHA-256")
                    assert received.read_bytes() == original, (name, "receive bytes")
                    # Return the received file itself, proving both transfer
                    # directions preserve the original SHA-256 file checksum.
                    with received.open("rb") as reply_file:
                        assert checked([str(binary), "reply", id], stdin=reply_file) == b""
                    _, diagnostics = child.communicate(timeout=10)
                    assert child.returncode == 0 and not diagnostics, (
                        name, child.returncode, diagnostics)
                finally:
                    if child.poll() is None:
                        child.kill()
                        child.communicate()
                    checked([str(binary), "close", id])
            assert checksum(returned) == expected_digest, (name, "round-trip SHA-256")
            assert returned.read_bytes() == original, (name, "round-trip bytes")
    print(f"PASS: {len(fixtures)} file round trips through Bash/jq; original, received, "
          "and returned SHA-256 checksums and bytes match", flush=True)
