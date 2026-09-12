import re
import json
from pathlib import Path

raw_file = Path(r"D:\Steam Checker\target_games_raw.txt")
with open(raw_file, "r", encoding="utf-8", errors="replace") as f:
    content = f.read()

prefix = "FIFA International Soccer"
idx = content.find(prefix)
suffix = "bu oyunlardan herhangi biri gelirse discorda payla"
idx2 = content.find(suffix)

if idx == -1 or idx2 == -1:
    print(f"Indices not found: idx={idx}, idx2={idx2}")
    exit(1)

games_blob = content[idx:idx2]
raw_titles = [g.strip() for g in games_blob.split(",") if g.strip()]

cleaned_titles = []
for t in raw_titles:
    if "Wallpaper engine" in t or "Wallpaper Engine" in t:
        parts = re.split(r"Wallpaper [eE]ngine", t)
        for p in parts:
            if p.strip():
                cleaned_titles.append(p.strip())
        cleaned_titles.append("Wallpaper Engine")
    else:
        cleaned_titles.append(t)

print(f"Total raw parsed titles: {len(raw_titles)}")
print(f"Total cleaned titles: {len(cleaned_titles)}")

# Deduplicate while preserving case
seen = set()
unique_titles = []
for t in cleaned_titles:
    norm = re.sub(r"[\s\-_:!?,.™®'\"]+", " ", t).strip().lower()
    if norm and norm not in seen:
        seen.add(norm)
        unique_titles.append(t)

print(f"Total unique target game titles: {len(unique_titles)}")

# Also extract franchise roots/keywords for smart matching
franchise_keywords = set()
for t in unique_titles:
    norm = re.sub(r"[\s\-_:!?,.™®'\"]+", " ", t).strip().lower()
    # If title has colon or edition or year, extract prefix
    parts = re.split(r"[:\(\)\-]|\b(19\d\d|20\d\d)\b|\b(deluxe|complete|definitive|gold|ultimate|goty|remastered|remake|hd|collection|legacy|champion|special|director|anniversary|enhanced|game of the year)\b", norm)
    root = parts[0].strip()
    if len(root) >= 3 and not root.isdigit():
        franchise_keywords.add(root)

print(f"Extracted {len(franchise_keywords)} franchise root keywords.")

out_data = {
    "titles": unique_titles,
    "franchises": sorted(list(franchise_keywords))
}

out_path = Path(r"D:\Steam Checker\nexus\utils\target_games.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out_data, f, indent=2, ensure_ascii=False)

print(f"Successfully generated {out_path}")
