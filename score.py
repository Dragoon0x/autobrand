"""
score.py — Brand identity scoring.

Evaluates a generation's brand artifacts against the original brief.
Returns a score (0-100) and a written critique that gets fed back
into the next generation as creative direction.

The scoring criteria encode real design principles. Edit them if you
disagree. That's your taste showing up in a different place.
"""

import anthropic
import base64
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SCORE_MODEL = os.getenv("AUTOBRAND_SCORE_MODEL", "claude-sonnet-4-20250514")
BRIEF_PATH = Path("brief.md")

client = anthropic.Anthropic()

# ---------------------------------------------------------------------------
# Scoring prompt
# ---------------------------------------------------------------------------

SCORING_PROMPT = """You are a senior brand design critic evaluating a brand identity system.

You have the original brand brief and the generated artifacts. Score this generation
on a scale of 0-100. Be honest and specific. A score of 50 means "competent but
generic." A score of 80+ means "genuinely good work." Don't grade inflate.

CRITERIA:

**Brief Alignment (30 points)**
- Does the identity match what the brief asked for?
- Does it capture the FEELING described, not just the literal words?
- Does it avoid the anti-references and "never" constraints?

**Color & Palette (15 points)**
- Do the colors work together harmonically?
- Do they meet contrast requirements (WCAG AA)?
- Do they feel intentional? Would they work in light and dark contexts?

**Typography (15 points)**
- Does the type system have hierarchy and rhythm?
- Do the pairings complement each other?
- Does the type feel like it belongs to this brand?

**Logomark (15 points)**
- Is the mark meaningful or just decorative?
- Does it work at favicon size?
- Is the SVG clean and well-constructed?

**Voice & Tone (15 points)**
- Do the taglines sound like this brand, not like any brand?
- Is the microcopy consistent with the stated tone?
- Would you actually use these lines?

**Cohesion (10 points)**
- Do all elements feel like they belong to the same brand?
- If you saw the palette, type, mark, and copy separately, would you know they're related?

Return ONLY valid JSON:
{{
  "score": 0-100,
  "breakdown": {{
    "brief_alignment": {{"score": 0-30, "notes": "..."}},
    "color": {{"score": 0-15, "notes": "..."}},
    "typography": {{"score": 0-15, "notes": "..."}},
    "logomark": {{"score": 0-15, "notes": "..."}},
    "voice": {{"score": 0-15, "notes": "..."}},
    "cohesion": {{"score": 0-10, "notes": "..."}}
  }},
  "strengths": ["what worked well", "another strength"],
  "weaknesses": ["what needs improvement", "another issue"],
  "critique": "A 3-5 sentence overall critique. Be specific about what to change and what to keep. This gets fed directly to the next generation as creative direction.",
  "suggestion": "One specific, concrete mutation to try next. Not vague ('improve colors') but specific ('the accent is too close to the primary, try a complementary hue')."
}}

---

BRAND BRIEF:
{brief}

---

GENERATED ARTIFACTS:

PALETTE:
{palette}

TYPOGRAPHY:
{typography}

LOGOMARK CONCEPT:
{logo}

VOICE:
{voice}
"""


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def load_brief() -> str:
    if not BRIEF_PATH.exists():
        print("ERROR: brief.md not found.")
        sys.exit(1)
    return BRIEF_PATH.read_text()


def load_generation(gen_dir: Path) -> dict:
    artifacts = {}
    for name in ["palette", "typography", "voice"]:
        path = gen_dir / f"{name}.json"
        if path.exists():
            artifacts[name] = json.loads(path.read_text())
    logo_path = gen_dir / "logomark.json"
    if logo_path.exists():
        artifacts["logo"] = json.loads(logo_path.read_text())
    board_path = gen_dir / "board.svg"
    if board_path.exists():
        artifacts["board_svg"] = board_path.read_text()
    return artifacts


def score_generation(brief: str, artifacts: dict) -> dict:
    """Score a generation against the brief."""

    # build content: optional board image + text prompt
    content = []

    board_svg = artifacts.get("board_svg", "")
    if board_svg:
        b64 = base64.standard_b64encode(board_svg.encode("utf-8")).decode("utf-8")
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/svg+xml", "data": b64},
        })

    prompt = SCORING_PROMPT.format(
        brief=brief,
        palette=json.dumps(artifacts.get("palette", {}), indent=2),
        typography=json.dumps(artifacts.get("typography", {}), indent=2),
        logo=json.dumps(artifacts.get("logo", {}), indent=2),
        voice=json.dumps(artifacts.get("voice", {}), indent=2),
    )
    content.append({"type": "text", "text": prompt})

    response = client.messages.create(
        model=SCORE_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": content}],
    )

    text = response.content[0].text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def save_score(gen_dir: Path, score_data: dict) -> None:
    (gen_dir / "score.json").write_text(json.dumps(score_data, indent=2))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run score.py <gen_dir>")
        sys.exit(1)

    gen_dir = Path(sys.argv[1])
    if not gen_dir.exists():
        print(f"ERROR: {gen_dir} not found.")
        sys.exit(1)

    brief = load_brief()
    artifacts = load_generation(gen_dir)

    print(f"scoring {gen_dir}...")
    score_data = score_generation(brief, artifacts)
    save_score(gen_dir, score_data)

    print(f"\nscore: {score_data['score']}/100\n")
    for k, v in score_data.get("breakdown", {}).items():
        print(f"  {k}: {v['score']} — {v['notes'][:80]}")
    print(f"\ncritique: {score_data.get('critique', '')}")
    print(f"suggestion: {score_data.get('suggestion', '')}")
