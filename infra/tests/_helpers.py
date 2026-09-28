"""Shared helpers for the infra tests (no third-party imports)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

INFRA = Path(__file__).resolve().parents[1]
BACKEND = INFRA / "apps" / "care_tools_backend"
DOCS = INFRA / "data" / "care-docs"
POLICIES = INFRA / "modules" / "apim_apis" / "policies"
GLOBAL_POLICY = INFRA / "modules" / "apim" / "policies" / "global.xml"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

CONTRACT_TOOLS = {
    "search_patient": ("GET", "/patients/search"),
    "get_care_plan": ("GET", "/patients/{patient_id}/care-plan"),
    "list_available_slots": ("GET", "/slots"),
    "book_follow_up": ("POST", "/appointments"),
    "create_referral": ("POST", "/referrals"),
    "check_medication_interactions": ("POST", "/medications/interactions"),
    "check_prior_auth_requirement": ("GET", "/prior-auth"),
}

_DIRECTIVE = re.compile(r"%\{\s*(if\s+(!?)(\w+)|else|endif)\s*(~?)\}")


def render_template(text: str, variables: dict) -> str:
    """Minimal Terraform templatefile() emulation for the subset used by the policy templates:
    ${name}, %{ if name ~} / %{ else ~} / %{ endif ~} (the ~ strips following whitespace)."""
    out, stack, active, pos = [], [], True, 0
    for m in _DIRECTIVE.finditer(text):
        if active:
            out.append(text[pos:m.start()])
        token = m.group(1)
        if token.startswith("if"):
            value = bool(variables[m.group(3)])
            cond = not value if m.group(2) == "!" else value
            stack.append((active, cond))
            active = active and cond
        elif token == "else":
            parent, cond = stack[-1]
            active = parent and not cond
        else:
            parent, _ = stack.pop()
            active = parent
        pos = m.end()
        if m.group(4) == "~":
            while pos < len(text) and text[pos] in " \t\r\n":
                pos += 1
    assert not stack, "unbalanced %{ if } directives"
    if active:
        out.append(text[pos:])

    def substitute(match: re.Match) -> str:
        value = variables[match.group(1)]
        return str(value).lower() if isinstance(value, bool) else str(value)

    rendered = re.sub(r"\$\{(\w+)\}", substitute, "".join(out))
    assert "${" not in rendered and "%{" not in rendered, "unrendered template markers left"
    return rendered


def markdown_table(text: str, first_header: str) -> list[list[str]]:
    """Return the body rows of the markdown table whose first header cell equals `first_header`."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and cells and cells[0] == first_header:
            rows = []
            for body in lines[i + 2:]:
                if not body.startswith("|"):
                    break
                rows.append([c.strip() for c in body.strip().strip("|").split("|")])
            return rows
    raise AssertionError(f"table starting with '{first_header}' not found")
