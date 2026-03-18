"""
generate.py — Brand artifact generation.

Reads brief.md and produces a complete brand identity snapshot:
color palette, typography, logomark (SVG), voice samples, and a
composed brand board. Can mutate a previous generation using
critique feedback from the scoring model.

This file is NOT edited by the agent. The agent only edits brief.md.
"""

import anthropic
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
MODEL = os.getenv("AUTOBRAND_MODEL", "claude-sonnet-4-20250514")
BRIEF_PATH = Path("brief.md")

client = anthropic.Anthropic()

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PALETTE_PROMPT = """You are a brand designer generating a color palette.

Read the brand brief below carefully. Generate a color palette that aligns with
the brief's direction, feeling, and constraints.

Return ONLY valid JSON, no markdown fences, no explanation:
{{
  "colors": {{
    "primary": {{"hex": "#...", "name": "a short evocative name", "role": "what this color does"}},
    "secondary": {{"hex": "#...", "name": "...", "role": "..."}},
    "accent": {{"hex": "#...", "name": "...", "role": "..."}},
    "neutral": {{"hex": "#...", "name": "...", "role": "..."}},
    "background": {{"hex": "#...", "name": "...", "role": "..."}}
  }},
  "reasoning": "2-3 sentences on why these colors match the brief"
}}

BRAND BRIEF:
{brief}

{mutation_context}"""

TYPOGRAPHY_PROMPT = """You are a brand designer selecting typography.

Read the brand brief below. Select a type system that aligns with the brief's direction.
Use only fonts available on Google Fonts.

Return ONLY valid JSON:
{{
  "heading": {{
    "family": "Font Name",
    "weight": "400",
    "style": "normal",
    "role": "why this font for headings"
  }},
  "body": {{
    "family": "Font Name",
    "weight": "400",
    "style": "normal",
    "role": "why this font for body"
  }},
  "functional": {{
    "family": "Font Name",
    "weight": "400",
    "style": "normal",
    "role": "why this font for functional elements"
  }},
  "scale": {{
    "xs": 12, "sm": 14, "base": 16, "lg": 20, "xl": 28, "2xl": 36, "3xl": 48
  }},
  "reasoning": "2-3 sentences on why this type system matches the brief"
}}

BRAND BRIEF:
{brief}

{mutation_context}"""

LOGO_PROMPT = """You are a brand designer creating a logomark.

Read the brand brief below. Create a logomark as clean SVG code.

Rules:
- Must work at 16x16 (favicon) and 200x200
- Use only paths, circles, rects, polygons. No text elements, no embedded fonts.
- Maximum 5KB of SVG code
- Use a single color (primary brand color will be applied later)
- The mark should be meaningful, not generic
- Viewbox must be "0 0 100 100"

Return ONLY valid JSON:
{{
  "svg": "<svg viewBox='0 0 100 100' xmlns='http://www.w3.org/2000/svg'>...</svg>",
  "type": "abstract|wordmark|monogram|symbol",
  "concept": "what the mark represents and why",
  "reasoning": "how this connects to the brief"
}}

BRAND BRIEF:
{brief}

{mutation_context}"""

VOICE_PROMPT = """You are a brand copywriter developing brand voice.

Read the brand brief below. Generate voice and tone samples that match.

Return ONLY valid JSON:
{{
  "taglines": [
    {{"text": "tagline 1", "context": "when/where you'd use this"}},
    {{"text": "tagline 2", "context": "..."}},
    {{"text": "tagline 3", "context": "..."}}
  ],
  "microcopy": [
    {{"text": "example microcopy", "context": "e.g. 404 page, button label, empty state"}},
    {{"text": "...", "context": "..."}},
    {{"text": "...", "context": "..."}}
  ],
  "tone": {{
    "description": "2-3 sentences describing the voice",
    "do": ["write like this", "and this", "and this"],
    "dont": ["never write like this", "or this", "or this"]
  }},
  "reasoning": "how this voice connects to the brief"
}}

BRAND BRIEF:
{brief}

{mutation_context}"""

BOARD_PROMPT = """You are a brand designer composing a brand board.

You have these brand elements as JSON. Compose them into a single SVG brand board
that shows the palette, typography samples, logomark, and a tagline together.

The board should be 800x600, clean, well-spaced, and feel like a professional brand
presentation. Use the actual hex colors from the palette. Show type samples using
SVG text elements with the font names.

Return ONLY the raw SVG code, starting with <svg>. No markdown fences. No explanation.

PALETTE:
{palette}

TYPOGRAPHY:
{typography}

LOGOMARK SVG:
{logo_svg}

VOICE (use the first tagline):
{voice}

PRIMARY COLOR: {primary_color}
BACKGROUND COLOR: {bg_color}"""


# ---------------------------------------------------------------------------
# Mutation context builder
# ---------------------------------------------------------------------------

MUTATE_SECTION = """
MUTATION CONTEXT:
This is generation N+1. The previous generation scored {score}/100.
The scoring model's critique:
{critique}

Specific suggestion:
{suggestion}

Previous generation's output for reference:
{previous_artifacts}

Use this feedback to improve. Keep what worked. Fix what didn't. Don't throw
everything away. Evolve it.
"""


def build_mutation_context(critique: str | None, suggestion: str | None,
                           score: int | None, parent_artifacts: dict | None) -> str:
    if not critique or not parent_artifacts:
        return ""
    return MUTATE_SECTION.format(
        score=score or "?",
        critique=critique or "",
        suggestion=suggestion or "",
        previous_artifacts=json.dumps(parent_artifacts, indent=2)[:3000],
    )


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def load_brief() -> str:
    if not BRIEF_PATH.exists():
        print("ERROR: brief.md not found. Create your brand brief first.")
        sys.exit(1)
    return BRIEF_PATH.read_text()


def call_model(prompt: str, max_tokens: int = 4096) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def generate_palette(brief: str, mutation_ctx: str = "") -> dict:
    return parse_json(call_model(PALETTE_PROMPT.format(brief=brief, mutation_context=mutation_ctx)))


def generate_typography(brief: str, mutation_ctx: str = "") -> dict:
    return parse_json(call_model(TYPOGRAPHY_PROMPT.format(brief=brief, mutation_context=mutation_ctx)))


def generate_logo(brief: str, mutation_ctx: str = "") -> dict:
    return parse_json(call_model(LOGO_PROMPT.format(brief=brief, mutation_context=mutation_ctx)))


def generate_voice(brief: str, mutation_ctx: str = "") -> dict:
    return parse_json(call_model(VOICE_PROMPT.format(brief=brief, mutation_context=mutation_ctx)))


def generate_board(palette: dict, typography: dict, logo: dict, voice: dict) -> str:
    primary = palette.get("colors", {}).get("primary", {}).get("hex", "#333333")
    bg = palette.get("colors", {}).get("background", {}).get("hex", "#FAFAFA")
    tagline = voice.get("taglines", [{}])[0] if voice.get("taglines") else {}
    prompt = BOARD_PROMPT.format(
        palette=json.dumps(palette, indent=2),
        typography=json.dumps(typography, indent=2),
        logo_svg=logo.get("svg", ""),
        voice=json.dumps(tagline, indent=2),
        primary_color=primary,
        bg_color=bg,
    )
    result = call_model(prompt, max_tokens=8000)
    result = re.sub(r"^```(?:svg|xml)?\s*", "", result)
    result = re.sub(r"\s*```$", "", result)
    return result


def generate_full(
    brief: str,
    critique: str | None = None,
    suggestion: str | None = None,
    score: int | None = None,
    parent_artifacts: dict | None = None,
) -> dict:
    """Generate a complete brand identity snapshot."""
    mutation_ctx = build_mutation_context(critique, suggestion, score, parent_artifacts)

    print("  generating palette...")
    palette = generate_palette(brief, mutation_ctx)

    print("  generating typography...")
    typography = generate_typography(brief, mutation_ctx)

    print("  generating logomark...")
    logo = generate_logo(brief, mutation_ctx)

    print("  generating voice...")
    voice = generate_voice(brief, mutation_ctx)

    print("  composing brand board...")
    board_svg = generate_board(palette, typography, logo, voice)

    return {
        "palette": palette,
        "typography": typography,
        "logo": logo,
        "voice": voice,
        "board_svg": board_svg,
    }


def save_generation(gen_num: int, artifacts: dict, output_dir: Path = Path("history")) -> Path:
    gen_dir = output_dir / f"gen_{gen_num:03d}"
    gen_dir.mkdir(parents=True, exist_ok=True)

    (gen_dir / "palette.json").write_text(json.dumps(artifacts["palette"], indent=2))
    (gen_dir / "typography.json").write_text(json.dumps(artifacts["typography"], indent=2))
    (gen_dir / "logomark.json").write_text(json.dumps(
        {k: v for k, v in artifacts["logo"].items() if k != "svg"}, indent=2))
    (gen_dir / "logomark.svg").write_text(artifacts["logo"].get("svg", ""))
    (gen_dir / "voice.json").write_text(json.dumps(artifacts["voice"], indent=2))
    (gen_dir / "board.svg").write_text(artifacts["board_svg"])

    return gen_dir


# ---------------------------------------------------------------------------
# CLI: single generation
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    brief = load_brief()
    print(f"loaded brief ({len(brief)} chars)")
    print("generating brand identity...\n")

    artifacts = generate_full(brief)
    gen_dir = save_generation(1, artifacts)

    print(f"\ndone. artifacts saved to {gen_dir}/")
    print(f"  palette:    {gen_dir}/palette.json")
    print(f"  typography: {gen_dir}/typography.json")
    print(f"  logomark:   {gen_dir}/logomark.svg")
    print(f"  voice:      {gen_dir}/voice.json")
    print(f"  board:      {gen_dir}/board.svg")
