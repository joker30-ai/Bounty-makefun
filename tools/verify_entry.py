#!/usr/bin/env python3
"""Check the PNG and run the real entrypoint twice through /output."""

import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[1]


def inspect_png(raw):
    if raw[:8] != b"\x89PNG\r\n\x1a\n" or len(raw) >= 1048576:
        raise ValueError("Expected a PNG strictly below 1 MiB")
    position, chunks, compressed, header = 8, [], bytearray(), None
    while position < len(raw):
        length = struct.unpack_from(">I", raw, position)[0]
        end = position + length + 12
        if end > len(raw):
            raise ValueError("Truncated PNG chunk")
        kind = raw[position + 4:position + 8]
        data = raw[position + 8:end - 4]
        crc = struct.unpack_from(">I", raw, end - 4)[0]
        if zlib.crc32(kind + data) & 0xFFFFFFFF != crc:
            raise ValueError(f"Invalid {kind!r} checksum")
        chunks.append(kind.decode("ascii"))
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", data)
        elif kind == b"IDAT":
            compressed.extend(data)
        position = end
        if kind == b"IEND":
            break
    if chunks[0] != "IHDR" or chunks[-1] != "IEND" or position != len(raw):
        raise ValueError("PNG must have a complete header and terminator, with no trailing bytes")
    width, height, depth, color, compression, filtering, interlace = header
    if (width, height) != (1024, 1024) or depth != 8 or color not in (2, 6):
        raise ValueError("Expected a 1024 × 1024, 8-bit RGB/RGBA PNG")
    if (compression, filtering, interlace) != (0, 0, 0):
        raise ValueError("Unexpected PNG compression/filter/interlace method")
    decoder = zlib.decompressobj()
    decoded = decoder.decompress(compressed) + decoder.flush()
    stride = width * (3 if color == 2 else 4) + 1
    if not decoder.eof or decoder.unused_data or len(decoded) != stride * height:
        raise ValueError("Incomplete or oversized PNG pixel data")
    if any(decoded[row * stride] > 4 for row in range(height)):
        raise ValueError("Invalid PNG row filter")
    return {"dimensions": [width, height], "bytes": len(raw), "valid_chunk_checksums": len(chunks), "decoded_pixel_bytes": len(decoded)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", default="node", help="Node 22 executable")
    args = parser.parse_args()
    version = subprocess.check_output([args.node, "--version"], text=True).strip()
    if not version.startswith("v22."):
        raise SystemExit(f"Use the competition's Node 22 runtime; found {version}")
    source = (ROOT / "assets" / "entry.png").read_bytes()
    result = inspect_png(source)
    hashes = []
    for _ in range(2):
        subprocess.run([args.node, "main.ts"], cwd=ROOT, check=True, timeout=60)
        output = Path("/output/entry.png")
        rendered = output.read_bytes()
        if rendered != source:
            raise ValueError("Entrypoint changed the approved image bytes")
        if output.stat().st_mode & 0o777 != 0o644:
            raise ValueError("Grader output must have mode 0644")
        hashes.append(hashlib.sha256(rendered).hexdigest())
    if hashes[0] != hashes[1]:
        raise ValueError("Entrypoint is not deterministic")
    print(json.dumps({**result, "runtime": version, "output": "/output/entry.png", "run_sha256": hashes, "identical_bytes": True}, indent=2))


if __name__ == "__main__":
    main()
