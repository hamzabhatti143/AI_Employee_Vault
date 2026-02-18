# Test Plan: AI Employee Vault System

## Step 1: Inbox Drop Test
- Drop a sample file into `Inbox/`
- Verify the filesystem watcher copies it to `Needs_Action/` with a metadata `.md` file
- Confirm the watcher logs the detection event

## Step 2: Action Processing Test
- Read any files in `Needs_Action/`
- Classify the action type based on the metadata
- Move processed files to `Done/` and log the result in `Logs/`

## Step 3: Dashboard Update Test
- Update `Dashboard.md` with current counts (pending, active plans, completed)
- Add a timestamped entry to Recent Activity
- Verify all counters reflect the actual state of the vault folders
