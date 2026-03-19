"""Minimal offline QR Code generator for this project.

Supports QR Code Model 2, Version 3-L, byte mode only.
This is sufficient for short asset-code payloads and keeps the desktop
application dependency-free for Windows 7 packaging.
"""

from __future__ import annotations

from dataclasses import dataclass


class QrCodeError(ValueError):
    pass


@dataclass
class QrCode:
    size: int
    modules: list[list[bool]]

    def get_module(self, x: int, y: int) -> bool:
        return self.modules[y][x]


class QrCodeV3L:
    VERSION = 3
    SIZE = 29
    DATA_CODEWORDS = 55
    ECC_CODEWORDS = 15
    MAX_PAYLOAD_BYTES = 53
    GF_POLY = 0x11D

    def __init__(self, text: str):
        payload = text.encode("utf-8")
        if not payload:
            raise QrCodeError("资产编码不能为空")
        if len(payload) > self.MAX_PAYLOAD_BYTES:
            raise QrCodeError("资产编码过长，版本 3-L 二维码最多支持 53 个 UTF-8 字节")

        self.size = self.SIZE
        self.modules = [[False] * self.size for _ in range(self.size)]
        self.is_function = [[False] * self.size for _ in range(self.size)]

        codewords = self._make_codewords(payload)
        self._draw_function_patterns()
        self._draw_codewords(codewords)
        self._apply_best_mask()
        self.qr = QrCode(self.size, self.modules)

    def _make_codewords(self, payload: bytes) -> list[int]:
        bits: list[int] = []
        self._append_bits(bits, 0b0100, 4)
        self._append_bits(bits, len(payload), 8)
        for byte in payload:
            self._append_bits(bits, byte, 8)

        terminator = min(4, self.DATA_CODEWORDS * 8 - len(bits))
        self._append_bits(bits, 0, terminator)
        while len(bits) % 8 != 0:
            bits.append(0)

        data = []
        for i in range(0, len(bits), 8):
            value = 0
            for bit in bits[i : i + 8]:
                value = (value << 1) | bit
            data.append(value)

        pad_bytes = [0xEC, 0x11]
        index = 0
        while len(data) < self.DATA_CODEWORDS:
            data.append(pad_bytes[index % 2])
            index += 1

        ecc = self._reed_solomon_compute(data, self.ECC_CODEWORDS)
        return data + ecc

    def _draw_function_patterns(self) -> None:
        self._draw_finder(0, 0)
        self._draw_finder(self.size - 7, 0)
        self._draw_finder(0, self.size - 7)
        self._draw_alignment(22, 22)

        for i in range(8, self.size - 8):
            self._set_function(6, i, i % 2 == 0)
            self._set_function(i, 6, i % 2 == 0)

        self._set_function(8, self.size - 8, True)
        self._reserve_format_areas()

    def _draw_codewords(self, codewords: list[int]) -> None:
        bits = []
        for codeword in codewords:
            for shift in range(7, -1, -1):
                bits.append((codeword >> shift) & 1)

        bit_index = 0
        direction = -1
        x = self.size - 1
        y = self.size - 1

        while x > 0:
            if x == 6:
                x -= 1
            for _ in range(self.size):
                for dx in [0, -1]:
                    xx = x + dx
                    if not self.is_function[y][xx] and bit_index < len(bits):
                        self.modules[y][xx] = bool(bits[bit_index])
                        bit_index += 1
                y += direction
                if y < 0 or y >= self.size:
                    y -= direction
                    direction = -direction
                    break
            x -= 2

    def _apply_best_mask(self) -> None:
        best_mask = 0
        best_score = None
        original = [row[:] for row in self.modules]

        for mask in range(8):
            self.modules = [row[:] for row in original]
            self._apply_mask(mask)
            self._draw_format_bits(mask)
            score = self._penalty_score()
            if best_score is None or score < best_score:
                best_score = score
                best_mask = mask

        self.modules = [row[:] for row in original]
        self._apply_mask(best_mask)
        self._draw_format_bits(best_mask)

    def _apply_mask(self, mask: int) -> None:
        for y in range(self.size):
            for x in range(self.size):
                if self.is_function[y][x]:
                    continue
                invert = False
                if mask == 0:
                    invert = (x + y) % 2 == 0
                elif mask == 1:
                    invert = y % 2 == 0
                elif mask == 2:
                    invert = x % 3 == 0
                elif mask == 3:
                    invert = (x + y) % 3 == 0
                elif mask == 4:
                    invert = ((y // 2) + (x // 3)) % 2 == 0
                elif mask == 5:
                    invert = ((x * y) % 2) + ((x * y) % 3) == 0
                elif mask == 6:
                    invert = (((x * y) % 2) + ((x * y) % 3)) % 2 == 0
                elif mask == 7:
                    invert = (((x + y) % 2) + ((x * y) % 3)) % 2 == 0
                if invert:
                    self.modules[y][x] = not self.modules[y][x]

    def _draw_format_bits(self, mask: int) -> None:
        data = (0b01 << 3) | mask
        rem = data
        for _ in range(10):
            rem <<= 1
        generator = 0x537
        for bit in range(14, 9, -1):
            if (rem >> bit) & 1:
                rem ^= generator << (bit - 10)
        bits = ((data << 10) | rem) ^ 0x5412

        coords1 = [
            (8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5),
            (8, 7), (8, 8), (7, 8), (5, 8), (4, 8), (3, 8),
            (2, 8), (1, 8), (0, 8),
        ]
        coords2 = [
            (self.size - 1, 8), (self.size - 2, 8), (self.size - 3, 8),
            (self.size - 4, 8), (self.size - 5, 8), (self.size - 6, 8),
            (self.size - 7, 8), (8, self.size - 8), (8, self.size - 7),
            (8, self.size - 6), (8, self.size - 5), (8, self.size - 4),
            (8, self.size - 3), (8, self.size - 2), (8, self.size - 1),
        ]

        for i in range(15):
            bit = ((bits >> i) & 1) == 1
            x1, y1 = coords1[i]
            x2, y2 = coords2[i]
            self.modules[y1][x1] = bit
            self.modules[y2][x2] = bit

    def _penalty_score(self) -> int:
        score = 0
        size = self.size

        for row in self.modules:
            run_color = row[0]
            run_length = 1
            for value in row[1:]:
                if value == run_color:
                    run_length += 1
                else:
                    if run_length >= 5:
                        score += 3 + (run_length - 5)
                    run_color = value
                    run_length = 1
            if run_length >= 5:
                score += 3 + (run_length - 5)

        for x in range(size):
            run_color = self.modules[0][x]
            run_length = 1
            for y in range(1, size):
                value = self.modules[y][x]
                if value == run_color:
                    run_length += 1
                else:
                    if run_length >= 5:
                        score += 3 + (run_length - 5)
                    run_color = value
                    run_length = 1
            if run_length >= 5:
                score += 3 + (run_length - 5)

        for y in range(size - 1):
            for x in range(size - 1):
                color = self.modules[y][x]
                if (
                    self.modules[y][x + 1] == color
                    and self.modules[y + 1][x] == color
                    and self.modules[y + 1][x + 1] == color
                ):
                    score += 3

        pattern1 = [True, False, True, True, True, False, True, False, False, False, False]
        pattern2 = [False, False, False, False, True, False, True, True, True, False, True]
        for row in self.modules:
            for i in range(size - 10):
                chunk = row[i : i + 11]
                if chunk == pattern1 or chunk == pattern2:
                    score += 40
        for x in range(size):
            column = [self.modules[y][x] for y in range(size)]
            for i in range(size - 10):
                chunk = column[i : i + 11]
                if chunk == pattern1 or chunk == pattern2:
                    score += 40

        dark = sum(1 for row in self.modules for value in row if value)
        total = size * size
        k = abs(dark * 20 - total * 10) // total
        score += k * 10
        return score

    def _draw_finder(self, x: int, y: int) -> None:
        for dy in range(-1, 8):
            for dx in range(-1, 8):
                xx = x + dx
                yy = y + dy
                if 0 <= xx < self.size and 0 <= yy < self.size:
                    dist = max(abs(dx), abs(dy))
                    value = dist not in (1, 5) and dist <= 4
                    self._set_function(xx, yy, value)

    def _draw_alignment(self, cx: int, cy: int) -> None:
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                dist = max(abs(dx), abs(dy))
                self._set_function(cx + dx, cy + dy, dist != 1)

    def _reserve_format_areas(self) -> None:
        for i in range(9):
            if i != 6:
                self.is_function[8][i] = True
                self.is_function[i][8] = True
        for i in range(8):
            self.is_function[self.size - 1 - i][8] = True
            self.is_function[8][self.size - 1 - i] = True

    def _set_function(self, x: int, y: int, value: bool) -> None:
        self.modules[y][x] = value
        self.is_function[y][x] = True

    @classmethod
    def _append_bits(cls, bits: list[int], value: int, length: int) -> None:
        for shift in range(length - 1, -1, -1):
            bits.append((value >> shift) & 1)

    @classmethod
    def _gf_multiply(cls, x: int, y: int) -> int:
        result = 0
        while y:
            if y & 1:
                result ^= x
            x <<= 1
            if x & 0x100:
                x ^= cls.GF_POLY
            y >>= 1
        return result

    @classmethod
    def _reed_solomon_compute(cls, data: list[int], degree: int) -> list[int]:
        generator = [0] * degree
        generator[-1] = 1
        root = 1
        for _ in range(degree):
            for i in range(degree):
                generator[i] = cls._gf_multiply(generator[i], root)
                if i + 1 < degree:
                    generator[i] ^= generator[i + 1]
            root = cls._gf_multiply(root, 0x02)

        result = [0] * degree
        for value in data:
            factor = value ^ result[0]
            result = result[1:] + [0]
            for i in range(degree):
                result[i] ^= cls._gf_multiply(generator[i], factor)
        return result


def make_qr(text: str) -> QrCode:
    return QrCodeV3L(text).qr
