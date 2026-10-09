---
description: Rapport des tokens par session de 5 h et par tchat
argument-hint: "[jours, défaut 7]"
allowed-tools: Bash(python3:*), Bash(python:*)
---
!`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/tokmeter.py" report --days ${ARGUMENTS:-7} 2>/dev/null || python "${CLAUDE_PLUGIN_ROOT}/scripts/tokmeter.py" report --days ${ARGUMENTS:-7}`

Affiche le rapport ci-dessus tel quel dans un bloc de code, sans le reformuler. Ajoute ensuite une seule phrase qui signale la session de 5 h en cours et le tchat le plus consommateur. Ne lance aucun autre outil.
