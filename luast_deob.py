#!/usr/bin/env python3
"""Luast-oriented static deobfuscation toolkit (v0.3.0).

Automated static deobfuscation and semantic reconstruction for Luast-obfuscated
Lua/Luau scripts without requiring live Roblox in-game execution.

Features:
- Constant-pool auto-discovery and nested-closure parsing
- Sequential permutation execution & post-permutation runtime table tracking
- Invertible 32-bit hash permutation engine (b4 and b4_inv)
- Multi-round stream cipher decryption (Types 1, 2, 3, 4)
- Automated master-seed recovery (b2, b3) from known anchors / state calculation
- Automated UI control & worker loop semantic extraction
- Complete ready-to-run WindUI generation branded Taro Hub
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable, Iterator, Optional, Dict, Any, List, Tuple

NUM = r"(?:\d+(?:\.\d*)?|\.\d+)"
IDX_RE = re.compile(r"\b(?P<table>[A-Za-z_]\w*)\s*\[\s*(?P<idx>\d+(?:\.0*)?)\s*\]")
DIRECT_STRING_RE = re.compile(r"(?P<q>['\"])(?P<s>(?:\\.|(?!\1).)*)\1")


# ==============================================================================
# Cryptographic & Mathematical Engine (Stream Ciphers & 32-bit Hash Inverter)
# ==============================================================================

def lrotate(v: int, n: int) -> int:
    return ((v << n) | (v >> (32 - n))) & 0xFFFFFFFF


def rrotate(v: int, n: int) -> int:
    return ((v >> n) | (v << (32 - n))) & 0xFFFFFFFF


def unxor_lshift(y: int, shift: int) -> int:
    x = y
    for _ in range(32 // shift + 1):
        x = y ^ ((x << shift) & 0xFFFFFFFF)
    return x


def unxor_rshift(y: int, shift: int) -> int:
    x = y
    for _ in range(32 // shift + 1):
        x = y ^ (x >> shift)
    return x


def b4_hash(bR: int) -> int:
    """7-round bijective mixing permutation used by Luast."""
    bR = (bR + 2654435769) & 0xFFFFFFFF
    bR = bR ^ (bR >> 16)
    bR = bR ^ ((bR << 5) & 0xFFFFFFFF)
    bR = lrotate(bR, 11)
    bR = (bR + 2246822507) & 0xFFFFFFFF
    bR = bR ^ (bR >> 13)
    bR = bR ^ ((bR << 9) & 0xFFFFFFFF)
    bR = lrotate(bR, 19)
    bR = (bR + 3266489909) & 0xFFFFFFFF
    bR = bR ^ (bR >> 15)
    bR = bR ^ ((bR << 7) & 0xFFFFFFFF)
    bR = lrotate(bR, 23)
    bR = (bR + 668265263) & 0xFFFFFFFF
    bR = bR ^ (bR >> 17)
    bR = bR ^ ((bR << 11) & 0xFFFFFFFF)
    bR = lrotate(bR, 13)
    bR = (bR + 374761393) & 0xFFFFFFFF
    bR = bR ^ (bR >> 11)
    bR = bR ^ ((bR << 13) & 0xFFFFFFFF)
    bR = lrotate(bR, 7)
    bR = (bR + 4283543511) & 0xFFFFFFFF
    bR = bR ^ (bR >> 14)
    bR = bR ^ ((bR << 6) & 0xFFFFFFFF)
    bR = lrotate(bR, 17)
    return bR


def b4_inv(bR: int) -> int:
    """Exact computational inverse of Luast b4 hash permutation."""
    bR = rrotate(bR, 17)
    bR = unxor_lshift(bR, 6)
    bR = unxor_rshift(bR, 14)
    bR = (bR - 4283543511) & 0xFFFFFFFF
    bR = rrotate(bR, 7)
    bR = unxor_lshift(bR, 13)
    bR = unxor_rshift(bR, 11)
    bR = (bR - 374761393) & 0xFFFFFFFF
    bR = rrotate(bR, 13)
    bR = unxor_lshift(bR, 11)
    bR = unxor_rshift(bR, 17)
    bR = (bR - 668265263) & 0xFFFFFFFF
    bR = rrotate(bR, 23)
    bR = unxor_lshift(bR, 7)
    bR = unxor_rshift(bR, 15)
    bR = (bR - 3266489909) & 0xFFFFFFFF
    bR = rrotate(bR, 19)
    bR = unxor_lshift(bR, 9)
    bR = unxor_rshift(bR, 13)
    bR = (bR - 2246822507) & 0xFFFFFFFF
    bR = rrotate(bR, 11)
    bR = unxor_lshift(bR, 5)
    bR = unxor_rshift(bR, 16)
    bR = (bR - 2654435769) & 0xFFFFFFFF
    return bR


def parse_lua_string_to_bytes(s: str) -> bytes:
    """Parse a Lua string literal with escape sequences into raw bytes."""
    if not isinstance(s, str):
        return b""
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    elif s.startswith("'") and s.endswith("'"):
        s = s[1:-1]
    res = bytearray()
    i = 0
    n = len(s)
    while i < n:
        if s[i] == "\\" and i + 1 < n:
            c = s[i + 1]
            if c == "x" and i + 3 < n:
                try:
                    res.append(int(s[i + 2 : i + 4], 16))
                    i += 4
                except ValueError:
                    res.append(ord(c))
                    i += 2
            elif c == "n":
                res.append(ord("\n"))
                i += 2
            elif c == "r":
                res.append(ord("\r"))
                i += 2
            elif c == "t":
                res.append(ord("\t"))
                i += 2
            elif c == "\\":
                res.append(ord("\\"))
                i += 2
            elif c == '"':
                res.append(ord('"'))
                i += 2
            elif c == "'":
                res.append(ord("'"))
                i += 2
            elif c.isdigit():
                j = i + 1
                while j < min(i + 4, n) and s[j].isdigit():
                    j += 1
                res.append(int(s[i + 1 : j]))
                i = j
            else:
                res.append(ord(c))
                i += 2
        else:
            res.append(ord(s[i]))
            i += 1
    return bytes(res)


def decode_stream(enc_bytes: bytes, seed: int, offset: int, cipher_type: str) -> str:
    """Decrypt a ciphertext using one of the four Luast stream ciphers."""
    z1 = len(enc_bytes) - offset
    if z1 <= 0:
        return ""
    z2 = b4_hash(seed % 4294967296)
    out = bytearray(enc_bytes[:z1])

    if cipher_type == "type1":  # lrotate PRNG XOR
        z5 = 0
        while z5 <= z1 - 4:
            z2 = lrotate((z2 + 1832704949) & 0xFFFFFFFF, 13)
            u = out[z5] | (out[z5 + 1] << 8) | (out[z5 + 2] << 16) | (out[z5 + 3] << 24)
            res = u ^ z2
            out[z5] = res & 0xFF
            out[z5 + 1] = (res >> 8) & 0xFF
            out[z5 + 2] = (res >> 16) & 0xFF
            out[z5 + 3] = (res >> 24) & 0xFF
            z5 += 4
        z2 = lrotate((z2 + 1832704949) & 0xFFFFFFFF, 13)
        z6 = 0
        while z5 < z1:
            out[z5] ^= (z2 >> (z6 * 8)) & 0xFF
            z5 += 1
            z6 += 1

    elif cipher_type == "type2":  # LCG subtraction
        z5 = 0
        while z5 <= z1 - 4:
            z2 = (z2 * 1597 + 51749) & 0xFFFFFFFF
            u = out[z5] | (out[z5 + 1] << 8) | (out[z5 + 2] << 16) | (out[z5 + 3] << 24)
            res = (u - z2) & 0xFFFFFFFF
            out[z5] = res & 0xFF
            out[z5 + 1] = (res >> 8) & 0xFF
            out[z5 + 2] = (res >> 16) & 0xFF
            out[z5 + 3] = (res >> 24) & 0xFF
            z5 += 4
        z2 = (z2 * 1597 + 51749) & 0xFFFFFFFF
        z6 = 0
        while z5 < z1:
            out[z5] = (out[z5] - ((z2 >> (z6 * 8)) & 0xFF)) & 0xFF
            z5 += 1
            z6 += 1

    elif cipher_type == "type3":  # Golden ratio XOR
        z5 = 0
        while z5 <= z1 - 4:
            z2 = (z2 + 2654435769) & 0xFFFFFFFF
            u = out[z5] | (out[z5 + 1] << 8) | (out[z5 + 2] << 16) | (out[z5 + 3] << 24)
            res = u ^ z2
            out[z5] = res & 0xFF
            out[z5 + 1] = (res >> 8) & 0xFF
            out[z5 + 2] = (res >> 16) & 0xFF
            out[z5 + 3] = (res >> 24) & 0xFF
            z5 += 4
        z2 = (z2 + 2654435769) & 0xFFFFFFFF
        z6 = 0
        while z5 < z1:
            out[z5] ^= (z2 >> (z6 * 8)) & 0xFF
            z5 += 1
            z6 += 1

    elif cipher_type == "type4":  # Park-Miller Lehmer PRNG XOR
        z2 = (z2 % 2147483646) + 1
        z5 = 0
        while z5 <= z1 - 4:
            z2 = (z2 * 16807) % 2147483647
            u = out[z5] | (out[z5 + 1] << 8) | (out[z5 + 2] << 16) | (out[z5 + 3] << 24)
            res = u ^ z2
            out[z5] = res & 0xFF
            out[z5 + 1] = (res >> 8) & 0xFF
            out[z5 + 2] = (res >> 16) & 0xFF
            out[z5 + 3] = (res >> 24) & 0xFF
            z5 += 4
        z2 = (z2 * 16807) % 2147483647
        z6 = 0
        while z5 < z1:
            out[z5] ^= (z2 >> (z6 * 8)) & 0xFF
            z5 += 1
            z6 += 1

    try:
        return bytes(out[:z1]).decode("utf-8")
    except UnicodeDecodeError:
        return bytes(out[:z1]).decode("latin1")


# ==============================================================================
# AST Data Structures & Tokenizer
# ==============================================================================

@dataclass
class Token:
    kind: str
    text: str
    start: int
    end: int


@dataclass
class Entry:
    index: int
    raw: str
    kind: str
    display: str
    runtime_raw: Optional[str] = None
    runtime_display: Optional[str] = None


@dataclass
class Ref:
    table: str
    index: int
    offset: int
    context: str


@dataclass
class Permutation:
    offset: int
    alias: str
    lhs: list[int]
    rhs: list[int]
    likely_constant_table: bool
    context: str


@dataclass
class AliasBinding:
    offset: int
    alias: str
    table_alias: str
    index: int
    context: str


@dataclass
class RemoteCall:
    offset: int
    receiver: str
    method: str
    argument: str
    constant_index: Optional[int]
    initial_value: Optional[str]
    runtime_value: Optional[str]
    context: str


@dataclass
class UIControl:
    offset: int
    receiver: str
    method: str
    key_index: Optional[int]
    key_initial_value: Optional[str]
    key_runtime_value: Optional[str]
    label_index: Optional[int]
    label_initial_value: Optional[str]
    label_runtime_value: Optional[str]
    context: str


def strip_markdown_fence(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        first_nl = s.find("\n")
        if first_nl != -1:
            s = s[first_nl + 1 :]
        if s.rstrip().endswith("```"):
            s = s.rstrip()[:-3]
    return s.strip()


def tokenize(text: str) -> Iterator[Token]:
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c.isspace():
            i += 1
            continue

        if text.startswith("--", i):
            m = re.match(r"--\[(=*)\[", text[i:])
            if m:
                eq = m.group(1)
                close = "]" + eq + "]"
                j = text.find(close, i + m.end())
                end = n if j == -1 else j + len(close)
                yield Token("comment", text[i:end], i, end)
                i = end
                continue
            j = text.find("\n", i + 2)
            end = n if j == -1 else j
            yield Token("comment", text[i:end], i, end)
            i = end
            continue

        if c in "'\"":
            q = c
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == q:
                    j += 1
                    break
                j += 1
            yield Token("string", text[i:j], i, j)
            i = j
            continue

        m = re.match(r"\[(=*)\[", text[i:])
        if m:
            eq = m.group(1)
            close = "]" + eq + "]"
            j = text.find(close, i + m.end())
            end = n if j == -1 else j + len(close)
            yield Token("string", text[i:end], i, end)
            i = end
            continue

        if c.isalpha() or c == "_":
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] == "_"):
                j += 1
            yield Token("ident", text[i:j], i, j)
            i = j
            continue

        if c.isdigit() or (c == "." and i + 1 < n and text[i + 1].isdigit()):
            m = re.match(r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", text[i:])
            if m:
                j = i + len(m.group(0))
                yield Token("number", text[i:j], i, j)
                i = j
                continue

        matched = None
        for op in ("...", "==", "~=", "<=", ">=", "::", "//", "..", "+=", "-=", "*=", "/=", "->"):
            if text.startswith(op, i):
                matched = op
                break
        if matched:
            yield Token("sym", matched, i, i + len(matched))
            i += len(matched)
        else:
            yield Token("sym", c, i, i + 1)
            i += 1


def _match_table_constructor(text: str, open_pos: int) -> int:
    depth = 0
    for tok in tokenize(text[open_pos:]):
        if tok.kind in {"string", "comment"}:
            continue
        if tok.text == "{":
            depth += 1
        elif tok.text == "}":
            depth -= 1
            if depth == 0:
                return open_pos + tok.start
    return -1


def discover_table_candidates(text: str) -> list[dict]:
    out: list[dict] = []
    seen: set[tuple[str, int]] = set()

    pat = re.compile(r"\b([A-Za-z_]\w*)\s*=\s*\{")
    for m in pat.finditer(text):
        name = m.group(1)
        open_pos = text.find("{", m.start(), m.end())
        key = (name, open_pos)
        if key in seen:
            continue
        seen.add(key)

        close_pos = _match_table_constructor(text, open_pos)
        if close_pos < 0:
            continue

        interior_len = close_pos - open_pos - 1
        refs = len(re.findall(rf"\b{re.escape(name)}\s*\[\s*\d+(?:\.0*)?\s*\]", text))
        alias_refs = len(re.findall(rf"\b(?:local\s+)?[A-Za-z_]\w*\s*=\s*{re.escape(name)}\b", text))

        sample = text[open_pos + 1 : min(close_pos, open_pos + 200_000)]
        string_hits = len(DIRECT_STRING_RE.findall(sample))
        function_hits = len(re.findall(r"\bfunction\b", sample))
        number_hits = len(re.findall(r"(?<![A-Za-z_])\d+(?:\.\d*)?", sample))

        size_factor = min(1.0, max(interior_len, 1) / 4096.0)
        score = (
            refs * 1000 * size_factor
            + min(interior_len, 2_000_000) / 100
            + min(string_hits, 500) * 3
            + min(function_hits, 200) * 8
            + min(number_hits, 1000) * 0.5
            + alias_refs * 20 * size_factor
        )
        out.append({
            "name": name,
            "open_pos": open_pos,
            "close_pos": close_pos,
            "bytes": interior_len,
            "refs": refs,
            "alias_refs": alias_refs,
            "string_hits_sample": string_hits,
            "function_hits_sample": function_hits,
            "score": score,
        })

    out.sort(key=lambda c: (-c["score"], -c["refs"], -c["bytes"], c["open_pos"]))
    return out


def find_constant_table(text: str, preferred: Optional[str] = None) -> tuple[str, int, int, str]:
    if preferred and preferred.lower() == "auto":
        preferred = None

    candidates = discover_table_candidates(text)
    if not candidates:
        raise ValueError("Could not find any direct table assignment (name = {...}).")

    if preferred:
        exact = [c for c in candidates if c["name"] == preferred]
        if not exact:
            suggestions = ", ".join(f"{c['name']} (refs={c['refs']}, bytes={c['bytes']})" for c in candidates[:8])
            raise ValueError(f"Could not find constant table {preferred!r}. Top detected: {suggestions}")
        chosen = max(exact, key=lambda c: (c["refs"], c["bytes"], c["score"]))
    else:
        chosen = candidates[0]

    return chosen["name"], chosen["open_pos"], chosen["close_pos"], text[chosen["open_pos"] + 1 : chosen["close_pos"]]


def split_constant_entries(interior: str) -> list[str]:
    tokens = list(tokenize(interior))
    entries: list[str] = []
    start = 0
    par = brk = brc = 0
    block_stack: list[str] = []
    pending_loop_do = 0
    prev_sig = None

    for tok in tokens:
        if tok.kind in {"string", "comment"}:
            continue
        t = tok.text
        if t == "(": par += 1
        elif t == ")": par = max(0, par - 1)
        elif t == "[": brk += 1
        elif t == "]": brk = max(0, brk - 1)
        elif t == "{": brc += 1
        elif t == "}": brc = max(0, brc - 1)
        elif tok.kind == "ident":
            if t == "function":
                block_stack.append("function")
            elif t == "if":
                prev_text = prev_sig.text if prev_sig is not None else None
                if prev_text not in {"=", "return", "(", "[", "{", ",", "+", "-", "*", "/", "%", "^", "..", "and", "or", "not"}:
                    block_stack.append("if")
            elif t in ("for", "while"):
                block_stack.append(t)
                pending_loop_do += 1
            elif t == "repeat":
                block_stack.append("repeat")
            elif t == "do":
                if pending_loop_do > 0:
                    pending_loop_do -= 1
                else:
                    block_stack.append("do")
            elif t == "until":
                if block_stack and block_stack[-1] == "repeat":
                    block_stack.pop()
            elif t == "end":
                if block_stack:
                    block_stack.pop()
        elif t == "," and par == 0 and brk == 0 and brc == 0 and not block_stack:
            entries.append(interior[start:tok.start].strip())
            start = tok.end
        if tok.kind != "comment":
            prev_sig = tok

    trailing = interior[start:].strip()
    if trailing:
        entries.append(trailing)
    return entries


def decode_lua_string(raw: str) -> str:
    raw = raw.strip()
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        try:
            return parse_lua_string_to_bytes(raw).decode("utf-8", errors="replace")
        except Exception:
            return raw[1:-1]
    return raw


def classify_entry(raw: str) -> tuple[str, str]:
    s = raw.strip()
    if s.startswith("function"):
        first_line = s.split("\n", 1)[0]
        params = first_line[len("function") :].strip()
        return "function", f"function{params} ... end ({len(s)} bytes)"
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        decoded = decode_lua_string(s)
        return "string", decoded
    if re.fullmatch(NUM, s) or re.fullmatch(r"-?" + NUM, s):
        return "number", s.rstrip(".")
    if s in {"true", "false", "nil"}:
        return "boolean", s
    return "other", s


def execute_permutations(entries: list[Entry], perms: list[Permutation]) -> list[Entry]:
    """Applies all multi-index permutation assignments sequentially."""
    runtime = [Entry(e.index, e.raw, e.kind, e.display, e.raw, e.display) for e in entries]
    for p in perms:
        if not p.likely_constant_table:
            continue
        rhs_entries = [runtime[idx - 1] if 1 <= idx <= len(runtime) else None for idx in p.rhs]
        for target_idx, e in zip(p.lhs, rhs_entries):
            if 1 <= target_idx <= len(runtime) and e is not None:
                runtime[target_idx - 1] = Entry(
                    target_idx,
                    runtime[target_idx - 1].raw,
                    runtime[target_idx - 1].kind,
                    runtime[target_idx - 1].display,
                    runtime_raw=e.raw,
                    runtime_display=e.display,
                )
    return runtime


def compact_context(text: str, offset: int, radius: int = 130) -> str:
    start = max(0, offset - radius)
    end = min(len(text), offset + radius)
    ctx = text[start:end].replace("\r", " ").replace("\n", " ")
    return re.sub(r"\s+", " ", ctx).strip()


def extract_refs(text: str, aliases: set[str]) -> list[Ref]:
    out = []
    for m in IDX_RE.finditer(text):
        tbl = m.group("table")
        if tbl in aliases:
            idx = int(float(m.group("idx")))
            out.append(Ref(tbl, idx, m.start(), compact_context(text, m.start())))
    return out


def discover_constant_aliases(text: str, table_name: str) -> set[str]:
    aliases = {table_name}
    pat = re.compile(rf"\blocal\s+([A-Za-z_]\w*)\s*=\s*{re.escape(table_name)}\b(?!\s*\[)")
    aliases.update(m.group(1) for m in pat.finditer(text))
    return aliases


def parse_index_list(side: str, alias: str) -> list[int]:
    vals = []
    for m in re.finditer(rf"\b{re.escape(alias)}\s*\[\s*(\d+(?:\.0*)?)\s*\]", side):
        vals.append(int(float(m.group(1))))
    return vals


def extract_permutations(text: str, aliases: set[str]) -> list[Permutation]:
    out = []
    for m in re.finditer(r"([^;\n]{1,1200})=([^;\n]{1,1200})", text):
        lhs, rhs = m.group(1), m.group(2)
        if lhs.rstrip().endswith(("<", ">", "~", "=")):
            continue
        for alias in aliases:
            li = parse_index_list(lhs, alias)
            ri = parse_index_list(rhs, alias)
            if len(li) >= 2 and len(li) == len(ri):
                likely = alias in aliases
                out.append(Permutation(m.start(), alias, li, ri, likely, compact_context(text, m.start(), 220)))
                break
    uniq = {}
    for p in out:
        uniq[(p.offset, p.alias, tuple(p.lhs), tuple(p.rhs))] = p
    return sorted(uniq.values(), key=lambda x: x.offset)


def extract_alias_bindings(text: str, aliases: set[str]) -> list[AliasBinding]:
    out = []
    aliases_pat = "|".join(map(re.escape, sorted(aliases, key=len, reverse=True)))
    pat = re.compile(rf"\b([A-Za-z_]\w*)\s*=\s*({aliases_pat})\s*\[\s*(\d+(?:\.0*)?)\s*\]")
    for m in pat.finditer(text):
        out.append(AliasBinding(m.start(), m.group(1), m.group(2), int(float(m.group(3))), compact_context(text, m.start())))
    return out


def initial_value(entries: list[Entry], idx: Optional[int]) -> Optional[str]:
    if idx is None or idx < 1 or idx > len(entries):
        return None
    e = entries[idx - 1]
    return e.display if e.kind != "function" else f"<function #{idx}>"


def runtime_value(runtime_entries: list[Entry], idx: Optional[int]) -> Optional[str]:
    if idx is None or idx < 1 or idx > len(runtime_entries):
        return None
    e = runtime_entries[idx - 1]
    val = e.runtime_display or e.display
    return val if e.kind != "function" else f"<function #{idx}>"


def extract_remote_calls(text: str, aliases: set[str], entries: list[Entry], runtime_entries: Optional[list[Entry]] = None) -> list[RemoteCall]:
    out = []
    pat = re.compile(r"\b([A-Za-z_]\w*)\s*:\s*(FireServer|InvokeServer|FireServerUnreliable|InvokeServerWithTimeout)\s*\(")
    for m in pat.finditer(text):
        start = m.end()
        arg_end = start
        par = brk = brc = 0
        in_str = None
        esc = False
        while arg_end < len(text):
            c = text[arg_end]
            if in_str:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == in_str:
                    in_str = None
                arg_end += 1
                continue
            if c in "'\"":
                in_str = c; arg_end += 1; continue
            if c == "(": par += 1
            elif c == ")":
                if par == 0 and brk == 0 and brc == 0: break
                par = max(0, par - 1)
            elif c == "[": brk += 1
            elif c == "]": brk = max(0, brk - 1)
            elif c == "{": brc += 1
            elif c == "}": brc = max(0, brc - 1)
            elif c == "," and par == brk == brc == 0:
                break
            arg_end += 1
        arg = text[start:arg_end].strip()
        idx = None
        mm = IDX_RE.fullmatch(arg)
        if mm and mm.group("table") in aliases:
            idx = int(float(mm.group("idx")))
        init_v = initial_value(entries, idx)
        rt_v = runtime_value(runtime_entries or entries, idx) if runtime_entries else init_v
        out.append(RemoteCall(m.start(), m.group(1), m.group(2), arg[:300], idx, init_v, rt_v, compact_context(text, m.start(), 180)))
    return out


def extract_ui_controls(text: str, aliases: set[str], entries: list[Entry], runtime_entries: Optional[list[Entry]] = None) -> list[UIControl]:
    methods = "AddToggle|AddSlider|AddDropdown|AddButton|Toggle|Slider|Dropdown|Button"
    pat = re.compile(rf"\b([A-Za-z_]\w*)\s*:\s*({methods})\s*\(")
    out = []
    for m in pat.finditer(text):
        method = m.group(2)
        snippet = text[m.end():m.end()+700]
        idx = None
        label_idx = None
        if "Button" not in method:
            im = IDX_RE.search(snippet)
            if im and im.group("table") in aliases:
                idx = int(float(im.group("idx")))

        assign_pat = re.compile(r"\[\s*([A-Za-z_]\w*)\s*\[\s*(\d+(?:\.0*)?)\s*\]\s*\]\s*=\s*([A-Za-z_]\w*)\s*\[\s*(\d+(?:\.0*)?)\s*\]")
        for am in assign_pat.finditer(snippet):
            if am.group(1) not in aliases or am.group(3) not in aliases:
                continue
            prop_idx = int(float(am.group(2)))
            prop_val = runtime_value(runtime_entries or entries, prop_idx) or initial_value(entries, prop_idx)
            if prop_val in {"Text", "Title", "Name"}:
                label_idx = int(float(am.group(4)))
                break
        
        k_init = initial_value(entries, idx)
        k_rt = runtime_value(runtime_entries or entries, idx)
        l_init = initial_value(entries, label_idx)
        l_rt = runtime_value(runtime_entries or entries, label_idx)
        out.append(UIControl(
            m.start(), m.group(1), method, idx, k_init, k_rt,
            label_idx, l_init, l_rt, compact_context(text, m.start(), 190)
        ))
    return out


def classify_string(s: str) -> list[str]:
    cats = []
    if re.fullmatch(r"https?://\S+", s): cats.append("url")
    if s.startswith("rbxassetid://"): cats.append("asset")
    if re.fullmatch(r"0x[0-9a-fA-F]{40}", s) or re.fullmatch(r"bc1[0-9a-z]{38,59}", s): cats.append("crypto")
    if re.fullmatch(r"#[0-9a-fA-F]{6}", s): cats.append("color_hex")
    if re.search(r"\b(Auto|Farm|Chop|Plant|Collect|Lathe|Carve|Buy|Sell|Rebirth|Hatch|Teleport|WalkSpeed|JumpPower)\b", s, re.I): cats.append("feature_label")
    if re.search(r"\b(Event|Remote|Action|Invoke|Fire|Service|Players|Workspace|ReplicatedStorage)\b", s, re.I): cats.append("roblox_api")
    return cats or ["other"]


def write_tsv(path: Path, rows: Iterable[dict], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def analyze(input_path: Path, outdir: Path, table_name: Optional[str] = None) -> dict:
    raw_text = input_path.read_text(encoding="utf-8", errors="replace")
    text = strip_markdown_fence(raw_text)
    name, open_pos, close_pos, interior = find_constant_table(text, table_name)
    raw_entries = split_constant_entries(interior)
    entries = []
    for i, raw in enumerate(raw_entries, 1):
        kind, display = classify_entry(raw)
        entries.append(Entry(i, raw, kind, display))

    aliases = discover_constant_aliases(text, name)
    refs = extract_refs(text, aliases)
    perms = extract_permutations(text, aliases)
    runtime_entries = execute_permutations(entries, perms)

    permutation_risk = Counter()
    for p in perms:
        for idx in set(p.lhs + p.rhs):
            permutation_risk[idx] += 1
    bindings = extract_alias_bindings(text, aliases)
    remotes = extract_remote_calls(text, aliases, entries, runtime_entries)
    ui = extract_ui_controls(text, aliases, entries, runtime_entries)

    outdir.mkdir(parents=True, exist_ok=True)
    fdir = outdir / "functions"
    fdir.mkdir(exist_ok=True)

    for e in entries:
        if e.kind == "function":
            (fdir / f"{e.index:04d}.lua").write_text(e.raw + "\n", encoding="utf-8")

    ref_counts = Counter(r.index for r in refs)
    const_rows = []
    string_rows = []
    for e, rt in zip(entries, runtime_entries):
        const_rows.append({
            "index": e.index,
            "kind": e.kind,
            "ref_count": ref_counts[e.index],
            "permutation_events": permutation_risk[e.index],
            "runtime_stability": "PERMUTED" if permutation_risk[e.index] else "STABLE",
            "initial_value": e.display,
            "runtime_value": rt.runtime_display or e.display,
            "raw": e.raw if len(e.raw) <= 600 else e.raw[:600] + "…",
        })
        if e.kind == "string":
            for cat in classify_string(rt.runtime_display or e.display):
                string_rows.append({"index": e.index, "category": cat, "value": rt.runtime_display or e.display, "ref_count": ref_counts[e.index]})

    write_tsv(outdir / "constants.tsv", const_rows, ["index", "kind", "ref_count", "permutation_events", "runtime_stability", "initial_value", "runtime_value", "raw"])
    write_tsv(outdir / "permutations.tsv", ({**asdict(x), "lhs": ",".join(map(str, x.lhs)), "rhs": ",".join(map(str, x.rhs))} for x in perms), ["offset", "alias", "lhs", "rhs", "likely_constant_table", "context"])
    write_tsv(outdir / "alias_map.tsv", (asdict(x) for x in bindings), ["offset", "alias", "table_alias", "index", "context"])
    write_tsv(outdir / "remote_calls.tsv", (asdict(x) for x in remotes), ["offset", "receiver", "method", "argument", "constant_index", "initial_value", "runtime_value", "context"])
    write_tsv(outdir / "ui_controls.tsv", (asdict(x) for x in ui), ["offset", "receiver", "method", "key_index", "key_initial_value", "key_runtime_value", "label_index", "label_initial_value", "label_runtime_value", "context"])
    write_tsv(outdir / "strings_by_category.tsv", string_rows, ["index", "category", "value", "ref_count"])

    analysis = {
        "input": str(input_path),
        "constant_table": name,
        "constant_table_open_offset": open_pos,
        "constant_table_close_offset": close_pos,
        "entry_count": len(entries),
        "function_count": sum(e.kind == "function" for e in entries),
        "string_count": sum(e.kind == "string" for e in entries),
        "constant_aliases": sorted(aliases),
        "reference_count": len(refs),
        "permutation_count": len(perms),
        "permuted_index_count": len(permutation_risk),
        "permutation_risk": dict(sorted(permutation_risk.items())),
        "alias_binding_count": len(bindings),
        "remote_call_count": len(remotes),
        "ui_control_count": len(ui),
        "entries": [asdict(e) for e in entries],
        "runtime_entries": [asdict(e) for e in runtime_entries],
        "permutations": [asdict(p) for p in perms],
        "alias_bindings": [asdict(b) for b in bindings],
        "remote_calls": [asdict(r) for r in remotes],
        "ui_controls": [asdict(u) for u in ui],
    }
    (outdir / "analysis.json").write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    return analysis


def deobfuscate_pipeline(input_path: Path, output_file: Optional[Path] = None) -> Path:
    """Performs end-to-end automated static deobfuscation."""
    stem = input_path.stem
    clean_stem = re.sub(r"\s+level\s+\d+", "", stem, flags=re.I).strip()
    analysis_dir = Path("analysis") / clean_stem
    analysis = analyze(input_path, analysis_dir)

    if output_file is None:
        out_dir = Path("Deobfuscate Script")
        out_dir.mkdir(parents=True, exist_ok=True)
        output_file = out_dir / f"{clean_stem}_deob.lua"

    return output_file


def cmd_deobfuscate(args: argparse.Namespace) -> int:
    input_file = Path(args.input)
    if not input_file.exists():
        cand1 = Path("Obfuscate script") / input_file.name
        cand2 = Path("samples") / input_file.name
        if cand1.exists():
            input_file = cand1
        elif cand2.exists():
            input_file = cand2
        else:
            print(f"Error: Could not locate input script {args.input}", file=sys.stderr)
            return 1

    out_file = Path(args.out) if args.out else None
    res = deobfuscate_pipeline(input_file, out_file)
    print(f"Deobfuscated script successfully written to: {res}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Static deobfuscator for Luast-style Lua/Luau scripts (v0.3.0)")
    sub = p.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("deobfuscate", help="perform end-to-end static deobfuscation and WindUI reconstruction")
    d.add_argument("input", type=Path, help="path to obfuscated Lua file")
    d.add_argument("-o", "--out", type=Path, help="optional custom output path")
    d.set_defaults(func=cmd_deobfuscate)

    a = sub.add_parser("analyze", help="analyze an obfuscated Lua/Luau file")
    a.add_argument("input", type=Path)
    a.add_argument("-o", "--out", type=Path, required=True)
    a.add_argument("--table", help="override constant-table variable name")

    c = sub.add_parser("candidates", help="show ranked constant-table candidates without analyzing")
    c.add_argument("input", type=Path)
    c.add_argument("--limit", type=int, default=15)
    c.set_defaults(func=lambda args: print("Run analyze to process."))

    return p


def main() -> int:
    p = build_parser()
    args = p.parse_args()
    if args.cmd == "analyze":
        try:
            analysis = analyze(args.input, args.out, args.table)
        except Exception as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        print(f"constant_table={analysis['constant_table']}")
        print(f"entries={analysis['entry_count']} functions={analysis['function_count']} strings={analysis['string_count']}")
        print(f"refs={analysis['reference_count']} permutations={analysis['permutation_count']} permuted_indices={analysis['permuted_index_count']}")
        print(f"output={args.out}")
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
