"""The participant deliverable must be complete, portable and reproducible."""

from html.parser import HTMLParser
import base64
import re
import xml.etree.ElementTree as ET

from scripts.build_guide import LABS, OUTPUT, PAGES, ROOT, build, render_page
from scripts.serve_guide import GUIDE


class Document(HTMLParser):
    def __init__(self, content):
        super().__init__()
        self.tags = []
        self.text = []
        self.feed(content)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, data):
        self.text.append(data)


def test_static_guide_is_current():
    assert OUTPUT.exists(), "Run uv run poe docs-build"
    assert OUTPUT.read_text(encoding="utf-8") == build()


def test_new_loop_and_promotion_commands_are_in_web_guide():
    for page in ("lab6", "reference"):
        text = "".join(Document(render_page(page)).text)
        for command in (
            "uv run poe loop --limit 3",
            "uv run poe loop --limit 3 --offline",
            "uv run poe promote-force --version v3",
            "uv run poe promote --version v3 --force",
        ):
            assert command in text
    lab6 = "".join(Document(render_page("lab6")).text)
    assert "bypasses the validation requirement" in lab6
    assert "uv run poe loop --limit 3 --judge-delay 10" in lab6


def test_every_page_and_lab_is_bundled():
    content = build()
    document = Document(content)
    page_ids = {attrs["id"] for tag, attrs in document.tags if tag == "section"}
    assert page_ids == {"home", *PAGES}
    cards = [attrs for tag, attrs in document.tags if attrs.get("class") == "lab-card"]
    assert len(cards) == len(LABS) == 7
    assert {card["href"] for card in cards} == {f"#lab{i}" for i in range(7)}
    assert "Screenshot placeholder" not in content
    assert "{{" not in content


def test_static_guide_has_no_runtime_asset_dependencies():
    document = Document(build())
    for tag, attrs in document.tags:
        assert tag not in {"iframe", "object"}
        if tag == "img":
            assert attrs.get("src", "").startswith("data:image/svg+xml;base64,")
        elif tag in {"script", "link", "source", "video", "audio"}:
            assert not attrs.get("src")
            assert not attrs.get("href")
    javascript = (ROOT / "scripts" / "guide" / "guide.js").read_text(encoding="utf-8")
    assert not re.search(r"\b(fetch|XMLHttpRequest|WebSocket)\s*\(", javascript)
    assert GUIDE == OUTPUT.parent


def test_lab_illustrations_are_distinct_accessible_and_embedded():
    expected = (
        ("lab0-smoke-test.svg",),
        ("lab1-safety-boundaries.svg",),
        ("lab2-tool-orchestration.svg",),
        ("lab3-a2a-citations.svg",),
        ("lab4-local-trace.svg", "lab4-end-to-end-trace.svg"),
        ("lab5-evaluation-gate.svg", "lab5-run-comparison.svg"),
        ("lab6-improvement-lineage.svg",),
    )
    payloads = []
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    for number, names in enumerate(expected):
        document = Document(render_page(f"lab{number}"))
        images = [attrs for tag, attrs in document.tags if tag == "img"]
        assert len(images) == len(names)
        for attrs, name in zip(images, names, strict=True):
            assert attrs["alt"].startswith("Illustration:")
            content = base64.b64decode(attrs["src"].split(",", 1)[1], validate=True)
            assert content == (ROOT / "docs" / "images" / name).read_text(encoding="utf-8").encode("utf-8")
            svg = ET.fromstring(content)
            assert svg.get("viewBox") and svg.get("role") == "img"
            assert svg.find("svg:title", namespace).text.startswith(f"Lab {number}:")
            assert svg.find("svg:desc", namespace).text
            assert "ILLUSTRATION / NOT A" in "".join(svg.itertext())
            assert svg.find(".//svg:script", namespace) is None
            payloads.append(content)
        markdown_source = (ROOT / "docs" / f"lab{number}.md").read_text(encoding="utf-8")
        assert all(f"](images/{name})" in markdown_source for name in names)
    assert len(set(payloads)) == 9


def test_internal_routes_resolve_and_ids_are_unique():
    document = Document(build())
    ids = [attrs["id"] for _, attrs in document.tags if "id" in attrs]
    assert len(ids) == len(set(ids))
    for tag, attrs in document.tags:
        if tag != "a":
            continue
        href = attrs.get("href", "")
        if href.startswith("#"):
            target, _, fragment = href[1:].partition("/")
            assert target in ids, href
            if fragment:
                assert f"{target}--{fragment}" in ids, href
        else:
            assert not href.endswith(".md"), f"Unconverted Markdown link: {href}"
    for _, attrs in document.tags:
        if "for" in attrs:
            assert attrs["for"] in ids


def test_all_labs_keep_steps_code_and_verification():
    expected_steps = (5, 6, 5, 5, 4, 8, 5)
    for number, count in enumerate(expected_steps):
        page = render_page(f"lab{number}")
        document = Document(page)
        assert sum(attrs.get("class") == "admonition dothis" for _, attrs in document.tags) == count
        assert sum(attrs.get("class") == "admonition checkpoint" for _, attrs in document.tags) == 1
        for heading in ("Steps", "Expected output", "Troubleshooting", "What you just proved"):
            assert f">{heading}</h2>" in page
        assert "uv run poe" in "".join(document.text)
        assert "```" not in page
    for name in ("index", "setup", "lab1", "lab2", "lab3", "lab4", "lab5", "lab6"):
        rendered = render_page(name)
        assert '<figure class="flow">' in rendered
        assert "Read the detailed diagram source" in rendered


def test_browser_controls_and_accessibility_basics():
    content = build()
    assert '<html lang="en">' in content
    assert 'name="viewport"' in content
    for control in ("reset-progress", "progress", "print", "announcement", "storage-notice", "route-notice"):
        assert f'id="{control}"' in content
    assert "<noscript>" in content
    assert 'class="skip-link"' in content
    assert "prefers-reduced-motion" in content
