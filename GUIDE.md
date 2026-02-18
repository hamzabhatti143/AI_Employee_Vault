# AI Employee - PowerShell Guide (No Claude CLI needed)

---

## EMAIL

### Check New Emails
```powershell
# List all pending emails (newest first)
Get-ChildItem "D:\ai-employee-vault\Needs_Action\EMAIL_*.md" | Sort-Object LastWriteTime -Descending

# Read the latest email
Get-Content (Get-ChildItem "D:\ai-employee-vault\Needs_Action\EMAIL_*.md" | Sort-Object LastWriteTime -Descending | Select-Object -First 1)

# Read a specific email
Get-Content "D:\ai-employee-vault\Needs_Action\EMAIL_<MESSAGE_ID>.md"
```

### Reply to an Email
```powershell
# Get the message_id from inside the email file, then:
python D:\ai-employee-vault\watchers\gmail_utils.py reply <MESSAGE_ID> "Your reply here"

# Example
python D:\ai-employee-vault\watchers\gmail_utils.py reply 19c5b7712e9658fc "Mein nay bhi dekhli shukriya"
```

### Send a New Email
```powershell
python D:\ai-employee-vault\watchers\gmail_utils.py send "someone@email.com" "Subject" "Body text"

# Example
python D:\ai-employee-vault\watchers\gmail_utils.py send "john@gmail.com" "Meeting Tomorrow" "Hi, are we still on for tomorrow?"
```

---

## WHATSAPP

### Check New WhatsApp Messages
```powershell
# List all pending WhatsApp messages (newest first)
Get-ChildItem "D:\ai-employee-vault\Needs_Action\WHATSAPP_*.md" | Sort-Object LastWriteTime -Descending

# Read the latest WhatsApp message
Get-Content (Get-ChildItem "D:\ai-employee-vault\Needs_Action\WHATSAPP_*.md" | Sort-Object LastWriteTime -Descending | Select-Object -First 1)

# Show only urgent messages (keyword matches)
Get-ChildItem "D:\ai-employee-vault\Needs_Action\WHATSAPP_*.md" | Where-Object { (Get-Content $_) -match "urgent: true" }
```

### Send / Reply on WhatsApp
Works with both **saved contact names** and **phone numbers** (even unsaved):
```powershell
# By contact name (must match exactly as in WhatsApp)
'{"contact":"John Doe","message":"Hello!"}' | Out-File -Encoding utf8 "D:\ai-employee-vault\wa_outbox\SEND_$(Get-Date -Format yyyyMMddHHmmss).json"

# By phone number (with country code, works even if not saved)
'{"contact":"+92 316 3836744","message":"Shukriya, From AI"}' | Out-File -Encoding utf8 "D:\ai-employee-vault\wa_outbox\SEND_$(Get-Date -Format yyyyMMddHHmmss).json"

# Phone number formats all work: +923163836744, 923163836744, +92 316 3836744
```
The wa-watcher picks up the file and sends it automatically (check `wa_outbox\sent\` for confirmation).

---

## GENERAL

### Check All Pending Items
```powershell
Get-ChildItem "D:\ai-employee-vault\Needs_Action\" | Sort-Object LastWriteTime -Descending
```

### Check Done Items
```powershell
Get-ChildItem "D:\ai-employee-vault\Done\" | Sort-Object LastWriteTime -Descending
```

### Check Watcher Status
```powershell
pm2 list
pm2 logs gmail-watcher --lines 20
pm2 logs wa-watcher --lines 20
```

---

## APPROVAL WORKFLOW

```
Needs_Action/  →  review  →  Approved/  →  auto-executes  →  Done/
                               Rejected/  →  no action
```

```powershell
# Approve
Move-Item "D:\ai-employee-vault\Needs_Action\<FILENAME>.md" "D:\ai-employee-vault\Approved\"

# Reject
Move-Item "D:\ai-employee-vault\Needs_Action\<FILENAME>.md" "D:\ai-employee-vault\Rejected\"
```
