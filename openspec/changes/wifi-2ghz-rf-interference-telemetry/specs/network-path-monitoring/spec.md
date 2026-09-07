## ADDED Requirements

### Requirement: 2.4 GHz Wi-Fi Contention Advisory and Roam Warning

The system SHALL detect when the active Wi-Fi interface operates on the 2.4 GHz band (Channels 1–14), emit an informative advisory banner at startup and during downward roaming transitions, and record the RF band advisory state in the companion `.meta.json` sidecar.

#### Scenario: 2.4 GHz Wi-Fi detected at startup

- **WHEN** the monitor initializes on an active Wi-Fi interface whose band is "2.4GHz" or channel is between 1 and 14
- **THEN** the console and logfile startup banner display an informative advisory that 2.4 GHz Wi-Fi operates in a shared ISM band with higher susceptibility to Bluetooth, peripheral dongles, and USB 3.0 EMI
- **AND** the companion `.meta.json` records `"rf_band_advisory": "2.4GHZ_SHARED_ISM_RISK"`.

#### Scenario: Roaming downgrade from 5GHz/6GHz to 2.4GHz

- **WHEN** dynamic Wi-Fi roaming detects a transition from a 5 GHz or 6 GHz channel down to a 2.4 GHz channel
- **THEN** the logged `[WIFI ROAM]` event appends an informative advisory indicating potential RF contention risk (e.g. `(shared 2.4GHz band -- higher RF contention risk)`).
