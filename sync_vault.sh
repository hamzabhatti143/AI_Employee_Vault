#!/bin/bash
cd /mnt/d/ai-employee-vault
git pull origin main --no-edit
git add -A
git diff --staged --quiet || git commit -m "Auto-sync: $(date +%Y-%m-%d\ %H:%M:%S)"
git push origin main
