---
name: pr-review
description: Review a pull request for code quality, test coverage, security, and best practices
metadata:
  openclaw:
    emoji: "\U0001F50D"
    os:
      - linux
    requires:
      bins:
        - gh
        - git
parameters:
  pr:
    type: string
    description: PR number, URL, or branch name to review
    required: false
  focus:
    type: string
    description: "Review focus area: all, security, tests, style, architecture (default: all)"
    required: false
---

# PR Code Review

Review a pull request for code quality, correctness, test coverage, security, and best practices.

## Overview

This skill performs a thorough code review, either on:
- A GitHub PR (by number or URL)
- A local branch (compared to its base)

It produces structured feedback with actionable comments.

## Workflow

### Step 1: Gather PR Information

**PR mode** (number or URL provided):
```bash
# Get PR metadata
gh pr view "$PR" --json title,body,baseRefName,headRefName,files,additions,deletions,author,labels

# Get the full diff
gh pr diff "$PR"

# Get existing review comments (avoid duplicating feedback)
gh api repos/{owner}/{repo}/pulls/{pr}/comments --jq '.[].body'
```

**Local branch mode** (no PR specified):
```bash
# Determine base branch
BASE=$(git merge-base HEAD main || git merge-base HEAD master)

# Get the diff
git diff "$BASE"...HEAD

# Get changed files
git diff "$BASE"...HEAD --name-only
```

### Step 2: Analyze Changes

For each changed file, evaluate:

#### Correctness
- Does the logic match the stated intent (PR description)?
- Are there off-by-one errors, null pointer risks, or race conditions?
- Are error paths handled properly?
- Do new functions return expected types/values?

#### Test Coverage
- Are there tests for new functionality?
- Do tests cover edge cases and error paths?
- Are tests testing behavior (not implementation details)?
- Is there adequate integration test coverage for API changes?

#### Security
- Input validation on user-provided data?
- SQL injection, XSS, command injection risks?
- Secrets or credentials accidentally included?
- Proper authentication/authorization checks?
- Safe handling of file paths (no path traversal)?

#### Style and Readability
- Consistent naming conventions?
- Functions at reasonable size (< 50 lines preferred)?
- Clear variable/function names?
- Unnecessary complexity that could be simplified?
- Dead code or commented-out code?

#### Architecture
- Does the change fit the existing patterns?
- Are there unnecessary dependencies introduced?
- Is the change properly scoped (not mixing concerns)?
- Will this change be easy to maintain and extend?

#### Backward Compatibility
- Are public APIs changed in breaking ways?
- Are database migrations reversible?
- Are config changes backward compatible?

### Step 3: Write Review

Structure the review as:

```markdown
## Review Summary

**PR**: #<number> — <title>
**Author**: <author>
**Files changed**: <count> (+<additions>, -<deletions>)
**Verdict**: APPROVE | REQUEST_CHANGES | COMMENT

### Key Findings

1. **[severity]** <file>:<line> — <description>
   Suggestion: <what to do instead>

2. ...

### Positive Notes
- <things done well>

### Test Coverage
- <assessment of test adequacy>

### Security
- <any security concerns or "No issues found">
```

Severity levels:
- **BLOCKING**: Must fix before merge (bugs, security issues, data loss risks)
- **IMPORTANT**: Should fix, but not a showstopper (missing tests, unclear naming)
- **NIT**: Minor style/preference (optional to address)
- **QUESTION**: Need clarification from author

### Step 4: Submit Review

**For GitHub PRs**, post the review:
```bash
# Submit as a review (not individual comments)
gh pr review "$PR" --comment --body "$REVIEW_BODY"

# Or with a verdict:
gh pr review "$PR" --approve --body "$REVIEW_BODY"
gh pr review "$PR" --request-changes --body "$REVIEW_BODY"
```

**For local branches**, print the review to stdout.

### Step 5: Post Inline Comments

For specific line-level feedback, post inline comments:
```bash
gh api repos/{owner}/{repo}/pulls/{pr}/comments \
  -f body="<comment>" \
  -f path="<file>" \
  -F line=<line_number> \
  -f side="RIGHT" \
  -f commit_id="$(gh pr view $PR --json headRefOid -q .headRefOid)"
```

## Review Principles

1. **Be constructive**: Suggest improvements, don't just criticize
2. **Be specific**: Point to exact lines, show code examples
3. **Prioritize**: Focus on bugs and security over style nits
4. **Respect intent**: Understand what the author was trying to do
5. **Don't bikeshed**: If it works and is readable, minor style differences are fine
6. **Check the tests**: Good tests are often more important than perfect code
