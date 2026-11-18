"""Read settings.md (the YAML block), apply one-off overrides, and print/save the result as JSON.

Usage:
  python settings.py                                  # print the settings as JSON
  python settings.py --set caption_style=pop --set custom_colors.active=#00ff00 --out run/settings.json
  python settings.py --file other_settings.md

Values: on/true/yes -> true, off/false/no -> false, numbers -> numbers, [..] -> list, anything else -> text.
"""
import argparse
import json
import re
import sys
from pathlib import Path

from common import SKILL_DIR, save_json, utf8


def strip_comment(line):
    out, quote = [], None
    for ch in line:
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "#":
            break
        out.append(ch)
    return "".join(out).rstrip()


def convert(val):
    v = val.strip()
    if not v:
        return ""
    if (v[0] == v[-1]) and v[0] in "\"'" and len(v) >= 2:
        return v[1:-1]
    low = v.lower()
    if low in ("true", "on", "yes"):
        return True
    if low in ("false", "off", "no"):
        return False
    if v.startswith("["):
        try:
            return json.loads(v.replace("'", '"'))
        except json.JSONDecodeError:
            return [x.strip().strip("\"'") for x in v.strip("[]").split(",") if x.strip()]
    if re.fullmatch(r"-?\d+", v):
        return int(v)
    if re.fullmatch(r"-?\d*\.\d+", v):
        return float(v)
    return v


def parse(text):
    m = re.search(r"```yaml\s*\n(.*?)```", text, re.S)
    if not m:
        sys.exit("settings file has no ```yaml block")
    data, parent = {}, None
    for raw in m.group(1).splitlines():
        line = strip_comment(raw)
        if not line.strip():
            continue
        indent = len(raw) - len(raw.lstrip())
        key, sep, val = line.strip().partition(":")
        if not sep:
            continue
        key = key.strip()
        if indent == 0:
            if val.strip() == "":
                data[key], parent = {}, key
            else:
                data[key], parent = convert(val), None
        elif parent is not None:
            data[parent][key] = convert(val)
    return data


def load(path=None, overrides=()):
    p = Path(path) if path else SKILL_DIR / "settings.md"
    data = parse(p.read_text(encoding="utf-8"))
    for o in overrides:
        key, _, val = o.partition("=")
        key = key.strip()
        target = data
        parts = key.split(".")
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        if parts[-1] not in target and key.split(".")[0] not in data:
            print(f"warning: '{key}' is not a known setting", file=sys.stderr)
        target[parts[-1]] = convert(val)
    return data


if __name__ == "__main__":
    utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", help="settings file (default: the skill's settings.md)")
    ap.add_argument("--set", action="append", default=[], help="key=value override, repeatable")
    ap.add_argument("--out", help="also save the JSON here")
    a = ap.parse_args()
    s = load(a.file, a.set)
    if a.out:
        save_json(a.out, s)
    print(json.dumps(s, ensure_ascii=False, indent=1))
