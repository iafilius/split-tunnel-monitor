class SplitTunnelMonitor < Formula
  desc "Split-tunnel VPN multipath monitor for macOS (Zscaler, AnyConnect, GlobalProtect)"
  homepage "https://github.com/iafilius/split-tunnel-monitor"
  url "https://github.com/iafilius/split-tunnel-monitor/archive/refs/tags/v1.6.0.tar.gz"
  sha256 "e8bb367c4d2fe02881fe550e81afe0de4e9dd125d5a84170b61dc8a227c6b845"
  license "GPL-3.0-or-later"

  depends_on :macos
  # Floor is Python 3.9+ (asyncio.to_thread, used for background traceroute verification)
  depends_on "python3"

  def install
    bin.install "ping_checker.py" => "split-tunnel-monitor"
  end

  test do
    assert_match "ping_checker #{version}", shell_output("#{bin}/split-tunnel-monitor --version")
  end
end
