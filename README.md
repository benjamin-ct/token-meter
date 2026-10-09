# Token Meter — plugin Claude Code

Suivi en direct de ta consommation de tokens dans Claude Code :

- **par tchat** (conversation en cours)
- **par session de 5 h** (la fenêtre de limite d'usage des abonnements Pro/Max)

```
Opus 5.5 │ 💬 Tchat 164k (↑10.2k ↓4.0k ⟲150k) ~$0.42 │ ⏱ Session 5h 263k 24% reset 21:39 │ ctx 34%
```

`↑` entrée (dont écriture cache) · `↓` sortie · `⟲` lecture cache · `24%` = part de ta limite de 5 h consommée (donnée officielle Claude Code, abonnés Pro/Max) · `~$` = coût estimé au prix catalogue (indicatif).

## Installation

Prérequis : Python 3.8+ (aucune dépendance).

1. Dans Claude Code :
   ```
   /plugin marketplace add benjamin-ct/token-meter
   /plugin install token-meter@benjamin-tools
   ```
   (depuis un dossier local : `/plugin marketplace add C:/chemin/vers/token-meter`)
2. Active la barre d'état live :
   ```
   /token-meter:setup
   ```

## Commandes

| Commande | Effet |
|---|---|
| `/token-meter:setup` | Active la barre d'état live (sauvegarde l'ancienne si besoin) |
| `/token-meter:tokens [jours]` | Rapport par session de 5 h et par tchat (7 jours par défaut) |
| `/token-meter:live` | Donne la commande du tableau de bord à lancer dans un 2ᵉ terminal |
| `/token-meter:unsetup` | Retire la barre d'état et restaure l'ancienne |

En direct hors Claude Code, dans un autre terminal :

```
python tokmeter.py live --every 3      # tableau de bord rafraîchi
python tokmeter.py report --days 30    # rapport ponctuel
```

## Fonctionnement

- Les chiffres viennent des transcripts locaux `~/.claude/projects/**/*.jsonl` (champ `usage` de chaque réponse), dédoublonnés par message. Rien n'est envoyé nulle part, et la barre d'état ne consomme aucun token.
- La fenêtre de 5 h utilise l'heure de reset officielle quand Claude Code la fournit, sinon elle est reconstituée (début arrondi à l'heure du premier message).
- Les sous-agents sont inclus (leurs transcripts sont dans le même dossier).
- `CLAUDE_CONFIG_DIR` est respecté.

## Limites

- Ne couvre que **Claude Code**. L'app claude.ai (web/desktop/mobile) n'expose pas de compteur de tokens, aucun plugin ne peut le lire.
- La barre d'état ne s'affiche que dans le terminal (CLI). Dans l'extension VS Code et l'app desktop, les commandes `/token-meter:…` fonctionnent, mais pas la barre.
- Le total brut est dominé par les lectures de cache, qui pèsent beaucoup moins dans les limites que les tokens d'entrée/sortie : regarde le `%` de session pour savoir où tu en es vraiment.
