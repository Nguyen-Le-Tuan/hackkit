"""Turn the template into YOUR project in one command (run it right after kickoff):

    make init-project NAME="NOCO Scout" TAGLINE="From an address to a quote in seconds" \
         TEAM="HELIX · Ana, Bo, Chi, Dan" EVENT="UB AI for Good 2026"

It renames the app (web/config.json, page title), the slides (docs/pitch/deck.toml), the video
title cards (docs/pitch/demo_flow.toml) and the Devpost draft, and writes a product README.md.
The hackkit README moves to docs/HACKKIT.md, so judges see YOUR project first on GitHub.
Safe to re-run: names are replaced wherever the previous name appears.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_TEAM = "Team NAME · Ana, Bo, Chi, Dan"

README = """# {name}

**{tagline}**

{event_line}[Try it]({try_url}) · [Demo video](VIDEO_URL) · [Devpost](DEVPOST_URL)

![{name}](docs/pitch/shots/home.png)

## The problem

Who has it, in their words, and one real number. (Replace this paragraph.)

## What it does

1. **Input:** what the user gives (text, a file, an address...).
2. **The model reads it:** an LLM turns it into validated, structured data with its confidence.
3. **Code checks it:** plain, tested Python does the math and rules and flags what a human should
   review. The model never decides a number.

## Try it

```bash
make setup && source .venv/bin/activate
make run          # http://localhost:8000  (LLM provider from .env; `make demo` needs no key)
```

No Python? Open the static demo: {try_url}

## How it is built

| Part | Technology |
|---|---|
| Model access | Anthropic / Groq / Ollama, one interface, schema-validated output + retry |
| Rules and math | Deterministic Python with tests (`make test`) and accuracy evals (`make eval`) |
| API and UI | FastAPI + plain HTML/CSS/JS (no build step); runs offline from saved results |

## Data and sources

| Data | Source | Licence |
|---|---|---|
| | | |

## Team

{team}

## Disclosure

Built during {event} on top of [hackkit](docs/HACKKIT.md), the team's pre-existing, challenge-
agnostic hackathon template (LLM plumbing, UI kit, pitch tools). Everything specific to this
challenge was written during the event. AI coding assistants were used.
"""


def replace_in(path: Path, old: str, new: str) -> bool:
    if not path.exists() or not old or old == new:
        return False
    text = path.read_text(encoding="utf-8")
    if old not in text:
        return False
    path.write_text(text.replace(old, new), encoding="utf-8")
    return True


def git_remote_pages_url() -> str:
    try:
        url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "TRY_URL"
    match = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", url)
    return f"https://{match.group(1)}.github.io/{match.group(2)}/" if match else "TRY_URL"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rename the template to your project.")
    parser.add_argument("--name", required=True)
    parser.add_argument("--tagline", required=True)
    parser.add_argument("--team", default="Team NAME")
    parser.add_argument("--event", default="the hackathon")
    args = parser.parse_args(argv)

    config_path = ROOT / "web" / "config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    old_name = config.get("name", "hackkit")
    old_tagline = config.get("tagline", "")
    old_team = config.get("team", TEMPLATE_TEAM)
    config["name"] = args.name
    config["tagline"] = args.tagline
    config["team"] = args.team
    config["event"] = args.event
    hero = config.setdefault("hero", {})
    hero["eyebrow"] = args.event if args.event != "the hackathon" else hero.get("eyebrow", "")
    hero["title"] = args.tagline
    hero["highlight"] = ""
    try_url = git_remote_pages_url()
    config.setdefault("links", {})["repo"] = (
        try_url.replace(".github.io/", "/").replace("https://", "https://github.com/")
        if try_url != "TRY_URL"
        else ""
    )
    config_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    changed = ["web/config.json"]

    index = ROOT / "web" / "index.html"
    if replace_in(index, f"<title>{old_name}</title>", f"<title>{args.name}</title>"):
        changed.append("web/index.html")
    text = index.read_text(encoding="utf-8")
    text = re.sub(
        r'(<meta name="description" content=")[^"]*(")', rf"\g<1>{args.tagline}\g<2>", text
    )
    index.write_text(text, encoding="utf-8")

    for rel in ("docs/pitch/deck.toml", "docs/pitch/demo_flow.toml"):
        path = ROOT / rel
        hit = replace_in(path, f'"{old_name}"', f'"{args.name}"')
        hit |= replace_in(path, f"{old_name} ·", f"{args.name} ·")
        if old_tagline:
            hit |= replace_in(path, old_tagline, args.tagline)
        hit |= replace_in(path, old_team, args.team)  # the previous run's team (or the template's)
        hit |= replace_in(path, old_team.split(" · ")[0], args.team.split(" · ")[0])
        if hit:
            changed.append(rel)

    readme = ROOT / "README.md"
    hackkit_doc = ROOT / "docs" / "HACKKIT.md"
    if not hackkit_doc.exists() and readme.exists() and readme.read_text().startswith("# hackkit"):
        hackkit_doc.write_text(readme.read_text(encoding="utf-8"), encoding="utf-8")
        changed.append("docs/HACKKIT.md (the template's README)")
    event_line = f"{args.event} · " if args.event != "the hackathon" else ""
    readme.write_text(
        README.format(
            name=args.name,
            tagline=args.tagline,
            team=args.team,
            event=args.event,
            event_line=event_line,
            try_url=try_url,
        ),
        encoding="utf-8",
    )
    changed.append("README.md")
    replace_in(
        ROOT / "docs" / "SUBMISSION.md",
        "# Devpost submission",
        f"# Devpost submission: {args.name}",
    )

    print("init-project: updated " + ", ".join(changed))
    print("Next: edit web/config.json (impact numbers!), docs/pitch/deck.toml, then `make shots`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
