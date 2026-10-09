---
description: Retire la barre d'état token-meter (restaure l'ancienne si elle existait)
allowed-tools: Bash(python3:*), Bash(python:*)
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/tokmeter.py" unsetup 2>/dev/null || python "${CLAUDE_PLUGIN_ROOT}/scripts/tokmeter.py" unsetup`

Résume le résultat ci-dessus en une ligne.
