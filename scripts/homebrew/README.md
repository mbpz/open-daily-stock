# Homebrew Tap for open-daily-stock

Install the open-daily-stock GUI app on macOS via Homebrew Cask.

## Install

```bash
brew install --cask mbpz/tap/open-daily-stock
```

## Upgrade

```bash
brew upgrade open-daily-stock
```

## Uninstall

```bash
brew uninstall --cask open-daily-stock
brew untap mbpz/tap
```

## Requirements

- macOS 10.15+ (Catalina or later)
- Apple Silicon (M1/M2/M3) or Intel

## Notes

- Installs to `/Applications/open-daily-stock-gui.app`
- `auto_updates true` — checks GitHub Releases for new versions
- DMG is signed and quarantine xattr cleared — no Gatekeeper popup
- Cask is maintained in [mbpz/homebrew-tap](https://github.com/mbpz/homebrew-tap)
