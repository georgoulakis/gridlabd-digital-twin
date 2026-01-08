# GitHub Setup Guide

## Step 1: Create a New Repository on GitHub

1. Go to [GitHub.com](https://github.com) and sign in
2. Click the **"+"** icon in the top right corner
3. Select **"New repository"**
4. Fill in:
   - **Repository name**: e.g., `gridlabd-digital-twin` or `digitise-third-docker`
   - **Description**: (optional) "GridLAB-D Digital Twin Implementation with FastAPI"
   - **Visibility**: Choose Public or Private
   - **DO NOT** initialize with README, .gitignore, or license (we already have these)
5. Click **"Create repository"**

## Step 2: Connect Your Local Repository to GitHub

After creating the repository, GitHub will show you commands. Use these:

```bash
# Add the remote repository (replace YOUR_USERNAME and REPO_NAME)
git remote add origin https://github.com/YOUR_USERNAME/REPO_NAME.git

# Or if you prefer SSH (if you have SSH keys set up):
# git remote add origin git@github.com:YOUR_USERNAME/REPO_NAME.git

# Rename the default branch to 'main' (if needed)
git branch -M main

# Push your code to GitHub
git push -u origin main
```

## Step 3: Verify the Push

1. Go to your GitHub repository page
2. You should see all your files there
3. The commit message should appear in the commit history

## Working with Changes and Reverting

### Making Changes

1. **Make your changes** to files
2. **Stage changes**: `git add .` or `git add specific_file.py`
3. **Commit**: `git commit -m "Description of changes"`
4. **Push**: `git push`

### Viewing Changes

```bash
# See what files changed
git status

# See detailed changes
git diff

# See commit history
git log
```

### Reverting Changes

#### Undo Uncommitted Changes (Before Commit)

```bash
# Discard changes to a specific file
git checkout -- filename.py

# Discard all uncommitted changes
git reset --hard HEAD
```

#### Undo Last Commit (Keep Changes)

```bash
# Undo last commit but keep changes staged
git reset --soft HEAD~1

# Undo last commit and unstage changes
git reset HEAD~1
```

#### Revert a Specific Commit

```bash
# Create a new commit that undoes a specific commit
git revert COMMIT_HASH

# Example: git revert abc1234
```

#### Go Back to a Previous Commit

```bash
# View commit history to find commit hash
git log

# Go back to a specific commit (creates detached HEAD)
git checkout COMMIT_HASH

# Create a new branch from that commit
git checkout -b new-branch-name COMMIT_HASH
```

### Using Branches for Safe Experimentation

```bash
# Create a new branch
git checkout -b feature/new-feature

# Make changes and commit
git add .
git commit -m "Add new feature"

# Switch back to main
git checkout main

# Merge feature branch into main
git merge feature/new-feature

# Delete feature branch
git branch -d feature/new-feature
```

### Viewing and Comparing Versions on GitHub

1. Go to your repository on GitHub
2. Click on **"Commits"** to see all commits
3. Click on any commit to see what changed
4. Use **"Compare"** to compare different branches or commits
5. Click on any file and then **"History"** to see file history

## Common Workflow

```bash
# 1. Check status
git status

# 2. Stage changes
git add .

# 3. Commit with message
git commit -m "Add feature X"

# 4. Push to GitHub
git push

# 5. If you need to undo
git reset HEAD~1  # Undo commit, keep changes
# or
git revert HEAD  # Create new commit that undoes last commit
```

## Troubleshooting

### If push fails due to authentication:

1. **Use Personal Access Token** (recommended):
   - Go to GitHub Settings > Developer settings > Personal access tokens
   - Generate new token with `repo` permissions
   - Use token as password when pushing

2. **Or use GitHub CLI**:
   ```bash
   gh auth login
   ```

### If you need to update remote URL:

```bash
# Check current remote
git remote -v

# Update remote URL
git remote set-url origin https://github.com/YOUR_USERNAME/REPO_NAME.git
```

## Best Practices

1. **Commit often** with clear messages
2. **Use branches** for experimental features
3. **Pull before pushing** if working with others: `git pull`
4. **Don't commit sensitive data** (passwords, API keys)
5. **Use .gitignore** to exclude unnecessary files (already set up)

