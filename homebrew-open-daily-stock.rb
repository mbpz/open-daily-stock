# typed: false
# frozen_string_literal: true

class OpenDailyStock < Formula
  desc "Local-first A-share/HK/US stock analyzer with AI, GUI desktop app"
  homepage "https://github.com/mbpz/open-daily-stock"
  url "https://github.com/mbpz/open-daily-stock/releases/download/#{version}/open-daily-stock-macos.tar.gz"
  sha256 "TODO: update sha256 after first release"
  license "MIT"
  depends_on macos: ">= :big_sur"

  def install
    bin.install "open-daily-stock-gui"
  end

  test do
    system "#{bin}/open-daily-stock", "--version"
  end
end