class SplitTunnelMonitor < Formula
  desc "Split-tunnel VPN multipath monitor for macOS (Zscaler, AnyConnect, GlobalProtect)"
  homepage "https://github.com/iafilius/split-tunnel-monitor"
  url "https://github.com/iafilius/split-tunnel-monitor/archive/refs/tags/v1.1.0.tar.gz"
  sha256 "7bda46df52b565886f0bc67f99b27d947916969ab5886b69eae7263d7d337e2c"
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
