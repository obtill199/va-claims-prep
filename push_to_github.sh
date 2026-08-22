#!/usr/bin/env bash
# Push this repo to GitHub. Run after creating an EMPTY repo at
# https://github.com/new  (no README, no .gitignore, no license --
# this repo already has all three).
set -e
cd "$(dirname "$0")"

if [ -z "$1" ]; then
  echo "Usage: ./push_to_github.sh <your-github-username> [repo-name]"
  echo "Example: ./push_to_github.sh obtill199 va-claims-prep"
  exit 1
fi

USER="$1"
REPO="${2:-va-claims-prep}"

git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/$USER/$REPO.git"
git branch -M main

echo
echo "Pushing to https://github.com/$USER/$REPO"
echo "You'll be asked for your GitHub username and a Personal Access Token"
echo "(GitHub no longer accepts your account password here)."
echo "Create one at: https://github.com/settings/tokens  -> scope: repo"
echo
git push -u origin main

echo
echo "Done. Send your buddy:  https://github.com/$USER/$REPO"
