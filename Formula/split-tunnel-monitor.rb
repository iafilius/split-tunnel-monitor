class SplitTunnelMonitor < Formula
  desc "Split-tunnel VPN multipath monitor for macOS (Zscaler, AnyConnect, GlobalProtect)"
  homepage "https://github.com/iafilius/split-tunnel-monitor"
  url "https://github.com/iafilius/split-tunnel-monitor/archive/refs/tags/v1.0.1.tar.gz"
  sha256 "c9904d83d0f1272636a811acb6cfaf6557f01bddf830ec03511b2b2f6c4d6f9a"
  license "GPL-3.0-or-later"

  depends_on :macos
  depends_on "python3"

  def install
    bin.install "ping_checker.py" => "split-tunnel-monitor"
  end

  test do
    assert_match "split-tunnel-monitor 1.0.1", shell_output("#{bin}/split-tunnel-monitor --version")
  end
end
