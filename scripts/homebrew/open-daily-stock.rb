class OpenDailyStock < Formula
  include Language::Python::Virtualenv

  desc "Local-first A-share/HK/US stock analyzer with TUI+GUI dual-mode"
  homepage "https://github.com/mbpz/open-daily-stock"
  url "https://github.com/mbpz/open-daily-stock.git", tag: "v0.5.0"
  license "MIT"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
    bin.install_symlink libexec/"bin/open-daily-stock"
  end

  test do
    system bin/"open-daily-stock", "--version"
  end
end
