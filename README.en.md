# SuperSmart EV Charging for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://www.hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io/)

[🇮🇹 Italiano](README.md) · 🇬🇧 English

SuperSmart EV Charging brings PV-surplus charging, off-peak charging, dynamic
load balancing and manual wallbox controls into a single Home Assistant
integration.

It is based on the automation logic developed for **Skoda Elroq/Enyaq and Silla
Prism**, but can be configured for other vehicles and wallboxes exposing
equivalent entities and commands.

> [!WARNING]
> Disable the old EV automations before enabling the integration. Two active
> controllers could send competing commands to the wallbox.

## Features

| Feature | Description |
|---|---|
| ☀️ **PV surplus** | Modulates charging current using available solar power and a configurable grid offset |
| 🌙 **Off-peak charging** | Charges during the selected cheap tariff, such as F3, up to the user SOC target |
| ⚡ **Load balancing** | Limits charging according to the total operating threshold and household consumption |
| 🔋 **Dual SOC target** | User target for off-peak charging and vehicle target for PV/Force Charge |
| 🚀 **Force Charge** | Starts charging regardless of tariff band and PV surplus |
| 🛑 **Master Stop** | Immediately revokes authorization and blocks every charging mode |
| 🔄 **SOC synchronization** | Synchronizes the vehicle target with the car charge limit when configured |
| ⏱️ **Charging estimates** | Calculates remaining time and completion time from SOC, usable capacity and actual power |
| 📡 **Configurable MQTT** | Configurable topics, payloads and telemetry; HA buttons can authorize and revoke |
| 🛡️ **Operational safeguards** | Input validation, PV hysteresis, minimum current, maximum limits and command anti-spam |

## Compatibility and requirements

### Requirements

- Home Assistant 2024.1 or later;
- HACS for custom-repository installation;
- a vehicle SOC sensor;
- grid power, PV production, wallbox state and wallbox power sensors;
- MQTT configured in Home Assistant when automatic wallbox mode and current
  control are required.

### Required conventions

- Grid power must be **positive while importing** and **negative while exporting**.
- Power values must be expressed in Watts.
- Wallbox state must expose `idle`, `waiting`, `pause` and `charging`.
- Wallboxes other than Silla Prism need MQTT topics and payloads equivalent to
  those requested by the setup flow.
- If a critical input is `unknown` or `unavailable`, no new commands are sent
  until valid data returns.

## Installation via HACS

1. Open **HACS → Integrations**.
2. From the ⋮ menu, select **Custom repositories**.
3. Enter
   `https://github.com/atcodrinky/ha-supersmart-ev-charging` and select
   **Integration** as the category.
4. Install SuperSmart EV Charging and restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration** and search for
   **SuperSmart EV Charging**.

## Guided setup

### Step 1 — General settings

| Field | Description | Initial value |
|---|---|---|
| Instance and device name | Vehicle name also used as the basis for entity IDs | SuperSmart EV Charging |
| Total operating power limit | Desired overall ceiling for the house and wallbox | 5700 W |
| Usable battery capacity | Actual usable capacity, adjustable over time | 60 kWh |
| User SOC target | Target used by off-peak charging | 50% |
| Vehicle SOC target | Target used by PV and Force Charge | 80% |
| Off-peak tariff | Enables the off-peak charging logic | Enabled |
| MQTT | Enables MQTT wallbox control | Enabled |
| MQTT energy telemetry | Publishes energy data to the configured topics | Enabled |
| Notifications | Opens the optional notification setup | Disabled |

### Step 2 — Home Assistant entities

#### Required entities

| Role | Requirement | Example |
|---|---|---|
| Vehicle SOC | Numeric percentage | `sensor.ev_battery_level` |
| Grid power | W, positive import and negative export | `sensor.grid_power` |
| PV production | Power in W | `sensor.solar_power` |
| Wallbox state | `idle`, `waiting`, `pause`, `charging` | `sensor.wallbox_state` |
| Wallbox power | Power in W; its sign is ignored | `sensor.wallbox_power` |
| Tariff band | Required only when off-peak charging is enabled | `sensor.current_tariff` |

#### Optional entities

| Role | Behavior when not configured |
|---|---|
| Vehicle connected | Derived from wallbox state: `idle` means unplugged |
| Vehicle charge limit | The internal target remains available without car synchronization |
| Total instantaneous power | Calculated as grid power + PV production |
| Wallbox voltage | Uses 230 V; sensor values are internally clamped to 180–260 V |
| Wallbox port/mode | Only improves notification classification |
| Authorize/revoke buttons | Falls back to the configured MQTT topics |

When off-peak charging is enabled, also select the tariff sensor and enter the
value identifying the cheap band, for example `F3`.

### Optional step — Notifications

When enabled in the first step, one or more `notify.*` actions can be selected
from a dropdown. Messages can automatically follow the Home Assistant language
or explicitly use Italian or English. Titles and messages can be customized
with `{mode}`, `{soc}`, `{target}`, `{time_remaining}` and `{charge_end_time}`.
The `{instance}` placeholder identifies the vehicle and is included in the
default titles.

Notifications can also be enabled, disabled or changed later from the
integration gear icon. The same page directly shows enablement, recipients and
language; when customization is enabled, the next step lets the user edit titles
and messages. The device and its entities do not need to be recreated.

### Final step — MQTT commands

This step is displayed when MQTT is enabled.

| Function | Default value |
|---|---|
| Authorize topic | `wallbox/command/authorize` |
| Revoke topic | `wallbox/command/revoke` |
| Current-limit topic | `prism/1/command/set_current_limit` |
| Mode topic | `prism/1/command/set_mode` |
| Solar / Normal / Pause payload | `1` / `2` / `3` |
| Grid telemetry | `prism/energy_data/power_grid` |
| PV telemetry | `prism/energy_data/power_solar` |
| House telemetry | `prism/energy_data/power_house` |

For Silla Prism, selecting the Home Assistant authorize and revoke buttons is
recommended. Their MQTT topics are intended as a fallback or for other
wallboxes.

## What it creates in Home Assistant

The integration is listed under **Integrations** and creates one SuperSmart EV
Charging device containing all related entities. No manual `input_boolean`,
`input_number`, `input_select` or `input_datetime` helpers are required.

Display names are translated into the Home Assistant backend language when the
entities are first created. The instance name is used as the basis for entity
IDs: `SuperSmart Elroq Charging` will normally generate IDs prefixed with
`supersmart_elroq_charging_`. IDs may still vary: check the actual values under
**Settings → Devices & services → Entities**.

### Multiple vehicles and wallboxes

Multiple integration instances can be added. Use the pattern **SuperSmart
VEHICLE_NAME Charging** to distinguish them, for example `SuperSmart Elroq
Charging` and `SuperSmart Enyaq Charging`. Each instance creates a separate
device, entities, persisted state, and control logic.

The vehicle SOC sensor and wallbox state sensor cannot be reused by another
instance: two controllers acting on the same vehicle or wallbox would send
competing commands. Shared sensors such as grid power, PV production, and tariff
band can be reused.

Home Assistant preserves entity IDs already stored in its registry: upgrading
does not rename the existing instance's IDs. The new naming pattern is applied
automatically to instances created with v1.2.0 or later.

### Sensors

| Sensor | Description |
|---|---|
| Charging Mode | `idle`, `pv_surplus`, `night`, `force` or `master_stop` |
| PV Surplus | PV margin already corrected by the configured import/export offset |
| Active SOC Target | Vehicle target in PV/Force, user target during off-peak charging |
| Charging Time Remaining | Estimated duration at the instantaneous charging power |
| Estimated Charge End Time | Timezone-aware timestamp formatted by Home Assistant |
| Wallbox Current Target | Last current limit actually sent to the wallbox |
| Actual Wallbox Current | Estimate calculated from wallbox power and voltage |

### Switches

| Switch | Function |
|---|---|
| Master Stop | Blocks charging and revokes authorization |
| Force Charge | Charges to the vehicle SOC target with contract load balancing |
| Solar Controller Active | Enables or disables PV-surplus control |
| Night Charging (F3) | Enables or disables off-peak charging |

### Numbers

| Number | Range | Initial value |
|---|---:|---:|
| User SOC Target | 10–100% | 50% |
| Vehicle SOC Target | 20–100% | 80% |
| Total Operating Power Limit | 1500–22000 W | 5700 W |
| Allowed Grid Import / PV Offset | -500–+500 W | 200 W |
| Off-Peak Total Operating Power Limit | 1000–22000 W | 3000 W |
| Usable Battery Capacity | 1–250 kWh | 60 kWh |

The user target cannot exceed the vehicle target. A negative PV offset requires
an export margin: for example, `-200 W` aims to keep approximately 200 W
exported to the grid.

The operating limit is the **desired total ceiling for the house and wallbox**,
not the nominal contract rating and not a guaranteed consumption target. It
should leave any meter tolerance available as a buffer. Actual power may remain
lower because of household loads, effective voltage, internal wallbox limits or
vehicle demand.

### Actions

With one instance, `config_entry_id` is optional. With multiple vehicles, select
the instance in the visual action editor; Home Assistant will add its
`config_entry_id` to the YAML.

```yaml
action: supersmart_ev_charging.authorize_charging
```

```yaml
action: supersmart_ev_charging.revoke_charging
```

```yaml
action: supersmart_ev_charging.set_charge_limit
data:
  config_entry_id: YOUR_CONFIG_ENTRY_ID
  current_a: 10
```

`current_a` accepts values from 6 to 32 A.

## Internal process

```text
State change or periodic evaluation every 30 s
                         │
                         ▼
                 Read and validate inputs
                         │
              invalid critical data
                         └──────────────→ no new command
                         │ valid
                         ▼
Vehicle unplugged / wallbox idle? ─ yes ─→ full reset
                         │ no
                         ▼
Master Stop? ────────────── yes ─→ Pause + revoke authorization
                         │ no
                         ▼
SOC ≥ vehicle target? ───── yes ─→ Absolute stop + revoke
                         │ no
                         ▼
Force Charge? ───────────── yes ─→ Normal + vehicle target
                         │ no       + contract load balancing
                         ▼
Usable PV surplus? ──────── yes ─→ Solar + vehicle target
                         │ no       + incremental current control
                         ▼
Off-peak + night enabled? ─ yes ─→ Normal + user target
                         │ no       + night power limit
                         ▼
                        IDLE
```

Decisions are serialized to avoid overlapping MQTT commands.

### Load balancing and PV calculation

In Force Charge and off-peak modes, available current is derived from the
selected power limit after subtracting household consumption:

```text
house_load        = max(total_power - wallbox_power, 0)
available_current = (power_limit - house_load) / voltage
```

In PV mode, the controller corrects the current already delivered:

```text
delta_A      = (-grid_power + import_offset) / voltage
current_now  = wallbox_power / voltage
target_A     = current_now + delta_A
```

PV charging starts when at least 7 A has been available for 30 seconds and
stops when the target remains below 5.5 A for 60 seconds. The operating minimum
is 6 A; the maximum is 25 A in PV mode and 32 A in Force/off-peak modes. A new
limit is sent only when it changes by at least 0.5 A.

### SOC targets and estimates

- **Force Charge and PV:** vehicle SOC target.
- **Off-peak charging:** user SOC target.

Remaining time is estimated with:

```text
((target SOC - current SOC) / 100 × usable capacity kWh) / wallbox power kW
```

Charging efficiency is assumed to be 100%. Below 100 W, remaining time and
estimated completion are unavailable.

When the vehicle charge-limit entity is configured, a change made from the
integration is sent to the vehicle after 3 seconds, allowing the car time to
wake up. A change coming from the car or its app immediately updates the
integration target.

## Complete flow diagram

![SuperSmart EV Charging flow diagram](assets/ev_energy_manager_flow_en.svg)

## License

MIT License — see [LICENSE](LICENSE).
