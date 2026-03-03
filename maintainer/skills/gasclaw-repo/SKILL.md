---
name: gasclaw-repo
description: "Repository management for the gasclaw project"
metadata:
  openclaw:
    emoji: "\U0001F4C1"
    os: ["linux"]
    requires:
      bins: ["gh", "git"]
parameters:
  action:
    type: string
    description: "Action: commits, pr-detail, create-issue, close-issue, pull, diff"
    required: true
  number:
    type: integer
    description: "PR or issue number"
    required: false
  title:
    type: string
    description: "Issue title (for create-issue)"
    required: false
  body:
    type: string
    description: "Issue body (for create-issue)"
    required: false
  count:
    type: integer
    description: "Number of items to show"
    required: false
---

# Gasclaw Repo Management

Manage the gasclaw GitHub repository.

## Usage

```bash
bash ~/.openclaw/skills/gasclaw-repo/scripts/repo.sh commits 20
bash ~/.openclaw/skills/gasclaw-repo/scripts/repo.sh pr-detail 42
bash ~/.openclaw/skills/gasclaw-repo/scripts/repo.sh create-issue "Bug title" "Bug description"
bash ~/.openclaw/skills/gasclaw-repo/scripts/repo.sh pull
```
