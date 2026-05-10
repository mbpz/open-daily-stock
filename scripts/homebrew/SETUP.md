# Homebrew Tap Setup Guide

This guide explains how to create and maintain the `mbpz/homebrew-tap`
repository for distributing open-daily-stock via Homebrew.

## One-Time Setup

### 1. Create the Tap Repository

Create a public GitHub repository named `homebrew-tap` under the `mbpz` account:

```bash
# Via GitHub CLI
gh repo create mbpz/homebrew-tap --public --description "Homebrew tap for open-daily-stock"

# Or create manually at: https://github.com/new
# Repository name: homebrew-tap
# Owner: mbpz
# Visibility: Public
```

### 2. Clone and Initialize

```bash
git clone https://github.com/mbpz/homebrew-tap.git
cd homebrew-tap
```

### 3. Copy the Formula

```bash
cp path/to/open-daily-stock/scripts/homebrew/open-daily-stock.rb Formula/
git add Formula/open-daily-stock.rb
git commit -m "Add open-daily-stock formula v0.5.0"
git push
```

### 4. Verify

```bash
brew tap mbpz/tap
brew install open-daily-stock
open-daily-stock --version
```

## Release Process

### Automated Update (CI)

When a new GitHub Release is published, the `.github/workflows/homebrew-release.yml`
workflow automatically updates the formula's `tag` reference in the `homebrew-tap` repo.
No manual SHA256 computation is needed since the formula builds from the git source.

### Manual Update

For each new release tag (e.g., `v0.5.0`), update the `tag` in `Formula/open-daily-stock.rb`:

```bash
cd homebrew-tap
sed -i '' 's/tag: "v[0-9.]*"/tag: "v0.5.0"/' Formula/open-daily-stock.rb
git add Formula/open-daily-stock.rb
git commit -m "Update open-daily-stock to v0.5.0"
git push
```

## How Users Install

Users do NOT need to clone the tap repo. They can install directly:

```bash
# First time (tap + install)
brew tap mbpz/tap
brew install open-daily-stock

# Subsequent updates
brew upgrade open-daily-stock
```

Homebrew automatically resolves `mbpz/tap/<name>` to
`https://github.com/mbpz/homebrew-tap`.

## Formula Maintenance

- Keep the formula in the `homebrew-tap` repo (NOT in the main repo)
- The copy in `scripts/homebrew/` is the canonical source for reference
- Always test the formula locally before pushing:
  ```bash
  brew audit --strict Formula/open-daily-stock.rb
  brew test Formula/open-daily-stock.rb
  ```
