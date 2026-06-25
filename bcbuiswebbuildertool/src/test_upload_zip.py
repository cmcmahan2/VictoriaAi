"""
Tests for the site-zip uploader (server._safe_extract_zip / _detect_entry_point).

Covers: happy path, zip-slip attempt, oversized (zip-bomb) zip, a zip with no
HTML, and a disallowed file type. Offline — builds in-memory zips and calls the
extraction helpers directly.

Run:  python test_upload_zip.py
"""
import io
import os
import sys
import tempfile
import zipfile
import zlib
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

import server


def _assert(cond, msg):
    if not cond:
        raise AssertionError(msg)


def _zip(files: dict) -> bytes:
    """Build a zip from {arcname: bytes|str}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            if isinstance(data, str):
                data = data.encode("utf-8")
            zf.writestr(name, data)
    return buf.getvalue()


def test_happy_path():
    raw = _zip({
        "index.html": "<!DOCTYPE html><html><body><h1>Hi</h1></body></html>",
        "css/style.css": "body{color:#222}",
        "js/app.js": "console.log('ok')",
        "assets/logo.png": b"\x89PNG\r\n\x1a\n fake",
        "__MACOSX/._index.html": "junk",   # should be skipped
        ".DS_Store": b"junk",                # should be skipped
    })
    with tempfile.TemporaryDirectory() as d:
        dest = Path(d) / "site"
        rel = server._safe_extract_zip(raw, dest)
        _assert("index.html" in rel, "index.html should be extracted")
        _assert("css/style.css" in rel, "nested css should be extracted")
        _assert(not any("__MACOSX" in p for p in rel), "__MACOSX must be skipped")
        _assert(not any(p.endswith(".DS_Store") for p in rel), ".DS_Store must be skipped")
        _assert((dest / "css" / "style.css").exists(), "folder structure preserved")
        entry = server._detect_entry_point(rel)
        _assert(entry == "index.html", f"entry should be index.html, got {entry}")
    print("✓ happy path: extracts, preserves structure, skips cruft, finds index.html")


def test_entry_point_fallbacks():
    # No index.html, single top-level html -> that file.
    rel = ["Careful Painting.html", "css/x.css"]
    _assert(server._detect_entry_point(rel) == "Careful Painting.html",
            "single top-level html should be the entry")
    # Nested index.html when none at root.
    rel = ["pages/index.html", "a.css"]
    _assert(server._detect_entry_point(rel) == "pages/index.html",
            "nested index.html should be chosen")
    # Multiple top-level html, no index, no base_dir -> ambiguous (None).
    rel = ["a.html", "b.html"]
    _assert(server._detect_entry_point(rel) is None,
            "ambiguous multiple top-level html should return None without base_dir")
    # With base_dir, the largest top-level html wins the tie-break.
    with tempfile.TemporaryDirectory() as d:
        base = Path(d)
        (base / "small.html").write_text("<html></html>")
        (base / "Home Page.html").write_text("<html>" + "x" * 5000 + "</html>")
        chosen = server._detect_entry_point(["small.html", "Home Page.html"], base_dir=base)
        _assert(chosen == "Home Page.html",
                f"largest top-level html should win, got {chosen}")
    print("✓ entry-point fallbacks: nested index, single html, ambiguous-None, largest tie-break")


def test_zip_slip_rejected():
    raw = _zip({
        "index.html": "<html></html>",
        "../evil.html": "<html>pwned</html>",
    })
    with tempfile.TemporaryDirectory() as d:
        dest = Path(d) / "site"
        try:
            server._safe_extract_zip(raw, dest)
            _assert(False, "zip-slip entry should have been rejected")
        except server.ZipUploadError as e:
            _assert("zip-slip" in str(e).lower() or "escapes" in str(e).lower(),
                    f"unexpected message: {e}")
        # Nothing should have been written outside the target.
        _assert(not (Path(d) / "evil.html").exists(), "evil file escaped!")
    print("✓ zip-slip: '../evil.html' rejected, nothing written outside target")


def test_oversized_rejected():
    # Highly compressible payload: small zip, huge uncompressed size.
    big = b"\x00" * (server.MAX_UPLOAD_BYTES + 1024)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("index.html", "<html></html>")
        zf.writestr("blob.json", big)
    raw = buf.getvalue()
    _assert(len(raw) < server.MAX_UPLOAD_BYTES,
            "compressed bomb should be small")
    with tempfile.TemporaryDirectory() as d:
        try:
            server._safe_extract_zip(raw, Path(d) / "site")
            _assert(False, "oversized uncompressed content should be rejected")
        except server.ZipUploadError as e:
            _assert("limit" in str(e).lower() or "bomb" in str(e).lower(),
                    f"unexpected message: {e}")
    print("✓ oversized: zip-bomb (uncompressed > limit) rejected")


def test_no_html_rejected():
    raw = _zip({"css/style.css": "body{}", "js/app.js": "1"})
    with tempfile.TemporaryDirectory() as d:
        rel = server._safe_extract_zip(raw, Path(d) / "site")
        try:
            server._detect_entry_point(rel)
            _assert(False, "a zip with no HTML should be rejected")
        except server.ZipUploadError as e:
            _assert("no html" in str(e).lower(), f"unexpected message: {e}")
    print("✓ no-html: zip without any .html rejected with a clear message")


def test_disallowed_filetype_rejected():
    raw = _zip({"index.html": "<html></html>", "run.exe": b"MZ\x90\x00"})
    with tempfile.TemporaryDirectory() as d:
        try:
            server._safe_extract_zip(raw, Path(d) / "site")
            _assert(False, "executable inside zip should be rejected")
        except server.ZipUploadError as e:
            _assert("disallowed" in str(e).lower(), f"unexpected message: {e}")
    print("✓ disallowed type: '.exe' inside zip rejected")


def test_not_a_zip_rejected():
    with tempfile.TemporaryDirectory() as d:
        try:
            server._safe_extract_zip(b"this is not a zip", Path(d) / "site")
            _assert(False, "non-zip bytes should be rejected")
        except server.ZipUploadError as e:
            _assert("valid .zip" in str(e).lower(), f"unexpected message: {e}")
    print("✓ not-a-zip: plain bytes rejected as invalid archive")


def main():
    tests = [
        test_happy_path,
        test_entry_point_fallbacks,
        test_zip_slip_rejected,
        test_oversized_rejected,
        test_no_html_rejected,
        test_disallowed_filetype_rejected,
        test_not_a_zip_rejected,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"✗ {t.__name__}: {e}")
    print()
    if failed:
        print(f"{failed}/{len(tests)} test(s) FAILED")
        sys.exit(1)
    print(f"All {len(tests)} upload tests passed.")


if __name__ == "__main__":
    main()
