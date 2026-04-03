"""
Daily data updater for AI Native App Monitor.
Runs via GitHub Actions every day at 08:00 UTC.
Uses Claude API (claude-sonnet-4-6 + web_search) to scan for:
  - New funding rounds / valuation updates
  - ARR milestone announcements
  - New AI apps to consider adding
Then patches data.json with confirmed changes and appends an update note.
"""

import json
import os
import sys
import re
from datetime import date, timedelta
import urllib.request
import urllib.error

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"
DATA_FILE = "data.json"

# ── Prompt sent to Claude each day ─────────────────────────────────────────
SYSTEM_PROMPT = """You are a financial data analyst maintaining an AI industry monitor dashboard.
Your job is to search for the latest news about AI company funding, valuations, and revenue milestones,
then return a structured JSON patch with ONLY confirmed, sourced changes.

Rules:
- Only update a field if you find a credible source (Bloomberg, TechCrunch, CNBC, company announcement, Sacra, The Information).
- Do NOT speculate or extrapolate. If unsure, skip the field.
- Valuations: use post-money from the most recent closed round. "In talks" rounds use the target value but add "(in talks)" to update_notes.
- ARR: use the figure from the most recent credible report. Always note the source date.
- Return ONLY valid JSON, no prose, no markdown fences.
"""

USER_PROMPT = """Today is {today}. Search the web for AI company news from the past 7 days.

Focus on these companies:
MODELS: OpenAI, Anthropic, Google Gemini, xAI/Grok, Mistral AI, Cohere, Kimi/Moonshot, MiniMax, Zhipu AI, 01.AI
APPS: Cursor/Anysphere, Perplexity, Character.ai, ElevenLabs, Midjourney, Runway, Harvey, Glean, Sierra, Cognition, HeyGen, Suno, Granola, Luma AI

Look for:
1. New funding rounds (amount, valuation, lead investors)
2. ARR / revenue milestones announced by company or reported by The Information / Bloomberg / Sacra
3. New AI apps with rapid growth worth adding to the monitor

Return a JSON object with this exact structure (omit any section with no confirmed updates):

{{
  "has_updates": true or false,
  "update_notes": "Brief summary of what changed and sources (max 200 chars)",
  "model_patches": [
    {{
      "name": "exact name as in dataset",
      "field": "arr | val | arrg | tokM",
      "new_value": <number>,
      "source": "source name + date",
      "confidence": "high | medium"
    }}
  ],
  "app_patches": [
    {{
      "name": "exact name as in dataset",
      "field": "arr | val | arrg | mau | m",
      "new_value": <number>,
      "source": "source name + date",
      "confidence": "high | medium"
    }}
  ],
  "new_apps": [
    {{
      "name": "App Name",
      "uc": "one-line description in Chinese",
      "cat": "coding|search|creative|enterprise|vertical|consumer|voice",
      "stage": "scale|growth|pmf|pre",
      "arr": <number in $M>,
      "arrg": <YoY % or null>,
      "mau": <millions or null>,
      "maug": <YoY % or null>,
      "ti": "ultra|high|med|low",
      "biz": "B2B|B2C|B2B+B2C",
      "val": <$B or null>,
      "m": <0-100>,
      "selfModel": true or false,
      "source": "source + date"
    }}
  ]
}}
"""

def call_claude(today_str: str) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    payload = {
        "model": MODEL,
        "max_tokens": 2000,
        "tools": [{"type": "web_search_20250305", "name": "web_search"}],
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": USER_PROMPT.format(today=today_str)}]
    }

    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "web-search-2025-03-05",
            "content-type": "application/json"
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())

    # Extract the text block (Claude may have tool_use blocks before the final text)
    text = ""
    for block in result.get("content", []):
        if block.get("type") == "text":
            text = block["text"]

    # Strip any accidental markdown fences
    text = re.sub(r"^```json\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())

    return json.loads(text)


def apply_patches(data: dict, patch: dict) -> tuple[dict, list[str]]:
    """Apply Claude's patches to data dict. Returns (updated_data, change_log)."""
    changes = []
    today = str(date.today())

    # Patch models
    for p in patch.get("model_patches", []):
        if p.get("confidence") not in ("high", "medium"):
            continue
        for m in data["models"]:
            if m["name"] == p["name"]:
                old = m.get(p["field"])
                m[p["field"]] = p["new_value"]
                changes.append(f"[MODEL] {p['name']}.{p['field']}: {old} → {p['new_value']} ({p['source']})")
                break

    # Patch apps
    for p in patch.get("app_patches", []):
        if p.get("confidence") not in ("high", "medium"):
            continue
        for a in data["apps"]:
            if a["name"] == p["name"]:
                old = a.get(p["field"])
                a[p["field"]] = p["new_value"]
                changes.append(f"[APP] {p['name']}.{p['field']}: {old} → {p['new_value']} ({p['source']})")
                break

    # Add new apps
    existing_names = {a["name"] for a in data["apps"]}
    for na in patch.get("new_apps", []):
        if na["name"] not in existing_names:
            # Remove 'source' key before adding to dataset
            na_clean = {k: v for k, v in na.items() if k != "source"}
            data["apps"].append(na_clean)
            changes.append(f"[NEW APP] {na['name']} added ({na.get('source', '')})")

    # Update meta
    data["meta"]["last_updated"] = today
    data["meta"]["next_update"] = str(date.today() + timedelta(days=1))
    if patch.get("has_updates") and patch.get("update_notes"):
        data["meta"]["update_notes"] = f"{today}: {patch['update_notes']}"

    return data, changes


def main():
    today_str = str(date.today())
    print(f"=== AI Monitor daily update: {today_str} ===")

    # Load current data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("Calling Claude API with web search...")
    try:
        patch = call_claude(today_str)
    except Exception as e:
        print(f"Claude API error: {e}", file=sys.stderr)
        # Update meta even on failure so we know the job ran
        data["meta"]["last_updated"] = today_str
        data["meta"]["next_update"] = str(date.today() + timedelta(days=1))
        data["meta"]["update_notes"] = f"{today_str}: Auto-update ran, no changes (API error or no new data)"
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("Wrote unchanged data with updated timestamp.")
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
