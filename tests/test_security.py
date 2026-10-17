"""Security control tests. Every control in security.py is exercised here."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cortexforge.security import (  # noqa: E402
    SecurityError, assert_parameterised, check_archive_budget, check_file_size,
    constant_time_compare, escape_html, load_json_only, load_yaml_safe,
    parse_xml_safe, redact, safe_join, safe_merge, sanitise_text,
    secure_token, security_headers, validate_outbound_url,
)


class TestPathTraversal(unittest.TestCase):
    """CVE-2021-42740 / zip-slip class: containment must hold."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        (self.base / "sub").mkdir()
        (self.base / "sub" / "ok.txt").write_text("fine")

    def tearDown(self):
        self.tmp.cleanup()

    def test_allows_contained_path(self):
        p = safe_join(self.base, "sub", "ok.txt")
        self.assertTrue(str(p).startswith(str(self.base)))

    def test_blocks_parent_traversal(self):
        with self.assertRaises(SecurityError):
            safe_join(self.base, "..", "..", "etc", "passwd")

    def test_blocks_nested_traversal(self):
        with self.assertRaises(SecurityError):
            safe_join(self.base, "sub", "..", "..", "outside")

    def test_blocks_absolute_path(self):
        with self.assertRaises(SecurityError):
            safe_join(self.base, "/etc/passwd")

    def test_blocks_windows_drive(self):
        with self.assertRaises(SecurityError):
            safe_join(self.base, "C:\\Windows\\System32")

    def test_blocks_unc_path(self):
        with self.assertRaises(SecurityError):
            safe_join(self.base, "\\\\server\\share")

    def test_blocks_nul_byte(self):
        with self.assertRaises(SecurityError):
            safe_join(self.base, "ok\x00.txt")

    def test_blocks_symlink_escape(self):
        link = self.base / "escape"
        try:
            link.symlink_to("/etc")
        except OSError:
            self.skipTest("cannot create symlink")
        with self.assertRaises(SecurityError):
            safe_join(self.base, "escape", "passwd")

    def test_file_size_cap(self):
        big = self.base / "big.bin"
        big.write_bytes(b"x" * 100)
        with self.assertRaises(SecurityError):
            check_file_size(big, limit=10)
        self.assertEqual(check_file_size(big, limit=1000), 100)


class TestArchiveBudget(unittest.TestCase):
    """CVE-2019-1010206 / CVE-2023-45853: zip bombs."""

    def test_accepts_reasonable_archive(self):
        check_archive_budget(1000, [{"name": "a.txt", "size": 5000}])

    def test_blocks_ratio_bomb(self):
        with self.assertRaises(SecurityError):
            check_archive_budget(1000, [{"name": "a", "size": 10_000_000}])

    def test_blocks_too_many_entries(self):
        entries = [{"name": f"f{i}", "size": 1} for i in range(20_000)]
        with self.assertRaises(SecurityError):
            check_archive_budget(1000, entries)

    def test_blocks_traversal_member(self):
        with self.assertRaises(SecurityError):
            check_archive_budget(1000, [{"name": "../../etc/passwd", "size": 10}])

    def test_blocks_absolute_member(self):
        with self.assertRaises(SecurityError):
            check_archive_budget(1000, [{"name": "/etc/passwd", "size": 10}])

    def test_blocks_nul_member(self):
        with self.assertRaises(SecurityError):
            check_archive_budget(1000, [{"name": "a\x00b", "size": 10}])


class TestXML(unittest.TestCase):
    """CVE-2022-25314 / CVE-2023-43644: XXE and entity expansion."""

    def test_parses_plain_xml(self):
        root = parse_xml_safe("<a><b>1</b></a>")
        self.assertEqual(root.tag, "a")

    def test_blocks_doctype(self):
        with self.assertRaises(SecurityError):
            parse_xml_safe('<?xml version="1.0"?><!DOCTYPE a [<!ENTITY x "y">]><a/>')

    def test_blocks_billion_laughs(self):
        payload = ('<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
                   '<!ENTITY lol2 "&lol;&lol;">]><lolz>&lol2;</lolz>')
        with self.assertRaises(SecurityError):
            parse_xml_safe(payload)

    def test_blocks_external_entity(self):
        payload = ('<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
                   '<foo>&xxe;</foo>')
        with self.assertRaises(SecurityError):
            parse_xml_safe(payload)

    def test_blocks_malformed(self):
        with self.assertRaises(SecurityError):
            parse_xml_safe("<a><b></a>")


class TestYAML(unittest.TestCase):
    """CVE-2020-14343: unsafe YAML construction."""

    def test_loads_plain(self):
        """PyYAML is optional; when absent the JSON fallback must still work."""
        try:
            import yaml  # noqa: F401
            self.assertEqual(load_yaml_safe("a: 1"), {"a": 1})
        except ImportError:
            self.assertEqual(load_yaml_safe('{"a": 1}'), {"a": 1})

    def test_blocks_python_tag(self):
        with self.assertRaises(SecurityError):
            load_yaml_safe("!!python/object/apply:os.system ['echo hi']")

    def test_blocks_exec_tag(self):
        with self.assertRaises(SecurityError):
            load_yaml_safe("x: !!exec 'import os'")

    def test_falls_back_to_json(self):
        self.assertEqual(load_yaml_safe('{"a": 1}'), {"a": 1})


class TestJSON(unittest.TestCase):
    """Prototype pollution and depth bombs."""

    def test_parses_plain(self):
        self.assertEqual(load_json_only('{"a": 1}'), {"a": 1})

    def test_blocks_proto_key(self):
        with self.assertRaises(SecurityError):
            load_json_only('{"__proto__": {"polluted": true}}')

    def test_blocks_constructor_key(self):
        with self.assertRaises(SecurityError):
            load_json_only('{"constructor": {"x": 1}}')

    def test_blocks_duplicate_keys(self):
        with self.assertRaises(SecurityError):
            load_json_only('{"a": 1, "a": 2}')

    def test_blocks_deep_nesting(self):
        payload = "[" * 200 + "]" * 200
        with self.assertRaises(SecurityError):
            load_json_only(payload)

    def test_blocks_malformed(self):
        with self.assertRaises(SecurityError):
            load_json_only("{not json")

    def test_safe_merge_rejects_pollution(self):
        with self.assertRaises(SecurityError):
            safe_merge({"a": 1}, {"__proto__": {"x": 1}})

    def test_safe_merge_deep(self):
        out = safe_merge({"a": {"b": 1}}, {"a": {"c": 2}})
        self.assertEqual(out, {"a": {"b": 1, "c": 2}})


class TestSSRF(unittest.TestCase):
    """CVE-2024-28849 class: outbound URL validation."""

    def test_allows_public_https(self):
        self.assertTrue(validate_outbound_url("https://example.com/mcp"))

    def test_blocks_loopback(self):
        with self.assertRaises(SecurityError):
            validate_outbound_url("http://127.0.0.1/admin")

    def test_blocks_localhost_name(self):
        with self.assertRaises(SecurityError):
            validate_outbound_url("http://localhost:8731/")

    def test_blocks_metadata_endpoint(self):
        with self.assertRaises(SecurityError):
            validate_outbound_url("http://169.254.169.254/latest/meta-data/")

    def test_blocks_private_10(self):
        with self.assertRaises(SecurityError):
            validate_outbound_url("http://10.0.0.5/")

    def test_blocks_private_192(self):
        with self.assertRaises(SecurityError):
            validate_outbound_url("http://192.168.1.1/")

    def test_blocks_ipv6_loopback(self):
        with self.assertRaises(SecurityError):
            validate_outbound_url("http://[::1]/")

    def test_blocks_file_scheme(self):
        with self.assertRaises(SecurityError):
            validate_outbound_url("file:///etc/passwd")

    def test_blocks_gopher_scheme(self):
        with self.assertRaises(SecurityError):
            validate_outbound_url("gopher://evil/")

    def test_blocks_credentials_in_url(self):
        with self.assertRaises(SecurityError):
            validate_outbound_url("https://user:pass@example.com/")

    def test_blocks_control_chars(self):
        with self.assertRaises(SecurityError):
            validate_outbound_url("https://example.com/\r\nHost: evil")

    def test_blocks_empty(self):
        with self.assertRaises(SecurityError):
            validate_outbound_url("")

    def test_allows_private_when_explicit(self):
        self.assertTrue(validate_outbound_url("http://10.0.0.5/", allow_private=True))


class TestEncoding(unittest.TestCase):
    """Stored XSS and log injection."""

    def test_escapes_script(self):
        out = escape_html("<script>alert(1)</script>")
        self.assertNotIn("<script>", out)
        self.assertIn("&lt;script&gt;", out)

    def test_escapes_quotes(self):
        out = escape_html('" onmouseover="x')
        self.assertNotIn('"', out)

    def test_escapes_ampersand(self):
        self.assertEqual(escape_html("a & b"), "a &amp; b")

    def test_sanitise_strips_control(self):
        out = sanitise_text("hello\x07\x1b[31mworld")
        self.assertNotIn("\x07", out)
        self.assertNotIn("\x1b", out)
        self.assertIn("hello", out)

    def test_sanitise_keeps_newline(self):
        self.assertIn("\n", sanitise_text("a\nb"))

    def test_sanitise_caps_length(self):
        self.assertEqual(len(sanitise_text("x" * 1000, limit=10)), 10)

    def test_sanitise_rejects_non_string(self):
        with self.assertRaises(SecurityError):
            sanitise_text(123)  # type: ignore[arg-type]

    def test_csp_present(self):
        h = security_headers()
        self.assertIn("Content-Security-Policy", h)
        self.assertIn("default-src 'none'", h["Content-Security-Policy"])
        self.assertEqual(h["X-Content-Type-Options"], "nosniff")
        self.assertEqual(h["X-Frame-Options"], "DENY")


class TestSecrets(unittest.TestCase):
    """Timing-safe comparison and secure token generation."""

    def test_constant_time_equal(self):
        self.assertTrue(constant_time_compare("abc123", "abc123"))

    def test_constant_time_unequal(self):
        self.assertFalse(constant_time_compare("abc123", "abc124"))

    def test_constant_time_length_mismatch(self):
        self.assertFalse(constant_time_compare("abc", "abcdef"))

    def test_token_is_random(self):
        a, b = secure_token(), secure_token()
        self.assertNotEqual(a, b)
        self.assertGreater(len(a), 20)

    def test_redact(self):
        out = redact("supersecrettoken", keep=4)
        self.assertTrue(out.startswith("supe"))
        self.assertNotIn("secret", out)

    def test_redact_short(self):
        self.assertEqual(redact("abc", keep=4), "***")

    def test_redact_empty(self):
        self.assertEqual(redact(""), "")


class TestSQLGuard(unittest.TestCase):
    """CVE-2022-31197 class: SQL injection via interpolation."""

    def test_accepts_parameterised(self):
        assert_parameterised("SELECT * FROM t WHERE a = ?", ("x",))

    def test_accepts_no_params(self):
        assert_parameterised("SELECT COUNT(*) FROM t", ())

    def test_blocks_fstring(self):
        with self.assertRaises(SecurityError):
            assert_parameterised('SELECT * FROM t WHERE a = f"{x}"', ())

    def test_blocks_percent(self):
        with self.assertRaises(SecurityError):
            assert_parameterised("SELECT * FROM t WHERE a = '%s'", ())

    def test_blocks_format(self):
        with self.assertRaises(SecurityError):
            assert_parameterised("SELECT * FROM t WHERE a = '{}'.format(x)", ())

    def test_blocks_concat_other_side(self):
        with self.assertRaises(SecurityError):
            assert_parameterised("SELECT * FROM t WHERE a = 'x' + ", ())

    def test_blocks_dynamic_table_name(self):
        """A dynamic identifier must be allowlisted, never interpolated."""
        with self.assertRaises(SecurityError):
            assert_parameterised("DELETE FROM {} WHERE id = ?", ("t",))
        with self.assertRaises(SecurityError):
            assert_parameterised("DELETE FROM %s WHERE id = ?", ("t",))

    def test_documents_concat_limit(self):
        """Honest limit: a value concatenated at Python parse time arrives as
        a single literal and is indistinguishable from a safe literal. The
        guard catches interpolation *syntax*, not already-joined strings, so
        callers must never build SQL by concatenation in the first place."""
        joined = "SELECT * FROM t WHERE a = '" + "x'"
        assert_parameterised(joined, ())  # passes: no syntax to detect
        self.assertEqual(joined, "SELECT * FROM t WHERE a = 'x'")

    def test_blocks_empty(self):
        with self.assertRaises(SecurityError):
            assert_parameterised("", ())

    def test_blocks_bad_param_type(self):
        with self.assertRaises(SecurityError):
            assert_parameterised("SELECT 1", "notatuple")  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main(verbosity=2)
