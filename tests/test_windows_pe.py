"""Offline tests for the PE/amd64 layer: address translation, assembler, and shape guard."""

from __future__ import annotations

import os
import pathlib
import struct
import unittest

from tools import win_amd64
from tools.binfmt import PEImage


def synthetic_pe() -> bytes:
    """A minimal PE32+ with .text at RVA 0x1000 and .rdata at RVA 0x2000."""
    image = bytearray(0x600)
    image[0:2] = b"MZ"
    struct.pack_into("<I", image, 0x3C, 0x40)
    image[0x40:0x44] = b"PE\0\0"
    struct.pack_into("<HHIIIHH", image, 0x44, 0x8664, 2, 0, 0, 0, 240, 0x22)
    optional = 0x58
    struct.pack_into("<H", image, optional, 0x20B)
    struct.pack_into("<Q", image, optional + 24, 0x140000000)
    struct.pack_into("<I", image, optional + 32, 0x1000)  # section alignment
    struct.pack_into("<I", image, optional + 36, 0x200)  # file alignment
    struct.pack_into("<I", image, optional + 56, 0x3000)  # size of image
    struct.pack_into("<I", image, optional + 60, 0x200)  # size of headers
    sections = optional + 240
    struct.pack_into("<8sIIII", image, sections, b".text", 0x200, 0x1000, 0x200, 0x200)
    struct.pack_into("<8sIIII", image, sections + 40, b".rdata", 0x200, 0x2000, 0x200, 0x400)
    image[0x200:0x210] = bytes(range(16))
    image[0x400:0x408] = b"template"
    return bytes(image)


class PEImageTests(unittest.TestCase):
    def test_address_translation(self) -> None:
        image = PEImage(synthetic_pe())
        self.assertEqual(image.image_base, 0x140000000)
        self.assertEqual(image.text.name, ".text")
        self.assertEqual(image.offset_of(0x140001000), 0x200)
        self.assertEqual(image.offset_of(0x14000100F), 0x20F)
        self.assertEqual(image.va_of(0x200), 0x140001000)
        self.assertEqual(image.va_of(0x400), 0x140002000)

    def test_rejects_an_address_outside_every_section(self) -> None:
        image = PEImage(synthetic_pe())
        with self.assertRaises(ValueError):
            image.offset_of(0x150000000)


class AsmTests(unittest.TestCase):
    def test_call_and_jump_displacements(self) -> None:
        asm = win_amd64.Asm(0x1000)
        asm.mov_rax_rsp(0x108)
        asm.call_va(0x2000)
        asm.leave()
        asm.ret()
        code = asm.finish()
        self.assertEqual(code[:8], bytes.fromhex("488b842408010000"))
        self.assertEqual(code[8], 0xE8)
        self.assertEqual(struct.unpack_from("<i", code, 9)[0], 0x2000 - (0x1000 + 13))
        self.assertEqual(code[13:], b"\xc9\xc3")

    def test_short_branch_to_label(self) -> None:
        asm = win_amd64.Asm(0x1000)
        asm.jz("miss")
        asm.ret()
        asm.label("miss")
        asm.ret()
        self.assertEqual(asm.finish(), b"\x74\x01\xc3\xc3")

    def test_cave_is_inside_the_reviewed_padding(self) -> None:
        spec = win_amd64._load_shapes("1.5.9")
        self.assertEqual(spec["text_vsize"], 0x40F62E6)
        self.assertEqual(spec["text_raw_size"], 0x40F6400)
        self.assertGreaterEqual(spec["text_raw_size"] - spec["text_vsize"], win_amd64.CAVE_SIZE)


class ShapeGuardTests(unittest.TestCase):
    def test_reviewed_shapes_are_hex(self) -> None:
        spec = win_amd64._load_shapes("1.5.9")
        self.assertIn("store.(*Store).ContextWindow -> (*Store).ContextWindowChoice", spec["sites"])
        for name, shape in spec["sites"].items():
            self.assertTrue(bytes.fromhex(shape), name)

    def test_unknown_version_fails_closed(self) -> None:
        with self.assertRaises(RuntimeError):
            win_amd64._load_shapes("0.0.0")


class LiveBinaryTests(unittest.TestCase):
    """Runs only when AGY_WINDOWS_BINARY points at a real windows/amd64 agy v1.5.9."""

    def test_resolves_every_reviewed_site(self) -> None:
        path = os.environ.get("AGY_WINDOWS_BINARY")
        if not path:
            self.skipTest("set AGY_WINDOWS_BINARY to the downloaded windows/amd64 agy.exe")
        data = pathlib.Path(path).read_bytes()
        sites = win_amd64.resolve_patch_sites(data, "1.5.9", strict=True)
        self.assertGreaterEqual(len(sites), 11)
        self.assertTrue(any(s.domain == "context-window" for s in sites))
        self.assertTrue(any(s.domain == "prompt" for s in sites))


if __name__ == "__main__":
    unittest.main()
