# Git Workflow - Dev to Production

## Branch Structure
- **dev** - Development/testing branch (work here daily)
- **main** - Production branch (live site at https://hamektok.github.io/infinite-solutions/)

## Daily Workflow

### 1. Start Working
```bash
git checkout dev
```

### 2. Make Your Changes
- Edit files as normal
- Test by opening `index.html` in browser
- Run your Python scripts to test

### 3. Save Your Work (Commit to Dev)
```bash
git add .
git commit -m "Description of changes"
git push
```
⚠️ This pushes to dev branch only - **NOT live yet**

### 4. Deploy to Production (When Ready)
```bash
git checkout main
git merge dev
git push
```
✅ This deploys to the live site!

### 5. Switch Back to Dev
```bash
git checkout dev
```

## Useful Commands

### Check Current Branch
```bash
git branch
```
The branch with `*` is your current branch.

### See What Changed
```bash
git status              # See modified files
git diff                # See exact changes
git log --oneline -5    # See recent commits
```

### Undo Mistakes

**Undo last commit (keep changes):**
```bash
git reset --soft HEAD~1
```

**Discard all uncommitted changes:**
```bash
git checkout .
```
⚠️ This deletes your changes! Be careful!

**Revert a bad commit on live site:**
```bash
git checkout main
git revert HEAD         # Creates new commit that undoes the last one
git push
```

## Safety Rules

✅ **DO:**
- Always work on dev branch
- Test locally before merging to main
- Commit often with clear messages
- Only merge to main when you're confident

❌ **DON'T:**
- Don't work directly on main branch
- Don't push to main without testing
- Don't force push (git push --force)
- Don't commit sensitive files (credentials.json, etc.)

## Protected Files (Never Commit)

These are automatically ignored by `.gitignore`:
- `config/` folder
- `token_manager.py`
- `credentials.json`
- `*.db` files
- `*.log` files

## Troubleshooting

### "You are on branch main"
```bash
git checkout dev
```

### "Your branch is behind origin/dev"
```bash
git pull
```

### "Merge conflict"
1. Open the conflicted files
2. Look for `<<<<<<<`, `=======`, `>>>>>>>` markers
3. Edit to keep what you want
4. Save the file
5. `git add .`
6. `git commit -m "Resolve merge conflict"`
7. `git push`

### "I broke the live site!"
```bash
git checkout main
git revert HEAD
git push
```
This creates a new commit that undoes your last change.

## Tips

- Use `git status` often to see where you are
- Commit messages should be descriptive: "Add blueprint category overrides" not "updates"
- Test in browser before deploying to main
- Keep dev branch in sync: `git checkout dev && git pull` regularly
