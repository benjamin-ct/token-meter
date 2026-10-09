---
description: Donne la commande pour ouvrir le tableau de bord live dans un second terminal
---
Donne à l'utilisateur, dans un bloc de code, la commande à lancer dans un autre terminal pour suivre sa consommation en direct :

```
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/tokmeter.py" live --every 3
```

Précise en une ligne que sous Windows il faut remplacer `python3` par `python`, et que Ctrl+C quitte. N'exécute rien.
