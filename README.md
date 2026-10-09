# Token Meter — mod Claude Code

Suivi en direct de ta consommation de tokens dans Claude Code, **sur toutes les surfaces** : terminal, app desktop (onglet Code), extension VS Code.

- **par tchat** : la conversation en cours
- **par session de 5 h** : la fenêtre de limite d'usage, toutes conversations confondues

La ligne d'état, sous la zone de saisie, se met à jour après chaque réponse :

```
💬 Tchat 65.7k (↑4.1k ↓1.6k ⟲60.0k) │ ⏱ Session 5h 263k · 24% · reset dans 2 h 14
```

`↑` entrée (dont écriture cache) · `↓` sortie · `⟲` lecture cache · `24%` = part de ta limite de 5 h consommée (relevé officiel, abonnés Pro/Max).

La commande `/token-meter` ouvre un panneau avec le détail : le tchat en cours, la session de 5 h (avec le % de la semaine) et les 30 derniers tchats.

## Installation

Dans un terminal Claude Code :

```
/plugin install token-meter --marketplace benjamin-ct/token-meter
```

Réponds `y` pour ajouter le marketplace, puis choisis la portée « user ». Installé à la portée user depuis le terminal, le mod se charge aussi dans les sessions locales de l'app desktop.

Mise à jour : `/plugin marketplace update benjamin-tools`.

## Fonctionnement

- Les tokens viennent de chaque réponse du modèle (événement `turn.complete`), sous-agents compris.
- Un journal partagé entre toutes tes sessions, sur cette machine, alimente le total de la session de 5 h. La fenêtre suit l'heure de reset officielle quand Claude Code la reçoit ; sinon elle est reconstituée (début arrondi à l'heure du premier message).
- `/clear` remet le compteur du tchat à zéro, pas celui de la session de 5 h.

## Limites

- Le mod compte à partir de son installation. Les tchats plus anciens ne sont pas repris : pour l'historique, utilise `extras/tokmeter.py` ci-dessous.
- Il compte ce qui passe par Claude Code sur cette machine. claude.ai, les autres appareils et les sessions cloud n'apparaissent pas dans les tokens, mais ils pèsent dans le **%** de la limite, qui vient de l'API.
- Le total brut est dominé par les lectures de cache, qui pèsent bien moins dans les limites : regarde le **%** pour savoir où tu en es vraiment.

## Extra : rapport et tableau de bord depuis l'historique

`extras/tokmeter.py` (Python 3.8+, sans dépendance) relit les transcripts locaux `~/.claude/projects/**/*.jsonl`, y compris ceux d'avant l'installation du mod :

```
python extras/tokmeter.py report --days 30   # rapport par session de 5 h et par tchat
python extras/tokmeter.py live --every 3     # tableau de bord qui se rafraîchit
```
