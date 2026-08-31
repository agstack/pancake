# SPDX-License-Identifier: EUPL-1.2
# Copyright (c) 2026 AgStack project contributors.
# Licensed under the EUPL, Version 1.2; see the LICENSE file for the full text.

"""StatusList2021-style revocation bitstring.

A compact revocation list: one bit per issued credential, indexed by the
``status.status_list.idx`` claim. Bit 1 = revoked. Published as a
zlib-compressed, base64url-encoded bitstring.
"""
from __future__ import annotations

import base64
import zlib

DEFAULT_SIZE = 65536  # bits; hub-allocated range size for one issuer


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


class StatusList:
    def __init__(self, size: int = DEFAULT_SIZE):
        if size <= 0 or size % 8 != 0:
            raise ValueError("size must be a positive multiple of 8")
        self.size = size
        self._bits = bytearray(size // 8)

    def _check(self, index: int) -> None:
        if not 0 <= index < self.size:
            raise IndexError(f"status index {index} out of range [0, {self.size})")

    def set(self, index: int, revoked: bool = True) -> None:
        self._check(index)
        byte, bit = divmod(index, 8)
        if revoked:
            self._bits[byte] |= 1 << bit
        else:
            self._bits[byte] &= ~(1 << bit)

    def is_revoked(self, index: int) -> bool:
        self._check(index)
        byte, bit = divmod(index, 8)
        return bool(self._bits[byte] & (1 << bit))

    def encode(self) -> str:
        return _b64url(zlib.compress(bytes(self._bits)))

    @classmethod
    def decode(cls, encoded: str) -> "StatusList":
        raw = zlib.decompress(_b64url_decode(encoded))
        sl = cls(size=len(raw) * 8)
        sl._bits = bytearray(raw)
        return sl

def is_revoked(status: dict, local_path: str = None) -> bool:
    import os
    import json
    import urllib.request
    
    uri = status.get("uri")
    idx = status.get("idx")
    if uri is None or idx is None:
        raise ValueError("status missing uri or idx")
        
    status_list_data = None
    if local_path:
        filepath = os.path.join(local_path, "status_list.txt")
        if not os.path.exists(filepath):
            filename = uri.rstrip('/').split('/')[-1]
            filepath = os.path.join(local_path, filename)
        with open(filepath, "rb") as f:
            status_list_data = f.read()
    else:
        req = urllib.request.Request(uri, headers={'Accept': 'application/statuslist+jwt'})
        with urllib.request.urlopen(req, timeout=10) as response:
            status_list_data = response.read()
            
    # Try parsing as JSON first
    encoded = None
    try:
        sl_json = json.loads(status_list_data)
        encoded = sl_json.get("encoded") or sl_json.get("status_list", {}).get("lst")
    except Exception:
        pass
        
    if not encoded:
        encoded = status_list_data.decode('utf-8').strip()
        
    sl = StatusList.decode(encoded)
    return sl.is_revoked(idx)
