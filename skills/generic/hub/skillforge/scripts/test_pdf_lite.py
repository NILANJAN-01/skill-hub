"""Tests for pdf_lite.py. The PDFs are built in code, so no binary fixtures are needed."""
import binascii
import hashlib
import os
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import pdf_lite  # noqa: E402
from pdf_lite import PdfDocument, PdfError  # noqa: E402

PAD = pdf_lite._PAD
FILE_ID = bytes(range(16))


class Builder:
    """Minimal PDF writer: classic or compressed cross-reference, optional RC4/AES encryption."""

    def __init__(self):
        self.objs = {}

    def add(self, body, num=None):
        num = num or len(self.objs) + 1
        self.objs[num] = body
        return num

    def stream(self, attrs, data, compress=False, num=None):
        if compress:
            data = zlib.compress(data)
            attrs = attrs + b" /Filter /FlateDecode"
        return self.add((b"<<" + attrs + b" /Length %d>>" % len(data), data), num)

    def build(self, root, info=None, xref_stream=False, objstm=(), crypt=None, break_xref=False):
        out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
        offsets = {}
        nums = sorted(self.objs)
        packed = [n for n in nums if n in objstm]
        next_num = max(nums) + 1
        for n in nums:
            if n in packed:
                continue
            body = self.objs[n]
            offsets[n] = len(out)
            out += b"%d 0 obj\n" % n
            if isinstance(body, tuple):
                head, data = body
                if crypt:
                    data = crypt(data, n)
                    head = head.replace(b"/Length %d" % len(body[1]), b"/Length %d" % len(data))
                out += head + b"\nstream\n" + data + b"\nendstream\nendobj\n"
            else:
                out += (crypt_strings(body, n, crypt) if crypt else body) + b"\nendobj\n"
        stm_num = None
        if packed:
            stm_num = next_num
            next_num += 1
            header, data = b"", b""
            for n in packed:
                header += b"%d %d " % (n, len(data))
                data += self.objs[n] + b"\n"
            payload = zlib.compress(header + data)
            offsets[stm_num] = len(out)
            out += (b"%d 0 obj\n<</Type /ObjStm /N %d /First %d /Filter /FlateDecode /Length %d>>\nstream\n"
                    % (stm_num, len(packed), len(header), len(payload))) + payload + b"\nendstream\nendobj\n"
        trailer = b"/Root %d 0 R" % root + (b" /Info %d 0 R" % info if info else b"")
        trailer += b" /ID [<%s> <%s>]" % (binascii.hexlify(FILE_ID), binascii.hexlify(FILE_ID))
        if crypt:
            trailer += b" /Encrypt %d 0 R" % crypt.enc_num
        if xref_stream:
            xnum = next_num
            size = xnum + 1
            offsets[xnum] = len(out)
            rows = []
            for n in range(size):
                if n in offsets:
                    rows.append(struct.pack(">BIH", 1, offsets[n], 0))
                elif n in packed:
                    rows.append(struct.pack(">BIH", 2, stm_num, packed.index(n)))
                else:
                    rows.append(struct.pack(">BIH", 0, 0, 0))
            prev, enc = bytes(7), b""
            for row in rows:                                   # PNG "Up" predictor
                enc += b"\x02" + bytes((a - b) & 0xFF for a, b in zip(row, prev))
                prev = row
            data = zlib.compress(enc)
            out += (b"%d 0 obj\n<</Type /XRef /Size %d /W [1 4 2] %s /Filter /FlateDecode "
                    b"/DecodeParms <</Predictor 12 /Columns 7>> /Length %d>>\nstream\n"
                    % (xnum, size, trailer, len(data))) + data + b"\nendstream\nendobj\n"
            start = offsets[xnum]
        else:
            start = len(out)
            size = max(offsets) + 1
            out += b"xref\n0 %d\n0000000000 65535 f \n" % size
            for n in range(1, size):
                out += (b"%010d 00000 n \n" % offsets[n]) if n in offsets else b"0000000000 00000 f \n"
            out += b"trailer\n<</Size %d %s>>\n" % (size, trailer)
        out += b"startxref\n%d\n%%%%EOF\n" % (start + 7 if break_xref else start)
        return bytes(out)


def crypt_strings(body, num, crypt):
    """Encrypt the (...) strings of an object body (test objects only use simple strings)."""
    import re

    def rep(m):
        return b"<" + binascii.hexlify(crypt(m.group(1), num)) + b">"
    return re.sub(rb"\(([^()\\]*)\)", rep, body)


class Rc4Crypt:
    """Standard security handler, revision 3, 128-bit RC4, empty user password."""

    def __init__(self, enc_num):
        self.enc_num = enc_num
        n = 16
        h = hashlib.md5((b"owner" + PAD)[:32]).digest()
        for _ in range(50):
            h = hashlib.md5(h[:n]).digest()
        okey = h[:n]
        o = pdf_lite._rc4(okey, PAD)
        for i in range(1, 20):
            o = pdf_lite._rc4(bytes(b ^ i for b in okey), o)
        self.p = -4
        key = hashlib.md5(PAD + o + struct.pack("<i", self.p) + FILE_ID).digest()
        for _ in range(50):
            key = hashlib.md5(key[:n]).digest()
        self.key = key[:n]
        u = pdf_lite._rc4(self.key, hashlib.md5(PAD + FILE_ID).digest())
        for i in range(1, 20):
            u = pdf_lite._rc4(bytes(b ^ i for b in self.key), u)
        self.o, self.u = o, u + bytes(16)

    def dict(self):
        return (b"<</Filter /Standard /V 2 /R 3 /Length 128 /P %d /O <%s> /U <%s>>>"
                % (self.p, binascii.hexlify(self.o), binascii.hexlify(self.u)))

    def objkey(self, num):
        return hashlib.md5(self.key + struct.pack("<I", num)[:3] + b"\x00\x00").digest()[:16]

    def __call__(self, data, num):
        return pdf_lite._rc4(self.objkey(num), data)


class AesCrypt(Rc4Crypt):
    """Revision 4 with the AESV2 crypt filter."""

    def dict(self):
        return (b"<</Filter /Standard /V 4 /R 4 /Length 128 /P %d /O <%s> /U <%s> /StmF /StdCF /StrF /StdCF "
                b"/CF <</StdCF <</CFM /AESV2 /Length 16>>>>>>"
                % (self.p, binascii.hexlify(self.o), binascii.hexlify(self.u)))

    def __call__(self, data, num):
        key = hashlib.md5(self.key + struct.pack("<I", num)[:3] + b"\x00\x00sAlT").digest()[:16]
        iv = bytes(range(16, 32))
        pad = 16 - len(data) % 16
        return iv + pdf_lite._AES(key).cbc_encrypt(iv, data + bytes([pad]) * pad)


PAGE1 = (b"BT /F1 18 Tf 72 720 Td (Installing the tool) Tj ET\n"
         b"BT /F2 10 Tf 72 690 Td 12 TL (First line of a paragraph that) Tj T* (continues on the next line.) Tj ET\n"
         b"BT /F2 10 Tf 72 640 Td (After a gap, a new paragraph.) Tj ET\n"
         b"BT /F3 9 Tf 90 610 Td ($ tool install --global) Tj ET\n"
         b"BT /F2 10 Tf 72 590 Td [(Kerned)-250(words)] TJ ET\n"
         b"q 0 0 100 100 re W n BT /F2 10 Tf 300 300 Td (Hidden by the clip) Tj ET "
         b"BT /F2 10 Tf 20 50 Td (Inside the clip) Tj ET Q\n"
         b"BT /F2 8 Tf 300 20 Td (7) Tj ET\n")
PAGE2 = (b"BT /F4 12 Tf 72 700 Td <00010002> Tj ET\n"
         b"BT /F5 12 Tf 72 680 Td (ABC) Tj ET\n"
         b"q 1 0 0 1 100 400 cm /X1 Do Q\n")
FONTS = b"<</F1 3 0 R /F2 4 0 R /F3 5 0 R /F4 6 0 R /F5 9 0 R>>"


def sample(compress=False, xref_stream=False, objstm=(), crypt_cls=None, break_xref=False, title=b"(Test Book)"):
    b = Builder()
    b.add(b"<</Type /Catalog /Pages 2 0 R /Outlines 14 0 R>>", 1)
    b.add(b"<</Type /Pages /Kids [10 0 R 11 0 R] /Count 2 /MediaBox [0 0 612 792]>>", 2)
    b.add(b"<</Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold>>", 3)
    b.add(b"<</Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding>>", 4)
    b.add(b"<</Type /Font /Subtype /Type1 /BaseFont /Courier>>", 5)
    b.add(b"<</Type /Font /Subtype /Type0 /BaseFont /ABCDEF+TestSans /Encoding /Identity-H "
          b"/DescendantFonts [7 0 R] /ToUnicode 8 0 R>>", 6)
    b.add(b"<</Type /Font /Subtype /CIDFontType2 /BaseFont /ABCDEF+TestSans /W [1 [500 600]] /DW 1000 "
          b"/CIDSystemInfo <</Registry (Adobe) /Ordering (Identity) /Supplement 0>>>>", 7)
    b.stream(b"", b"/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n1 begincodespacerange\n"
                  b"<0000> <FFFF>\nendcodespacerange\n1 beginbfchar\n<0001> <0048>\nendbfchar\n"
                  b"1 beginbfrange\n<0002> <0003> <0069>\nendbfrange\nendcmap\n", compress, 8)
    b.add(b"<</Type /Font /Subtype /Type1 /BaseFont /Times-Roman /Encoding "
          b"<</BaseEncoding /WinAnsiEncoding /Differences [65 /eacute /uni2192 /f_i]>>>>", 9)
    b.add(b"<</Type /Page /Parent 2 0 R /Resources <</Font " + FONTS + b">> /Contents 12 0 R>>", 10)
    b.add(b"<</Type /Page /Parent 2 0 R /Resources <</Font " + FONTS + b" /XObject <</X1 13 0 R>>>> "
          b"/Contents 15 0 R /Rotate 0>>", 11)
    b.stream(b"", PAGE1, compress, 12)
    b.stream(b" /Type /XObject /Subtype /Form /BBox [0 0 300 100] /Resources <</Font " + FONTS + b">>",
             b"BT /F2 10 Tf 5 5 Td (Text in a form) Tj ET", compress, 13)
    b.add(b"<</Type /Outlines /First 16 0 R /Last 16 0 R /Count 2>>", 14)
    b.stream(b"", PAGE2, compress, 15)
    b.add(b"<</Title <FEFF004300680061007000740065007200200031> /Parent 14 0 R /Dest [10 0 R /XYZ 0 792 0] "
          b"/First 17 0 R /Last 17 0 R>>", 16)
    b.add(b"<</Title (Section 1.1) /Parent 16 0 R /A <</S /GoTo /D [11 0 R /Fit]>>>>", 17)
    b.add(b"<</Title " + title + b" /Producer (pdf_lite tests)>>", 18)
    crypt = None
    if crypt_cls:
        crypt = crypt_cls(19)
        b.add(crypt.dict(), 19)
    return b.build(1, 18, xref_stream=xref_stream, objstm=objstm, crypt=crypt, break_xref=break_xref)


def open_bytes(data):
    tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    tmp.write(data)
    tmp.close()
    try:
        return PdfDocument(tmp.name)
    finally:
        os.unlink(tmp.name)


def lines(page):
    out = []
    for bi, b in enumerate(page.text_dict(sort=True)["blocks"]):
        for ln in b["lines"]:
            out.append((bi, "".join(s["text"] for s in ln["spans"]), ln["spans"][0], ln["bbox"]))
    return out


class Layout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = open_bytes(sample())

    def test_document_info(self):
        self.assertEqual(len(self.doc.pages), 2)
        self.assertEqual(self.doc.title, "Test Book")
        self.assertEqual(self.doc.toc, [(1, "Chapter 1", 1), (2, "Section 1.1", 2)])
        self.assertEqual((self.doc.pages[0].width, self.doc.pages[0].height), (612.0, 792.0))

    def test_lines_fonts_and_sizes(self):
        ls = lines(self.doc.pages[0])
        texts = [t for _, t, _, _ in ls]
        self.assertEqual(texts, ["Installing the tool", "First line of a paragraph that",
                                 "continues on the next line.", "After a gap, a new paragraph.",
                                 "$ tool install --global", "Kerned words", "Inside the clip", "7"])
        head = ls[0][2]
        self.assertEqual((head["font"], round(head["size"], 2)), ("Helvetica-Bold", 18.0))
        self.assertTrue(head["flags"] & 16)
        self.assertFalse(ls[1][2]["flags"] & 16)
        self.assertEqual(ls[4][2]["font"], "Courier")
        self.assertTrue(ls[4][2]["flags"] & 8)

    def test_positions_use_top_left_origin(self):
        bi, text, span, bbox = lines(self.doc.pages[0])[0]
        self.assertAlmostEqual(bbox[0], 72.0, places=3)
        self.assertAlmostEqual(span["origin"][1], 792 - 720, places=3)
        self.assertLess(bbox[1], 72.0)
        self.assertGreater(bbox[3], 72.0)

    def test_blocks_follow_line_spacing(self):
        ls = lines(self.doc.pages[0])
        self.assertEqual(ls[1][0], ls[2][0], "1.2 em leading keeps the paragraph in one block")
        self.assertNotEqual(ls[2][0], ls[3][0], "a 5 em gap starts a new block")

    def test_unicode_mappings_and_forms(self):
        texts = [t for _, t, _, _ in lines(self.doc.pages[1])]
        self.assertIn("Hi", texts)                        # Type0 + ToUnicode bfchar/bfrange
        self.assertIn("é→fi", texts)            # Differences: eacute, uni2192, f_i
        self.assertIn("Text in a form", texts)            # form XObject
        span = next(s for _, t, s, _ in lines(self.doc.pages[1]) if t == "Hi")
        self.assertEqual(span["font"], "TestSans")        # subset tag removed

    def test_clip_hides_text(self):
        texts = [t for _, t, _, _ in lines(self.doc.pages[0])]
        self.assertNotIn("Hidden by the clip", texts)
        self.assertIn("Inside the clip", texts)


class FileStructure(unittest.TestCase):
    def expect_same(self, data):
        doc = open_bytes(data)
        self.assertEqual(doc.title, "Test Book")
        self.assertEqual([t for _, t, _, _ in lines(doc.pages[0])][:2], ["Installing the tool",
                                                                          "First line of a paragraph that"])
        self.assertIn("Hi", [t for _, t, _, _ in lines(doc.pages[1])])

    def test_compressed_streams(self):
        self.expect_same(sample(compress=True))

    def test_xref_stream_with_predictor_and_object_stream(self):
        self.expect_same(sample(compress=True, xref_stream=True, objstm=(3, 4, 5, 9, 18)))

    def test_broken_xref_is_repaired(self):
        self.expect_same(sample(break_xref=True))

    def test_rc4_encryption(self):
        self.expect_same(sample(compress=True, crypt_cls=Rc4Crypt))

    def test_aes_encryption(self):
        self.expect_same(sample(compress=True, crypt_cls=AesCrypt))

    def test_not_a_pdf(self):
        with self.assertRaises(PdfError):
            open_bytes(b"hello world")


class Filters(unittest.TestCase):
    def test_lzw_example_from_the_pdf_reference(self):
        self.assertEqual(pdf_lite._lzw(binascii.unhexlify("800B6050220C0C8501")), b"-----A---B")

    def test_lzw_round_trip_through_all_code_widths(self):
        def encode(data):                    # reference encoder: EarlyChange=1, widths as in pdf.js
            table = {bytes([i]): i for i in range(256)}
            nxt, bits, out, w = 258, 9, [(256, 9)], b""
            for ch in data:
                wc = w + bytes([ch])
                if wc in table:
                    w = wc
                    continue
                out.append((table[w], bits))
                table[wc] = nxt
                nxt += 1
                if nxt >= 4094:
                    out.append((256, bits))
                    table, nxt, bits = {bytes([i]): i for i in range(256)}, 258, 9
                elif nxt >= (1 << bits) and bits < 12:
                    bits += 1
                w = bytes([ch])
            out += [(table[w], bits), (257, bits)]
            acc = n = 0
            res = bytearray()
            for c, b in out:
                acc, n = (acc << b) | c, n + b
                while n >= 8:
                    n -= 8
                    res.append((acc >> n) & 255)
            if n:
                res.append((acc << (8 - n)) & 255)
            return bytes(res)
        import random
        rnd = random.Random(1)
        data = bytes(rnd.choice(b"abcab cd\n") for _ in range(60000)) + bytes(rnd.randrange(256) for _ in range(20000))
        self.assertEqual(pdf_lite._lzw(encode(data)), data)

    def test_ascii_filters_and_runlength(self):
        self.assertEqual(pdf_lite._a85(b"87cURD]i,\"Ebo80~>"), b"Hello World!")
        self.assertEqual(pdf_lite._ahex(b"48 65 6c6C 6>"), b"Hell`")       # odd digit count: pad with 0
        self.assertEqual(pdf_lite._runlength(b"\x02abc\xfdz\x80"), b"abczzzz")

    def test_damaged_flate_keeps_what_it_can(self):
        data = zlib.compress(b"x" * 1000)[:-6]
        self.assertTrue(pdf_lite._flate(data).startswith(b"x" * 100))

    def test_png_predictors(self):
        rows = [bytes([10, 20, 30]), bytes([11, 22, 33])]
        enc = b"\x01" + bytes([10, 10, 10]) + b"\x02" + bytes([1, 2, 3])   # Sub, then Up
        self.assertEqual(pdf_lite._predict(enc, {"Predictor": 12, "Columns": 3}), b"".join(rows))


class Crypto(unittest.TestCase):
    def test_aes_fips197_vectors(self):
        pt = binascii.unhexlify("00112233445566778899aabbccddeeff")
        for key, ct in (("000102030405060708090a0b0c0d0e0f", "69c4e0d86a7b0430d8cdb78070b4c55a"),
                        ("000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f",
                         "8ea2b7ca516745bfeafc49904b496089")):
            aes = pdf_lite._AES(binascii.unhexlify(key))
            self.assertEqual(binascii.hexlify(aes.encrypt_block(pt)).decode(), ct)
            self.assertEqual(aes.decrypt_block(binascii.unhexlify(ct)), pt)

    def test_rc4_vector(self):
        self.assertEqual(binascii.hexlify(pdf_lite._rc4(b"Key", b"Plaintext")).decode(), "bbf316e8d940af0ad3")


class Glyphs(unittest.TestCase):
    def test_glyph_names(self):
        g = pdf_lite.glyph_to_unicode
        self.assertEqual([g("A"), g("eacute"), g("uni00E9"), g("u1F600"), g("f_i"), g("a.sc"), g("alpha")],
                         ["A", "é", "é", "\U0001F600", "fi", "a", "α"])
        self.assertIsNone(g("g123"))

    def test_text_strings(self):
        self.assertEqual(pdf_lite._text_string(b"\xfe\xff\x00H\x00i"), "Hi")
        self.assertEqual(pdf_lite._text_string(b"caf\xe9"), "café")


if __name__ == "__main__":
    unittest.main()
