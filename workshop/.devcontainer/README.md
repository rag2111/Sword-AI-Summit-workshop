# Dev Container / Codespaces

Zero-install alternative to the local setup (VS Code + Git + uv).

**Codespaces:** on the repository page choose *Code → Codespaces → Create codespace*. If the repository root is
`care-coordination-workshop/`, open the `workshop/` folder in the Codespace terminal (`cd workshop`) — or set the
dev container path to `workshop/.devcontainer/devcontainer.json` when creating the Codespace
(*New with options… → Dev container configuration*).

**VS Code Dev Containers:** open `workshop/` locally and run *Dev Containers: Reopen in Container*.

What happens: Python 3.12 image + uv, `uv sync`, `.env` created from `.env.example`, recommended extensions.
Then paste your three values into `.env` and run `uv run poe smoke`.

Ports 8000 (`uv run poe docs`) and 8080 (`uv run poe devui`) are forwarded automatically.
Your `.env` stays inside the container and is git-ignored — do not commit it from the Codespace.
