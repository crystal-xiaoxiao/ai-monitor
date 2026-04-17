"""
Daily data updater for AI Native App Monitor.
Uses Anthropic SDK with web_search tool (server-side built-in).
"""
import json
import os
import sys
import re
from datetime import date, timedelta
import anthropic

DATA_FILE = "data.json"
MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are a financial data analyst maintaining an AI industry monitor dashboard.
Search for the latest news about AI company funding, valuations, and revenue milestones,
then return a structured JSON patch with ONLY confirmed, sourced changes.

Rules:
- Only update a field if you find a credible source (Bloomberg, TechCrunch, CNBC, Sacra, The Information, company announcement).
- Do NOT speculate or extrapolate. If unsure, skip the field.
- Return ONLY valid JSON, no prose, no markdown fences.
"""

USER_PROMPT = """Today is {today}. Search the web for AI company news from the past 7 days.

Focus on these companies:
MODELS: OpenAI, Anthropic, Google Gemini, xAI/Grok, Mistral AI, Cohere, Kimi/Moonshot, MiniMax, Zhipu AI
APPS: Cursor/Anysphere, Perplexity, Character.ai, ElevenLabs, Midjourney, Runway, Harvey, Glean, Sierra, Cognition, HeyGen, Suno, Luma AI

Look for: new funding rounds, ARR/revenue milestones, valuation updates.

Return JSON with this structure (omit sections with no confirmed updates):
{{
  "has_updates": true or false,
  "update_notes": "Brief summary (max 200 chars)",
  "model_patches": [
    {{"name": "exact name in dataset", "field": "arr|val|arrg|tokM", "new_value": <number>, "source": "source + date", "confidence": "high|medium"}}
  ],
  "app_patches": [
    {{"name": "exact name in dataset", "field": "arr|val|arrg|mau", "new_value": <number>, "source": "source + date", "confidence": "high|medium"}}
  ]
}}

arr unit: $M. val unit: $B. arrg unit: %. Only include high/medium confidence changes.
"""


def call_claude(today_str: str) -> dict:
    """Call Claude with web_search tool using the SDK."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    # Use beta messages with web_search tool
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": USER_PROMPT.format(today=today_str)}],
        betas=["web-search-2025-03-05"],
    )

    # Extract final text block from response (web_search returns multiple content blocks)
    text = ""
    for block in response.content:
        if hasattr(block, "type") and block.type == "text":
            text = block.text

    if not text:
        raise ValueError(f"No text in response. stop_reason={response.stop_reason}, blocks={[b.type for b in response.content]}")

    # Strip markdown fences if any
    text = re.sub(r"^```json\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())

    return json.loads(text)


def apply_patches(data: dict, patch: dict) -> tuple:
    changes = []
    today = str(date.today())

    for mp in patch.get("model_patches", []):
        name, field, val = mp.get("name"), mp.get("field"), mp.get("new_value")
        if not all([name, field, val is not None]):
            continue
        for m in data["models"]:
            if name.lower() in m["name"].lower():
                old = m.get(field)
                m[field] = val
                changes.append(f"MODEL {m['name']}.{field}: {old} -> {val} ({mp.get('source','')})")
                break

    for ap in patch.get("app_patches", []):
        name, field, val = ap.get("name"), ap.get("field"), ap.get("new_value")
        if not all([name, field, val is not None]):
            continue
        for a in data["apps"]:
            if name.lower() in a["name"].lower():
                old = a.get(field)
                a[field] = val
                changes.append(f"APP {a['name']}.{field}: {old} -> {val} ({ap.get('source','')})")
                break

    data["meta"]["last_updated"] = today
    data["meta"]["next_update"] = str(date.today() + timedelta(days=1))
    if patch.get("update_notes"):
        data["meta"]["update_notes"] = f"{today}: {patch['update_notes']}"

    return data, changes


def main():
    today_str = str(date.today())
    print(f"=== AI Monitor daily update: {today_str} ===")

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("Calling Claude API with web_search tool...")
    try:
        patch = call_claude(today_str)
    except Exception as e:
        print(f"Claude API error: {e}", file=sys.stderr)
        data["meta"]["last_updated"] = today_str
        data["meta"]["next_update"] = str(date.today() + timedelta(days=1))
        data["meta"]["update_notes"] = f"{today_str}: Auto-update error: {str(e)[:100]}"
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Wrote unchanged data with error note.")
        return

    if not patch.get("has_updates"):
        print("No confirmed updates today.")
        data["meta"]["last_updated"] = today_str
        data["meta"]["next_update"] = str(date.today() + timedelta(days=1))
        data["meta"]["update_notes"] = f"{today_str}: No new confirmed data points found."
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return

    updated_data, changes = apply_patches(data, patch)

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(updated_data, f, ensure_ascii=False, indent=2)

    print(f"Applied {len(changes)} changes:")
    for c in changes:
        print(f"  {c}")
    print("data.json updated successfully.")


if __name__ == "__main__":
    main()
