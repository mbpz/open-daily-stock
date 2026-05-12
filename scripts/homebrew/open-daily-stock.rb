cask "open-daily-stock" do
  arch arm: "arm64", intel: "x64"

  version "0.4.0"
  sha256 arm:   "REPLACE_ARM_SHA256",
         intel: "REPLACE_INTEL_SHA256"

  url "https://github.com/mbpz/open-daily-stock/releases/download/v#{version}/open-daily-stock-gui-#{version}-macos-#{arch}.dmg"
  name "Open Daily Stock"
  desc "Local-first A-share/HK/US stock analyzer with AI, TUI+GUI"
  homepage "https://github.com/mbpz/open-daily-stock"

  livecheck do
    url :url
    strategy :github_latest
  end

  auto_updates true
  depends_on macos: ">= :catalina"

  app "open-daily-stock-gui.app"

  zap trash: [
    "~/Library/Application Support/open-daily-stock",
    "~/Library/Preferences/com.opendailystock.app.plist",
    "~/Library/Saved Application State/com.opendailystock.app.savedState",
  ]
end
