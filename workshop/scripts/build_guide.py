"""Build the self-contained, offline participant guide from the canonical docs."""

from __future__ import annotations

import argparse
import base64
import html
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "scripts" / "guide"
OUTPUT = ROOT / "guide" / "index.html"
PAGES = ("index", "setup", *(f"lab{i}" for i in range(7)), "wrap-up", "troubleshooting", "reference")
LABS = (
    ("Connect your workspace", "Setup", "5", "One key. Five routes. Ready to build."),
    ("Build your first agent", "Build", "15", "A conversation with clear safety boundaries."),
    ("Give your agent tools", "Connect", "10", "Discover and orchestrate seven tools over MCP."),
    ("Bring in a policy expert", "Delegate", "15", "Two agents, one contract, traceable citations."),
    ("Follow every request", "Observe", "10", "Turn model and tool calls into an end-to-end trace."),
    ("Measure what matters", "Evaluate", "20", "Weighted scores, hard safety gates and red teaming."),
    ("Close the improvement loop", "Improve", "10", "Validate a change. Keep the lineage. Roll it back."),
)
FLOWS = {
    "index": ("Your local agent", "APIM gateway / one key", "Models + MCP + A2A", "Traces + evaluations"),
    "setup": ("Your laptop", "HTTPS + subscription key", "APIM validates + correlates", "Managed backend"),
    "lab1": ("Instructions + safety", "Agent + chat client", "APIM /openai", "Model response"),
    "lab2": ("Discover 7 MCP tools", "Read the care plan", "Find an available slot", "Book + verify"),
    "lab3": ("Check prior authorization", "Read the Agent Card", "Ask the policy expert", "Retrieve policy", "Return citations"),
    "lab4": ("care_agent.turn", "invoke_agent", "chat / execute_tool", "APIM child spans", "Backend spans"),
    "lab5": ("Golden cases", "Run + capture traces", "Judge + weight", "Apply safety gates", "Compare runs"),
    "lab6": ("Pull failures", "Rank + propose", "Validate vs baseline", "Promote or reject", "Keep lineage + rollback"),
}


def flow_diagram(page: str, source: str) -> str:
    nodes = "".join(f"<li>{html.escape(label)}</li>" for label in FLOWS[page])
    return (
        '<figure class="flow"><figcaption>HOW IT WORKS <span>Simplified flow</span></figcaption>'
        f'<ol>{nodes}</ol><details><summary>Read the detailed diagram source</summary>'
        f"<pre><code>{html.escape(source.strip())}</code></pre></details></figure>"
    )


def render_page(page: str) -> str:
    source = (ROOT / "docs" / f"{page}.md").read_text(encoding="utf-8")
    # Preserve the detailed Mermaid source, but render a native offline visual instead of loading a CDN.
    source = re.sub(
        r"(?m)^([ ]*)```mermaid\n(.*?)^\1```",
        lambda match: "\n".join(
            match[1] + line for line in flow_diagram(page, match[2]).splitlines()
        ),
        source,
        flags=re.S,
    )
    rendered = markdown.markdown(
        source,
        extensions=["extra", "admonition", "toc", "pymdownx.superfences", "pymdownx.tabbed", "pymdownx.tasklist"],
        extension_configs={"pymdownx.tabbed": {"alternate_style": True}},
    )
    # Embed local illustrations so the exported HTML can still be moved and opened on its own.
    def embed_image(match: re.Match[str]) -> str:
        name = match[1]
        image = ROOT / "docs" / "images" / name
        encoded = base64.b64encode(image.read_text(encoding="utf-8").encode("utf-8")).decode("ascii")
        return f'src="data:image/svg+xml;base64,{encoded}"'

    rendered = re.sub(r'src="images/([\w-]+\.svg)"', embed_image, rendered)
    # Page-qualified fragments avoid duplicate heading / tab IDs in a single HTML document.
    rendered = re.sub(r'\b(id|for)="([^"]+)"', rf'\1="{page}--\2"', rendered)
    rendered = re.sub(r'\bname="(__tabbed_[^"]+)"', rf'name="{page}--\1"', rendered)
    rendered = re.sub(r'href="#([^"]+)"', rf'href="#{page}/\1"', rendered)
    rendered = re.sub(
        r'href="([\w-]+)\.md(?:#([^"]+))?"',
        lambda match: f'href="#{match[1]}' + (f"/{match[2]}" if match[2] else "") + '"',
        rendered,
    )
    return f'<section class="page" id="{page}" aria-label="{page}">\n{rendered}\n</section>'


def build() -> str:
    cards, links = [], []
    for number, (title, phase, minutes, description) in enumerate(LABS):
        cards.append(
            f'<a class="lab-card" href="#lab{number}" data-lab="lab{number}">'
            f'<span class="card-top"><span class="lab-number">{number:02}</span>'
            f'<span>{minutes} MIN</span></span><span class="eyebrow">{phase}</span>'
            f'<h3>{title}</h3><p>{description}</p>'
            f'<span class="card-bottom"><span class="card-status">Not started</span>'
            f'<span aria-hidden="true">&rarr;</span></span></a>'
        )
        links.append(
            f'<a href="#lab{number}" data-lab="lab{number}"><span class="nav-number">{number:02}</span>'
            f'<span>{title}</span><span class="nav-status" aria-label="Not started"></span></a>'
        )
    replacements = {
        "{{STYLE}}": (ASSETS / "guide.css").read_text(encoding="utf-8"),
        "{{SCRIPT}}": (ASSETS / "guide.js").read_text(encoding="utf-8"),
        "{{CARDS}}": "\n".join(cards),
        "{{LAB_LINKS}}": "\n".join(links),
        "{{PAGES}}": "\n".join(render_page(page) for page in PAGES),
    }
    output = (ASSETS / "shell.html").read_text(encoding="utf-8")
    for token, value in replacements.items():
        output = output.replace(token, value)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if the committed guide is stale.")
    args = parser.parse_args()
    content = build()
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != content:
            print("Static guide is stale. Run: python scripts/build_guide.py")
            return 1
        print("Static guide is up to date.")
        return 0
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(content, encoding="utf-8", newline="\n")
    print(f"Built {OUTPUT} (open directly in your browser; no server required).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
