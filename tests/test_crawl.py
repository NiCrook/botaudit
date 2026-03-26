"""Tests for sitemap crawl mode (SPEC-crawl)."""

import unittest
from unittest.mock import patch

from botaudit.crawl import (
    CrawlResult,
    apply_limit,
    filter_by_origin,
    parse_robots_sitemaps,
    parse_sitemap_text,
    parse_sitemap_xml,
)


# ===========================================================================
# FR-2 / NFR-4.1 — Sitemap discovery (pure functions)
# ===========================================================================

class TestParseRobotsSitemaps(unittest.TestCase):
    """FR-2.2/FR-2.3: Extract Sitemap: directives from robots.txt."""

    def test_single_sitemap(self):
        """Basic single Sitemap directive."""
        content = "User-agent: *\nDisallow: /private\nSitemap: https://example.com/sitemap.xml\n"
        result = parse_robots_sitemaps(content)
        self.assertEqual(result, ["https://example.com/sitemap.xml"])

    def test_multiple_sitemaps(self):
        """Multiple Sitemap directives."""
        content = (
            "Sitemap: https://example.com/sitemap1.xml\n"
            "Sitemap: https://example.com/sitemap2.xml\n"
        )
        result = parse_robots_sitemaps(content)
        self.assertEqual(len(result), 2)

    def test_case_insensitive_directive(self):
        """FR-2.2: Sitemap directive is case-insensitive."""
        content = "SITEMAP: https://example.com/sitemap.xml\nsitemap: https://example.com/other.xml\n"
        result = parse_robots_sitemaps(content)
        self.assertEqual(len(result), 2)

    def test_relative_url_skipped(self):
        """FR-2.3: Relative URLs ignored."""
        content = "Sitemap: /sitemap.xml\nSitemap: https://example.com/sitemap.xml\n"
        result = parse_robots_sitemaps(content)
        self.assertEqual(result, ["https://example.com/sitemap.xml"])

    def test_empty_robots(self):
        """No Sitemap directives → empty list."""
        content = "User-agent: *\nDisallow: /\n"
        result = parse_robots_sitemaps(content)
        self.assertEqual(result, [])

    def test_whitespace_handling(self):
        """Whitespace around directive value is stripped."""
        content = "Sitemap:   https://example.com/sitemap.xml   \n"
        result = parse_robots_sitemaps(content)
        self.assertEqual(result, ["https://example.com/sitemap.xml"])


# ===========================================================================
# FR-3 / NFR-4.2 — Sitemap parsing (pure functions)
# ===========================================================================

class TestParseSitemapXml(unittest.TestCase):
    """FR-3.1/FR-3.3/FR-3.4: XML sitemap parsing."""

    def test_urlset(self):
        """FR-3.1: <urlset> → page URLs extracted from <loc>."""
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url><loc>https://example.com/page1</loc></url>"
            "<url><loc>https://example.com/page2</loc></url>"
            "</urlset>"
        )
        pages, children = parse_sitemap_xml(xml)
        self.assertEqual(pages, ["https://example.com/page1", "https://example.com/page2"])
        self.assertEqual(children, [])

    def test_sitemapindex(self):
        """FR-3.1: <sitemapindex> → child sitemap URLs extracted."""
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<sitemap><loc>https://example.com/sitemap1.xml</loc></sitemap>"
            "<sitemap><loc>https://example.com/sitemap2.xml</loc></sitemap>"
            "</sitemapindex>"
        )
        pages, children = parse_sitemap_xml(xml)
        self.assertEqual(pages, [])
        self.assertEqual(children, [
            "https://example.com/sitemap1.xml",
            "https://example.com/sitemap2.xml",
        ])

    def test_namespace_aware(self):
        """FR-3.3: Works with explicit namespace prefix."""
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<sm:urlset xmlns:sm="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<sm:url><sm:loc>https://example.com/page1</sm:loc></sm:url>"
            "</sm:urlset>"
        )
        pages, children = parse_sitemap_xml(xml)
        self.assertEqual(pages, ["https://example.com/page1"])

    def test_ignores_non_loc_elements(self):
        """FR-3.4: Only <loc> extracted; lastmod/changefreq/priority ignored."""
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "<url>"
            "<loc>https://example.com/page1</loc>"
            "<lastmod>2026-01-01</lastmod>"
            "<changefreq>daily</changefreq>"
            "<priority>0.8</priority>"
            "</url>"
            "</urlset>"
        )
        pages, children = parse_sitemap_xml(xml)
        self.assertEqual(pages, ["https://example.com/page1"])

    def test_empty_urlset(self):
        """Empty <urlset> returns no URLs."""
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            "</urlset>"
        )
        pages, children = parse_sitemap_xml(xml)
        self.assertEqual(pages, [])
        self.assertEqual(children, [])


class TestParseSitemapText(unittest.TestCase):
    """FR-3.1: Plain text sitemap parsing."""

    def test_basic(self):
        """One URL per line."""
        content = "https://example.com/page1\nhttps://example.com/page2\n"
        result = parse_sitemap_text(content)
        self.assertEqual(result, ["https://example.com/page1", "https://example.com/page2"])

    def test_blank_lines_skipped(self):
        """Blank lines ignored."""
        content = "https://example.com/page1\n\nhttps://example.com/page2\n"
        result = parse_sitemap_text(content)
        self.assertEqual(len(result), 2)

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace stripped."""
        content = "  https://example.com/page1  \n"
        result = parse_sitemap_text(content)
        self.assertEqual(result, ["https://example.com/page1"])


# ===========================================================================
# FR-4 / NFR-4.3 — Scope filtering (pure functions)
# ===========================================================================

class TestFilterByOrigin(unittest.TestCase):
    """FR-4.1: Origin-based URL filtering."""

    def test_same_origin_kept(self):
        """URLs matching origin are kept."""
        urls = ["https://example.com/page1", "https://example.com/page2"]
        result = filter_by_origin(urls, "https://example.com")
        self.assertEqual(result, urls)

    def test_different_origin_excluded(self):
        """FR-4.1: Different origins silently excluded."""
        urls = [
            "https://example.com/page1",
            "https://other.com/page2",
            "https://example.com/page3",
        ]
        result = filter_by_origin(urls, "https://example.com")
        self.assertEqual(result, ["https://example.com/page1", "https://example.com/page3"])

    def test_scheme_mismatch_excluded(self):
        """http vs https counts as different origin."""
        urls = ["http://example.com/page1", "https://example.com/page2"]
        result = filter_by_origin(urls, "https://example.com")
        self.assertEqual(result, ["https://example.com/page2"])

    def test_port_mismatch_excluded(self):
        """Different ports count as different origin."""
        urls = ["https://example.com:8080/page1", "https://example.com/page2"]
        result = filter_by_origin(urls, "https://example.com")
        self.assertEqual(result, ["https://example.com/page2"])

    def test_preserves_order(self):
        """Filtered list maintains original order."""
        urls = [
            "https://example.com/c",
            "https://other.com/x",
            "https://example.com/a",
            "https://example.com/b",
        ]
        result = filter_by_origin(urls, "https://example.com")
        self.assertEqual(result, [
            "https://example.com/c",
            "https://example.com/a",
            "https://example.com/b",
        ])


# ===========================================================================
# FR-5 / NFR-4.3 — Limit application (pure functions)
# ===========================================================================

class TestApplyLimit(unittest.TestCase):
    """FR-5: --crawl-limit behavior."""

    def test_no_limit(self):
        """FR-5.3: No limit → all URLs returned."""
        urls = [f"https://example.com/{i}" for i in range(10)]
        result = apply_limit(urls, None, quiet=True)
        self.assertEqual(len(result), 10)

    def test_limit_applied(self):
        """FR-5.1: Take first N URLs."""
        urls = [f"https://example.com/{i}" for i in range(10)]
        result = apply_limit(urls, 3, quiet=True)
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0], "https://example.com/0")
        self.assertEqual(result[2], "https://example.com/2")

    def test_limit_greater_than_count(self):
        """Limit larger than URL count → all returned."""
        urls = ["https://example.com/a", "https://example.com/b"]
        result = apply_limit(urls, 100, quiet=True)
        self.assertEqual(len(result), 2)

    def test_warn_over_100_no_limit(self):
        """FR-5.4: Warning when >100 URLs and no limit."""
        urls = [f"https://example.com/{i}" for i in range(101)]
        with patch("sys.stderr") as mock_stderr:
            result = apply_limit(urls, None, quiet=False)
            self.assertEqual(len(result), 101)


# ===========================================================================
# FR-7.2 — CrawlResult data model
# ===========================================================================

class TestCrawlResult(unittest.TestCase):
    """CrawlResult metadata structure."""

    def test_default_values(self):
        cr = CrawlResult(origin="https://example.com")
        self.assertEqual(cr.origin, "https://example.com")
        self.assertEqual(cr.sitemaps_found, 0)
        self.assertEqual(cr.urls_discovered, 0)
        self.assertEqual(cr.urls_after_filter, 0)
        self.assertEqual(cr.urls_after_limit, 0)

    def test_populated(self):
        cr = CrawlResult(
            origin="https://example.com",
            sitemaps_found=3,
            urls_discovered=247,
            urls_after_filter=247,
            urls_after_limit=50,
        )
        self.assertEqual(cr.sitemaps_found, 3)
        self.assertEqual(cr.urls_after_limit, 50)


if __name__ == "__main__":
    unittest.main()
