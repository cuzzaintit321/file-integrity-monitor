#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
gh auth status
gh auth setup-git
if [[ -e .git ]]; then echo 'Git checkout exists; inspect before publishing manually.'; exit 1; fi
if gh repo view cuzzaintit321/file-integrity-monitor >/dev/null 2>&1; then
    echo 'Repository exists; inspect before publishing manually.'; exit 1
fi
git init -b main
git add .
git -c user.name='Jason Edwards' \
    -c user.email='228125969+cuzzaintit321@users.noreply.github.com' \
    commit -m 'Add Python systems tool with tests, documentation, and CI'
gh repo create cuzzaintit321/file-integrity-monitor --public --source . --remote origin --push \
    --description 'Python file integrity checker with SHA-256 baselines, content and permission drift detection, and JSON reports.'
