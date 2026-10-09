---
description: Active la barre d'état live (tokens du tchat + session de 5 h)
allowed-tools: Bash(python3:*), Bash(python:*)
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/tokmeter.py" setup 2>/dev/null || python "${CLAUDE_PLUGIN_ROOT}/scripts/tokmeter.py" setup`

Résume le résultat ci-dessus en une ou deux lignes. Si l'installation a réussi, précise que la barre d'état apparaît en bas dès la prochaine réponse.
