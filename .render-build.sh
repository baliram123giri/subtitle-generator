#!/usr/bin/env bash

# Check if any Python files or requirements.txt changed
if git diff --name-only HEAD~1 HEAD | grep -E '(\.py$|requirements\.txt)'; then
  echo "Relevant changes detected. Installing dependencies..."
  pip install -r requirements.txt
else
  echo "No relevant changes. Skipping dependency install."
fi

# Continue with your app start logic