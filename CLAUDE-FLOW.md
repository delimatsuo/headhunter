# Claude Code Workflow Protocol

## 🚨 MANDATORY: Commit and Push Protocol

**AFTER EVERY SIGNIFICANT MILESTONE OR BREAKTHROUGH:**

### 1. Document the Work
- Create/update relevant documentation files
- Include: what was done, why, results, and next steps
- Use clear, searchable titles and sections

### 2. Stage All Changes
```bash
git add -A
```

### 3. Review Changes
```bash
git status
git diff --cached --stat
```

### 4. Commit with Descriptive Message
```bash
git commit -m "type(scope): clear description

- Bullet points of key changes
- Why the changes were made
- Results/impact
- Related task/issue references"
```

### 5. Push to Remote IMMEDIATELY
```bash
git push origin main
```

### 6. Verify Push Succeeded
```bash
git log --oneline -1
# Confirm latest commit is on remote
```

## Why This Matters

1. **Work Protection** - Changes are backed up immediately
2. **Collaboration** - Team can see progress in real-time
3. **Recovery** - Can rollback if something breaks
4. **Accountability** - Clear history of what was done
5. **Documentation** - Commit messages serve as timeline

## When to Commit & Push

### ✅ ALWAYS Commit After:
- Fixing a bug
- Completing a feature
- Successful deployment
- Breakthrough/discovery
- Before switching tasks
- End of work session
- Every 30-60 minutes of work

### ❌ NEVER Commit:
- Broken/failing code (unless documented as WIP)
- Sensitive credentials
- Large binary files (without .gitignore)
- Work in progress without clear description

## Commit Message Format

```
type(scope): short description (50 chars max)

Detailed explanation of what and why (wrap at 72 chars):
- Change 1 with reason
- Change 2 with impact
- Change 3 with context

Related: Task #N, Issue #N, PR #N
```

### Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `refactor`: Code restructuring
- `test`: Adding/fixing tests
- `chore`: Maintenance/tooling
- `perf`: Performance improvement

## Current Session Commits

Session started: October 2, 2025
Commits made this session: 10+

Latest commits:
- 9e2b4ba: API Gateway deployment breakthrough
- e2476bb: Breakthrough - lazy initialization works
- a687bf7: Admin service lazy init pattern
- c7ecccb: Comprehensive troubleshooting summary
- 9a11adb: VPC firewall Cloud SQL peering fix
- 4333115: Redis host and port corrections
- 4d7e3a6: VPC egress all-traffic fix
- 1526ec9: PGVECTOR_PORT environment variables

## Pre-Work Checklist

Before starting new work:
- [ ] Pull latest changes: `git pull origin main`
- [ ] Check current branch: `git branch`
- [ ] Review pending changes: `git status`
- [ ] Commit any WIP: `git add -A && git commit -m "WIP: ..."`

## End of Session Checklist

Before ending work:
- [ ] All changes committed
- [ ] All commits pushed to remote
- [ ] Documentation updated
- [ ] Status files current (CURRENT_STATUS.md, etc.)
- [ ] No uncommitted changes: `git status` shows clean
- [ ] Create handover summary if needed

## Recovery Procedures

If work is lost:
1. Check `git reflog` for recent commits
2. Check remote: `git fetch && git log origin/main`
3. Check local uncommitted: `git stash list`
4. Last resort: `.deployment/` logs may have evidence

## This File

This file (`CLAUDE-FLOW.md`) itself must be:
1. Committed immediately after creation
2. Updated when protocol changes
3. Referenced in `CLAUDE.md` for enforcement
