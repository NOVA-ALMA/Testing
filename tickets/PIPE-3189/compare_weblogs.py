"""Compare two rendered weblog trees artefact by artefact (PIPE-3189).

Byte-compares every file the two trees share, and for PNGs additionally
compares the decoded pixels, so that a pure metadata difference (render
clock, temp path) is not mistaken for a visual change.  PNG IDAT streams are
compared separately to make that distinction explicit.

Usage:
    conda run -n almaPL26CM python compare_weblogs.py <name> <baseline_dir> <variant_dir>

Example:
    conda run -n almaPL26CM python compare_weblogs.py SQLD \
        pr/weblogs/sqld_main pr/weblogs/sqld_stratified
"""
import os
import struct
import sys

import numpy as np
from PIL import Image

# A difference below this is invisible: it is anti-aliasing on marker glyphs.
THRESHOLD = 8


def png_chunks(path):
    """Return {chunk type: concatenated payload} for a PNG file."""
    out = {}
    with open(path, 'rb') as fh:
        assert fh.read(8) == b'\x89PNG\r\n\x1a\n', 'not a PNG: %s' % path
        while True:
            head = fh.read(8)
            if len(head) < 8:
                break
            length, ctype = struct.unpack('>I4s', head)
            payload = fh.read(length)
            fh.read(4)  # CRC
            key = ctype.decode('latin1')
            out[key] = out.get(key, b'') + payload
    return out


def compare_png(base, var):
    """Pixel-level comparison. Returns (n_diff, pct, mean_ch_diff, size)."""
    a = np.asarray(Image.open(base).convert('RGB'), dtype=np.int16)
    b = np.asarray(Image.open(var).convert('RGB'), dtype=np.int16)
    if a.shape != b.shape:
        return None, None, None, '%s vs %s' % (a.shape, b.shape)
    d = np.abs(a - b)
    per_px = d.max(axis=2)
    n_diff = int((per_px > THRESHOLD).sum())
    pct = 100.0 * n_diff / per_px.size
    mean_ch = float(d.mean())
    return n_diff, pct, mean_ch, '%dx%d' % (a.shape[1], a.shape[0])


def idat_equal(base, var):
    """True when the compressed pixel streams are byte-identical."""
    return png_chunks(base).get('IDAT') == png_chunks(var).get('IDAT')


def main(name, base_dir, var_dir):
    print('=== %s ===' % name)
    print('baseline: %s' % base_dir)
    print('variant : %s' % var_dir)
    print()
    hdr = '%-34s %-10s %s' % ('artefact', 'identical', 'detail')
    print(hdr)
    print('-' * len(hdr))

    rows = []
    for root, _dirs, files in os.walk(base_dir):
        for fname in sorted(files):
            rel = os.path.relpath(os.path.join(root, fname), base_dir)
            base = os.path.join(base_dir, rel)
            var = os.path.join(var_dir, rel)
            if not os.path.exists(var):
                rows.append((rel, 'MISSING', 'absent from variant'))
                continue
            with open(base, 'rb') as fh:
                b_bytes = fh.read()
            with open(var, 'rb') as fh:
                v_bytes = fh.read()
            same = b_bytes == v_bytes
            if fname.lower().endswith('.png'):
                n_diff, pct, mean_ch, size = compare_png(base, var)
                detail = '>%d/255: %d px (%.3f%%)  mean ch diff %.3f  %s  [IDAT identical: %s]' % (
                    THRESHOLD, n_diff, pct, mean_ch, size, idat_equal(base, var))
            else:
                detail = '%d vs %d bytes' % (len(b_bytes), len(v_bytes))
            rows.append((rel, str(same), detail))

    for rel, same, detail in rows:
        print('%-34s %-10s %s' % (rel, same, detail))
    print()

    missing = [r for r in rows if r[1] == 'MISSING']
    if missing:
        print('MISSING from variant: %s' % ', '.join(r[0] for r in missing))
        print()
    return rows


if __name__ == '__main__':
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)
    main(sys.argv[1], sys.argv[2], sys.argv[3])
