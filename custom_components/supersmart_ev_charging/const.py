"""Constants for SuperSmart EV Charging integration – aligned with YAML automations."""

DOMAIN = "supersmart_ev_charging"

CONF_INSTANCE_NAME = "instance_name"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"

# ── Config entry keys ──────────────────────────────────────────────────────────

# Wallbox MQTT
CONF_MQTT_TOPIC_SET_CURRENT    = "mqtt_topic_set_current"
CONF_MQTT_TOPIC_SET_MODE       = "mqtt_topic_set_mode"
# Authorize / Revoke sono BUTTON PRESS su Silla Prism, non topic MQTT separati
CONF_MQTT_TOPIC_AUTHORIZE      = "mqtt_topic_authorize"   # kept for generic wallboxes
CONF_MQTT_TOPIC_REVOKE         = "mqtt_topic_revoke"      # kept for generic wallboxes
CONF_MQTT_PAYLOAD_MODE_SOLAR   = "mqtt_payload_mode_solar"
CONF_MQTT_PAYLOAD_MODE_NORMAL  = "mqtt_payload_mode_normal"
CONF_MQTT_PAYLOAD_MODE_PAUSE   = "mqtt_payload_mode_pause"
CONF_MQTT_ENABLED              = "mqtt_enabled"

# Telemetria energia Silla Prism (replica "Prism - Invio Dati Energia")
CONF_ENERGY_PUBLISH_ENABLED    = "energy_publish_enabled"
CONF_MQTT_TOPIC_POWER_GRID     = "mqtt_topic_power_grid"
CONF_MQTT_TOPIC_POWER_SOLAR    = "mqtt_topic_power_solar"
CONF_MQTT_TOPIC_POWER_HOUSE    = "mqtt_topic_power_house"

# Notifiche. CONF_NOTIFY_SERVICE resta supportato per migrare le installazioni
# create prima del selettore multiplo.
CONF_NOTIFY_SERVICE            = "notify_service"
CONF_NOTIFY_SERVICES           = "notify_services"
CONF_NOTIFICATIONS_ENABLED     = "notifications_enabled"
CONF_NOTIFICATION_LANGUAGE     = "notification_language"
CONF_NOTIFICATION_CUSTOMIZE    = "notification_customize"
CONF_NOTIFY_START_TITLE        = "notify_start_title"
CONF_NOTIFY_START_MESSAGE      = "notify_start_message"
CONF_NOTIFY_STOP_TITLE         = "notify_stop_title"
CONF_NOTIFY_STOP_MESSAGE       = "notify_stop_message"
CONF_WALLBOX_MODE_ENTITY       = "wallbox_mode_entity"

NOTIFICATION_LANGUAGE_AUTO = "auto"
NOTIFICATION_LANGUAGE_IT   = "it"
NOTIFICATION_LANGUAGE_EN   = "en"

# Silla Prism button entities (used for auth/revoke via HA button.press)
CONF_BUTTON_AUTHORIZE_ENTITY   = "button_authorize_entity"
CONF_BUTTON_REVOKE_ENTITY      = "button_revoke_entity"

# Vehicle entities
CONF_VEHICLE_SOC_ENTITY          = "vehicle_soc_entity"
CONF_VEHICLE_CHARGE_LIMIT_ENTITY = "vehicle_charge_limit_entity"
CONF_VEHICLE_CONNECTED_ENTITY    = "vehicle_connected_entity"

# Wallbox entities
CONF_WALLBOX_STATE_ENTITY   = "wallbox_state_entity"   # sensor.silla_prism_stato_wallbox
CONF_WALLBOX_POWER_ENTITY   = "wallbox_power_entity"
CONF_WALLBOX_VOLTAGE_ENTITY = "wallbox_voltage_entity"

# Energy entities
CONF_GRID_POWER_ENTITY     = "grid_power_entity"       # sensor.rete_power (+ = import, - = export)
# sensor.fotovoltaico_power – OBBLIGATORIO.
# Serve per calcolare potenza_istantanea quando CONF_TOTAL_POWER_ENTITY non è configurato:
#   potenza_istantanea = rete_power + fotovoltaico_power
# (replica esatta del template HA sensor.potenza_istantanea)
CONF_PV_POWER_ENTITY       = "pv_power_entity"         # sensor.fotovoltaico_power
# sensor.potenza_istantanea – OPZIONALE.
# Se configurato viene letto direttamente dal sensore template.
# Se omesso, viene calcolato internamente con la stessa formula:
#   {{ (states('sensor.rete_power')|float(0) + states('sensor.fotovoltaico_power')|float(0)) | round(0) }}
CONF_TOTAL_POWER_ENTITY    = "total_power_entity"      # sensor.potenza_istantanea (opzionale)

# Tariff entity (sensor.pun_fascia_corrente)
CONF_TARIFF_ENTITY        = "tariff_entity"
CONF_TARIFF_OFFPEAK_VALUE = "tariff_offpeak_value"     # "F3"
CONF_TARIFF_ENABLED       = "tariff_enabled"

# Power / capacity
CONF_CONTRACT_POWER_W     = "contract_power_w"
CONF_BATTERY_CAPACITY_KWH = "battery_capacity_kwh"

# ── Defaults ───────────────────────────────────────────────────────────────────
DEFAULT_CONTRACT_POWER_W     = 5700       # input_number.limite_potenza_contratto_w
DEFAULT_BATTERY_CAPACITY_KWH = 60.0
DEFAULT_ALLOWED_IMPORT_W     = 200        # input_number.limite_import_permesso
MIN_ALLOWED_IMPORT_W         = -500       # margine massimo di esportazione FV
MAX_ALLOWED_IMPORT_W         = 500        # import massimo tollerato in FV
DEFAULT_SAFETY_MARGIN_W      = 0          # la YAML non usa un margine fisso separato

DEFAULT_NIGHT_POWER_LIMIT_W  = 3000       # input_number.ev_limite_notturno_w
DEFAULT_USER_SOC_TARGET      = 50         # input_number.limite_batteria_manuale
DEFAULT_VEHICLE_SOC_TARGET   = 80         # input_number.limite_batteria_auto

# ── Charging current limits ────────────────────────────────────────────────────
DEFAULT_MIN_CHARGE_CURRENT_A = 6          # minimo assoluto IEC 61851
DEFAULT_MAX_CHARGE_CURRENT_A = 25         # controller FV: YAML usa [amp, 25] | min
DEFAULT_MAX_LOAD_CURRENT_A   = 32         # FORZA/notte: YAML usa [amp, 32] | min

# ── PV surplus soglie – REPLICANO ESATTAMENTE LE YAML ─────────────────────────
# Surplus FV: start se amp_new_raw >= 7 per 30 s (trigger template con for:30s)
DEFAULT_PV_START_CURRENT_A   = 7          # soglia avvio FV
# Surplus FV: stop soft se amp_new_raw < 5.5 per 60 s
DEFAULT_PV_STOP_CURRENT_A    = 5.5        # soglia stop FV  ← era 6, SBAGLIATO
# Igiene controller: spegne ev_solar_controller_active se surplus < 7A per 60 s
DEFAULT_FV_HYGIENE_CURRENT_A = 7          # soglia igiene controller FV

# Cicli di conferma (il coordinatore gira ogni 30 s, come il trigger template)
# start: il trigger YAML ha for:30s → 1 ciclo confermato
DEFAULT_PV_START_CONFIRM_CYCLES = 1
# stop:  il trigger YAML ha for:60s → 2 cicli da 30 s
DEFAULT_PV_STOP_CONFIRM_CYCLES  = 2

# ── Default MQTT topics (Silla Prism) ─────────────────────────────────────────
DEFAULT_MQTT_TOPIC_SET_CURRENT   = "prism/1/command/set_current_limit"
DEFAULT_MQTT_TOPIC_SET_MODE      = "prism/1/command/set_mode"
# Per wallbox generici (senza button entities in HA)
DEFAULT_MQTT_TOPIC_AUTHORIZE     = "wallbox/command/authorize"
DEFAULT_MQTT_TOPIC_REVOKE        = "wallbox/command/revoke"

# Mode payloads Silla Prism
DEFAULT_MQTT_PAYLOAD_MODE_SOLAR  = "1"    # prism mode 1 = solar
DEFAULT_MQTT_PAYLOAD_MODE_NORMAL = "2"    # prism mode 2 = normal/grid
DEFAULT_MQTT_PAYLOAD_MODE_PAUSE  = "3"    # prism mode 3 = pausa/revoca

DEFAULT_MQTT_TOPIC_POWER_GRID    = "prism/energy_data/power_grid"
DEFAULT_MQTT_TOPIC_POWER_SOLAR   = "prism/energy_data/power_solar"
DEFAULT_MQTT_TOPIC_POWER_HOUSE   = "prism/energy_data/power_house"

DEFAULT_TARIFF_OFFPEAK_VALUE     = "F3"

# ── Wallbox state values (sensor.silla_prism_stato_wallbox) ───────────────────
WB_STATE_IDLE     = "idle"
WB_STATE_WAITING  = "waiting"
WB_STATE_PAUSE    = "pause"
WB_STATE_CHARGING = "charging"
WB_STATES_READY   = {WB_STATE_WAITING, WB_STATE_PAUSE}  # pronti a ricevere auth

# ── Charging modes (interni al coordinator) ────────────────────────────────────
CHARGING_MODE_IDLE        = "idle"
CHARGING_MODE_PV_SURPLUS  = "pv_surplus"
CHARGING_MODE_NIGHT       = "night"
CHARGING_MODE_FORCE       = "force"
CHARGING_MODE_MASTER_STOP = "master_stop"

CHARGING_MODES = [
    CHARGING_MODE_IDLE,
    CHARGING_MODE_PV_SURPLUS,
    CHARGING_MODE_NIGHT,
    CHARGING_MODE_FORCE,
    CHARGING_MODE_MASTER_STOP,
]

# ── Entity unique-ID suffixes ──────────────────────────────────────────────────
SENSOR_CHARGING_MODE          = "charging_mode"
SENSOR_PV_SURPLUS             = "pv_surplus"
SENSOR_TARGET_SOC             = "target_soc"
SENSOR_TIME_REMAINING         = "time_remaining"
SENSOR_CHARGE_END_TIME        = "charge_end_time"
SENSOR_WALLBOX_CURRENT_TARGET = "wallbox_current_target"
SENSOR_WALLBOX_CURRENT_ACTUAL = "wallbox_current_actual"

SWITCH_MASTER_STOP      = "master_stop"
SWITCH_FORCE_CHARGE     = "force_charge"
SWITCH_SOLAR_CONTROLLER = "solar_controller"
SWITCH_NIGHT_CHARGING   = "night_charging"

NUMBER_USER_SOC_TARGET    = "user_soc_target"
NUMBER_VEHICLE_SOC_TARGET = "vehicle_soc_target"
NUMBER_CONTRACT_POWER     = "contract_power"
NUMBER_ALLOWED_IMPORT     = "allowed_import"
NUMBER_NIGHT_POWER_LIMIT  = "night_power_limit"
NUMBER_BATTERY_CAPACITY   = "battery_capacity"
