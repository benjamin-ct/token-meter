#!/usr/bin/env python3
"""token-meter : suivi en direct des tokens Claude Code.

Lit les transcripts locaux (~/.claude/projects/**/*.jsonl) et calcule :
  - les tokens du tchat (conversation) en cours
  - les tokens de la session de 5 h en cours (fenêtre de limite d'usage)

Sous-commandes :
  statusline        lit le JSON de Claude Code sur stdin, imprime la barre d'état
  report [--days N] tableau par tchat + par session de 5 h
  live   [--every S] tableau de bord qui se rafraîchit dans un terminal
  setup / unsetup   active / retire la barre d'état dans ~/.claude/settings.json

Aucune dépendance externe : Python 3.8+ standard library uniquement.
"""
import json
import os
import sys
import time
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

BLOCK = timedelta(hours=5)

# ---------------------------------------------------------------- utilitaires

def claude_dir() -> Path:
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        return Path(env.split(",")[0]).expanduser()
    return Path.home() / ".claude"


def fmt(n: float) -> str:
    n = float(n or 0)
    for unit, div in (("G", 1e9), ("M", 1e6), ("k", 1e3)):
        if abs(n) >= div:
            v = n / div
            return f"{v:.1f}{unit}" if v < 100 else f"{v:.0f}{unit}"
    return f"{int(n)}"


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


USE_COLOR = os.environ.get("NO_COLOR") is None
def c(code, txt):
    return f"\033[{code}m{txt}\033[0m" if USE_COLOR else str(txt)


# ---------------------------------------------------------------- lecture des transcripts

def read_usage(path: Path, since=None):
    """Retourne {clé_message: entrée} pour un fichier .jsonl.

    Claude Code écrit parfois plusieurs lignes pour une même réponse (un bloc
    de contenu par ligne) avec le même `usage` : on dédoublonne par
    message.id + requestId et on garde la ligne la plus complète.
    """
    out = {}
    try:
        fh = open(path, "r", encoding="utf-8", errors="replace")
    except OSError:
        return out
    with fh:
        for line in fh:
            if '"usage"' not in line:
                continue
            try:
                d = json.loads(line)
            except ValueError:
                continue
            msg = d.get("message") or {}
            u = msg.get("usage") if isinstance(msg, dict) else None
            if not isinstance(u, dict):
                continue
            ts = parse_ts(d.get("timestamp"))
            if since and ts and ts < since:
                continue
            key = f"{msg.get('id')}|{d.get('requestId')}"
            e = {
                "ts": ts,
                "session": d.get("sessionId") or path.stem,
                "cwd": d.get("cwd") or "",
                "model": msg.get("model") or "",
                "in": int(u.get("input_tokens") or 0),
                "out": int(u.get("output_tokens") or 0),
                "cw": int(u.get("cache_creation_input_tokens") or 0),
                "cr": int(u.get("cache_read_input_tokens") or 0),
            }
            prev = out.get(key)
            if prev is None or e["out"] >= prev["out"]:
                out[key] = e
    return out


def all_transcripts(modified_since=None):
    root = claude_dir() / "projects"
    if not root.exists():
        return []
    files = []
    cutoff = modified_since.timestamp() if modified_since else None
    for p in root.rglob("*.jsonl"):
        try:
            if cutoff is None or p.stat().st_mtime >= cutoff:
                files.append(p)
        except OSError:
            pass
    return files


def collect(since=None):
    """Toutes les entrées d'usage (dédoublonnées globalement) depuis `since`."""
    merged = {}
    for f in all_transcripts(since):
        merged.update(read_usage(f, since))
    return [e for e in merged.values() if e["ts"]]


def total(entries):
    t = {"in": 0, "out": 0, "cw": 0, "cr": 0, "n": 0}
    for e in entries:
        for k in ("in", "out", "cw", "cr"):
            t[k] += e[k]
        t["n"] += 1
    t["all"] = t["in"] + t["out"] + t["cw"] + t["cr"]
    return t


def blocks(entries):
    """Regroupe en sessions de 5 h (début arrondi à l'heure, comme les limites)."""
    out = []
    cur = None
    for e in sorted(entries, key=lambda x: x["ts"]):
        if cur is None or e["ts"] >= cur["end"]:
            start = e["ts"].replace(minute=0, second=0, microsecond=0)
            cur = {"start": start, "end": start + BLOCK, "items": []}
            out.append(cur)
        cur["items"].append(e)
    return out


# ---------------------------------------------------------------- statusline

def cache_path() -> Path:
    base = os.environ.get("CLAUDE_PLUGIN_DATA")
    d = Path(base) if base else claude_dir() / "token-meter"
    d.mkdir(parents=True, exist_ok=True)
    return d / "window-cache.json"


def window_totals(win_start, ttl=15):
    """Total de la fenêtre de 5 h, mis en cache quelques secondes (rapidité)."""
    cp = cache_path()
    key = win_start.isoformat()
    try:
        cached = json.loads(cp.read_text())
        if cached.get("key") == key and time.time() - cached.get("at", 0) < ttl:
            return cached["tot"]
    except (OSError, ValueError):
        pass
    tot = total(collect(win_start))
    try:
        cp.write_text(json.dumps({"key": key, "at": time.time(), "tot": tot}))
    except OSError:
        pass
    return tot


def statusline():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        data = {}
    now = datetime.now(timezone.utc)
    sep = c("2", " │ ")
    parts = []

    model = (data.get("model") or {}).get("display_name")
    if model:
        parts.append(c("36", model))

    # --- tchat en cours
    tp = data.get("transcript_path")
    chat = total(read_usage(Path(tp)).values()) if tp and Path(tp).exists() else total([])
    cost = (data.get("cost") or {}).get("total_cost_usd")
    s = (f"💬 Tchat {c('1', fmt(chat['all']))} "
         + c("2", f"(↑{fmt(chat['in'] + chat['cw'])} ↓{fmt(chat['out'])} ⟲{fmt(chat['cr'])})"))
    if cost:
        s += c("2", f" ~${cost:.2f}")
    parts.append(s)

    # --- session de 5 h
    rl = ((data.get("rate_limits") or {}).get("five_hour") or {})
    resets = rl.get("resets_at")
    if resets:
        end = datetime.fromtimestamp(float(resets), timezone.utc)
        win_start = end - BLOCK
    else:
        recent = blocks(collect(now - BLOCK))
        if recent and recent[-1]["end"] > now:
            win_start, end = recent[-1]["start"], recent[-1]["end"]
        else:
            win_start, end = now, None
    win = window_totals(win_start)
    s = f"⏱ Session 5h {c('1', fmt(win['all']))}"
    pct = rl.get("used_percentage")
    if pct is not None:
        col = "31" if pct >= 90 else "33" if pct >= 70 else "32"
        s += " " + c(col, f"{pct:.0f}%")
    if end:
        s += c("2", f" reset {end.astimezone().strftime('%H:%M')}")
    parts.append(s)

    ctx = (data.get("context_window") or {}).get("used_percentage")
    if ctx is not None:
        parts.append(c("2", f"ctx {ctx:.0f}%"))

    print(sep.join(parts))


# ---------------------------------------------------------------- rapport

JOURS = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]


def fr_date(d):
    d = d.astimezone()
    return f"{JOURS[d.weekday()]} {d.strftime('%d/%m %H:%M')}"


def row(cols, widths):
    return "  ".join(str(v).rjust(w) if i else str(v).ljust(w) for i, (v, w) in enumerate(zip(cols, widths)))


def report(days=7, limit=15, out=print):
    now = datetime.now(timezone.utc)
    entries = collect(now - timedelta(days=days))
    days = f"{days:g}"
    head = ["", "Total", "Entrée", "Sortie", "Cache écr.", "Cache lu", "Req."]

    out(c("1", f"\n⏱  Sessions de 5 h ({days} derniers jours)"))
    w = [24, 9, 9, 9, 10, 10, 6]
    out(c("2", row(head, w)))
    for b in reversed(blocks(entries)[-limit:]):
        t = total(b["items"])
        active = b["end"] > now
        label = fr_date(b["start"]) + ("  ● en cours" if active else "")
        line = row([label, fmt(t["all"]), fmt(t["in"]), fmt(t["out"]), fmt(t["cw"]), fmt(t["cr"]), t["n"]], w)
        out(c("32", line) if active else line)

    out(c("1", f"\n💬 Tchats (conversations) — {limit} plus récents"))
    chats = {}
    for e in entries:
        chats.setdefault(e["session"], []).append(e)
    ordered = sorted(chats.items(), key=lambda kv: max(x["ts"] for x in kv[1]), reverse=True)[:limit]
    w = [34, 9, 9, 9, 10, 10, 6]
    out(c("2", row(["Projet · session · dernière activité"] + head[1:], w)))
    for sid, items in ordered:
        t = total(items)
        last = max(x["ts"] for x in items).astimezone().strftime("%d/%m %H:%M")
        proj = Path(items[-1]["cwd"]).name or "?"
        label = f"{proj[:14]} · {sid[:8]} · {last}"
        out(row([label, fmt(t["all"]), fmt(t["in"]), fmt(t["out"]), fmt(t["cw"]), fmt(t["cr"]), t["n"]], w))

    t = total(entries)
    out(c("1", f"\nΣ {days} j : {fmt(t['all'])} tokens "
               f"(entrée {fmt(t['in'])}, sortie {fmt(t['out'])}, cache écrit {fmt(t['cw'])}, cache lu {fmt(t['cr'])}) "
               f"sur {t['n']} réponses, {len(chats)} tchats"))
    if not entries:
        out(c("33", f"Aucune donnée trouvée dans {claude_dir() / 'projects'}"))


def live(every=3, days=1):
    try:
        while True:
            buf = []
            report(days=days, limit=10, out=buf.append)
            os.system("cls" if os.name == "nt" else "clear")
            print(c("2", f"token-meter live — rafraîchi toutes les {every}s — Ctrl+C pour quitter"))
            print("\n".join(buf))
            time.sleep(every)
    except KeyboardInterrupt:
        print()


# ---------------------------------------------------------------- installation de la barre d'état

def settings_file() -> Path:
    return claude_dir() / "settings.json"


def setup():
    sf = settings_file()
    data = {}
    if sf.exists():
        try:
            data = json.loads(sf.read_text(encoding="utf-8"))
        except ValueError:
            print(f"✗ {sf} n'est pas un JSON valide, abandon.")
            return 1
        shutil.copy2(sf, sf.with_name("settings.json.token-meter.bak"))
    # copie stable du script (le dossier du plugin change à chaque mise à jour)
    dest = claude_dir() / "token-meter" / "tokmeter.py"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__).resolve(), dest)
    py = Path(sys.executable).as_posix()
    cmd = f'"{py}" "{dest.as_posix()}" statusline'
    old = data.get("statusLine")
    backup = dest.parent / "previous-statusline.json"
    if old and "tokmeter" not in json.dumps(old):
        backup.write_text(json.dumps(old), encoding="utf-8")
    data["statusLine"] = {"type": "command", "command": cmd, "refreshInterval": 10}
    sf.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"✓ Barre d'état token-meter activée dans {sf}")
    print(f"  commande : {cmd}")
    if old:
        print("  (l'ancienne barre d'état est sauvegardée, /token-meter:unsetup la restaure)")
    return 0


def unsetup():
    sf = settings_file()
    if not sf.exists():
        print("Rien à faire.")
        return 0
    data = json.loads(sf.read_text(encoding="utf-8"))
    backup = claude_dir() / "token-meter" / "previous-statusline.json"
    prev = json.loads(backup.read_text(encoding="utf-8")) if backup.exists() else None
    if prev:
        backup.unlink()
        data["statusLine"] = prev
    elif "tokmeter" in json.dumps(data.get("statusLine", "")):
        data.pop("statusLine", None)
    sf.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("✓ Barre d'état token-meter retirée" + (" (ancienne restaurée)" if prev else ""))
    return 0


# ---------------------------------------------------------------- main

def main(argv):
    global USE_COLOR
    cmd = argv[1] if len(argv) > 1 else "report"
    opts = argv[2:]
    def opt(name, default):
        if name in opts:
            i = opts.index(name)
            if i + 1 < len(opts):
                return float(opts[i + 1])
        return default
    if "--no-color" in opts or (cmd == "report" and not sys.stdout.isatty() and "--color" not in opts):
        USE_COLOR = False
    if cmd == "statusline":
        try:
            statusline()
        except Exception as exc:  # une barre d'état ne doit jamais planter
            print(f"token-meter: {exc.__class__.__name__}")
    elif cmd == "report":
        report(days=opt("--days", 7), limit=int(opt("--limit", 15)))
    elif cmd == "live":
        live(every=opt("--every", 3), days=opt("--days", 1))
    elif cmd == "setup":
        return setup()
    elif cmd == "unsetup":
        return unsetup()
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main(sys.argv) or 0)
