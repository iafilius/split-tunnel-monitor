## 1. Dynamic Path Discovery Engine

- [x] 1.1 Implement physical network interface detection using macOS `scutil --nwi`
- [x] 1.2 Implement local IP address extraction using `ipconfig getifaddr`
- [x] 1.3 Implement default LAN gateway resolution using `ipconfig getoption router`
- [x] 1.4 Implement fallback and mid-run interface re-discovery logic

## 2. Concurrent Probing & Outage Matrix

- [x] 2.1 Build asynchronous ICMP probe executor for macOS `ping` subprocesses
- [x] 2.2 Implement bound interface pinging via `ping -S <local_ip>` for Direct ISP path
- [x] 2.3 Implement standard routed pinging for Zscaler tunneled path
- [x] 2.4 Implement Outage Classification Matrix (Local Network Issue, ISP Issue, Zscaler Issue, Healthy)

## 3. Terminal UI & Timestamped Logging

- [x] 3.1 Implement single-line live updating terminal display with ANSI status updates
- [x] 3.2 Implement unique logfile creation named `ping_checker_YYYYMMDD_HHMMSS.log`
- [x] 3.3 Add ISO 8601 timestamp logging for every ping iteration and outage event

## 4. Verification & Testing

- [x] 4.1 Test dynamic discovery on macOS with Wi-Fi and Ethernet active
- [x] 4.2 Verify outage classification by simulating LAN/ISP/Zscaler probe drops
- [x] 4.3 Validate logfile output structure and timestamp accuracy

## 5. Tunnel Next-Hop Edge Case Refinement

- [x] 5.1 Adjust tunneled target selection so discovered virtual tunnel gateway IP is informational by default, not the primary ICMP health target
- [x] 5.2 Add classification guardrail to prevent Zscaler outage status from virtual next-hop ICMP failure alone
- [x] 5.3 Validate behavior on corporate Zscaler environment where route gateway is `100.64.x.x`, gateway ping fails, and routed tunnel target ping succeeds

## 6. Path Verification & Tool Check Layer

- [x] 6.1 Implement route-based path verification (`get_route_info`, `assess_path_verification`) confirming DIRECT=OK(en0) and ZSC=OK(utunX) using `route -n get -ifscope`
- [x] 6.2 Implement `check_required_tools()` startup check for all 7 required CLI tools with auto-disable of trace verification if `traceroute` is absent
- [x] 6.3 Implement ICMP-mode traceroute verification (`traceroute -I`) with hop2-based Zscaler confirmation; run as background async task every 30 iterations
- [x] 6.4 Make trace verification on by default; add `--no-trace-verify` flag to disable
- [x] 6.5 Validate on corporate Zscaler environment: DIRECT=OK(en0), ZSC=OK(utun4), TRACE(D=OK,Z=OK) with hop2=194.9.101.94 confirmed
