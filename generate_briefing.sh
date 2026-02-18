#!/bin/bash
# CEO Briefing Generator — uses Claude CLI to generate, captures output to file
# Scheduled: every Sunday at 11 PM via cron

VAULT=/mnt/d/ai-employee-vault
DATE=$(date +%Y-%m-%d)
BRIEFING_FILE="$VAULT/Briefings/${DATE}_Monday_Briefing.md"

cd "$VAULT"
mkdir -p Briefings Logs

# Gather context from vault files
CONTEXT=""

if [ -f Business_Goals.md ]; then
    CONTEXT+="=== Business_Goals.md ===
$(cat Business_Goals.md)

"
fi

if [ -f Accounting/Current_Month.md ]; then
    CONTEXT+="=== Accounting/Current_Month.md ===
$(cat Accounting/Current_Month.md)

"
fi

if [ -d Done ] && [ "$(ls Done/ 2>/dev/null)" ]; then
    CONTEXT+="=== Recent Done/ files (last 7 days) ===
$(find Done/ -name '*.md' -mtime -7 -exec basename {} \;)

"
fi

if [ -d Tasks/Done ] && [ "$(ls Tasks/Done/ 2>/dev/null)" ]; then
    CONTEXT+="=== Tasks/Done/ ===
$(ls Tasks/Done/)

"
fi

if [ -d Needs_Action ] && [ "$(ls Needs_Action/ 2>/dev/null)" ]; then
    CONTEXT+="=== Needs_Action/ (pending items) ===
$(ls Needs_Action/)

"
fi

if [ -f Dashboard.md ]; then
    CONTEXT+="=== Dashboard.md ===
$(cat Dashboard.md)

"
fi

# Ask Claude to generate the briefing (output only, no file writing)
BRIEFING=$(cd "$VAULT" && unset CLAUDECODE && claude --print --model haiku -p "You are a CEO briefing assistant. Based on the following business data, generate a Monday Morning CEO Briefing in markdown format. Output ONLY the markdown content, no explanations.

${CONTEXT}

Generate the briefing with these sections:

# CEO Briefing — ${DATE}

## 1. Revenue Summary
Compare current revenue vs targets. List all invoices and their payment status.

## 2. Completed Tasks This Week
List items from Done/ folder completed recently.

## 3. Bottlenecks & Issues
Flag any pending items, unpaid invoices, or delayed tasks.

## 4. Social Media Summary
Summarize any social media drafts or activity.

## 5. Cost-Saving Suggestions
Identify any optimization opportunities based on the data.

## 6. Upcoming Deadlines (Next 14 Days)
List any upcoming deadlines from Business_Goals.md." 2>&1)

# Write briefing to file
echo "$BRIEFING" > "$BRIEFING_FILE"
echo "Briefing saved to: $BRIEFING_FILE"

# Update Dashboard.md with briefing link
if [ -f Dashboard.md ]; then
    if grep -q "Latest Briefing" Dashboard.md; then
        sed -i "s|.*Latest Briefing.*|- [Latest Briefing](Briefings/${DATE}_Monday_Briefing.md)|" Dashboard.md
    else
        echo "" >> Dashboard.md
        echo "## Latest Briefing" >> Dashboard.md
        echo "- [Latest Briefing](Briefings/${DATE}_Monday_Briefing.md)" >> Dashboard.md
    fi
    echo "Dashboard.md updated with briefing link."
fi
