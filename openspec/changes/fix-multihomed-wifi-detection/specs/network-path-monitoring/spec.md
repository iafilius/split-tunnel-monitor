## MODIFIED Requirements

### Requirement: Continuous Wi-Fi Physical Layer Refresh
The system SHALL continuously refresh active Wi-Fi physical radio metadata (including Channel, Band, RSSI, Noise, SNR, and TxRate) on every monitoring iteration throttled to a maximum frequency of once per second (1Hz), ensuring that roaming transitions and signal shifts are captured in real-time and subsequent CSV records reflect current physical medium state. This telemetry, including the `is_wifi` classification itself, SHALL always be scoped to the specific interface currently carrying traffic (the active routing interface), never to a different Wi-Fi interface the host may also have powered on and associated in the background.

#### Scenario: Wi-Fi channel switches while interface and IP remain unchanged
- **WHEN** the host roams or the access point switches radio channels (e.g. from Channel 36 to Channel 100) while the interface remains `en0` and the local IP is unchanged
- **THEN** real-time polling updates the active Wi-Fi metadata in memory within 1 second and subsequent CSV rows record the new channel and current RSSI.

#### Scenario: Real-time Wi-Fi polling rate-limiting
- **WHEN** the monitoring loop runs at high frequency or under fast intervals
- **THEN** physical Wi-Fi radio sampling is executed at most once per second to prevent unnecessary framework calls.

#### Scenario: Wired active interface is not misreported as Wi-Fi on a multi-homed host
- **WHEN** the active routing interface is a wired adapter (e.g. a USB-C/Thunderbolt Ethernet dongle) while the host's separate internal Wi-Fi radio is independently powered on and associated to an access point
- **THEN** `is_wifi` is `False`, `medium` reflects the wired adapter's actual hardware port name, and no channel/RSSI/noise/SNR/TxRate values are attributed to the session — regardless of the internal Wi-Fi radio's own channel, band, or signal state

#### Scenario: Physical medium and RF-band advisories follow the active interface, not a background radio
- **WHEN** the active routing interface is wired but a separate background Wi-Fi association exists on a 2.4GHz channel
- **THEN** `physical_medium_advisory` reports the wired clean-room baseline advisory (not the Wi-Fi RF-contention advisory) and `rf_band_advisory` is `None` (not `"2.4GHZ_SHARED_ISM_RISK"`), since the 2.4GHz radio is not the path actually carrying monitored traffic
