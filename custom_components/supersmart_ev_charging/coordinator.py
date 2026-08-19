"""Coordinator for SuperSmart EV Charging – logica replicata dalle automazioni YAML Silla Prism."""
from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .calculations import (
    active_soc_target,
    balanced_current,
    charging_time_minutes,
    clamp_voltage,
    pv_current_values,
    wallbox_current_from_power,
)

from .const import (
    DOMAIN,
    CONF_CONTRACT_POWER_W,
    CONF_BATTERY_CAPACITY_KWH,
    CONF_VEHICLE_SOC_ENTITY,
    CONF_VEHICLE_CHARGE_LIMIT_ENTITY,
    CONF_VEHICLE_CONNECTED_ENTITY,
    CONF_WALLBOX_STATE_ENTITY,
    CONF_WALLBOX_POWER_ENTITY,
    CONF_WALLBOX_VOLTAGE_ENTITY,
    CONF_GRID_POWER_ENTITY,
    CONF_TOTAL_POWER_ENTITY,
    CONF_PV_POWER_ENTITY,
    CONF_TARIFF_ENTITY,
    CONF_TARIFF_OFFPEAK_VALUE,
    CONF_TARIFF_ENABLED,
    CONF_MQTT_ENABLED,
    CONF_MQTT_TOPIC_SET_CURRENT,
    CONF_MQTT_TOPIC_SET_MODE,
    CONF_MQTT_TOPIC_AUTHORIZE,
    CONF_MQTT_TOPIC_REVOKE,
    CONF_MQTT_PAYLOAD_MODE_SOLAR,
    CONF_MQTT_PAYLOAD_MODE_NORMAL,
    CONF_MQTT_PAYLOAD_MODE_PAUSE,
    CONF_BUTTON_AUTHORIZE_ENTITY,
    CONF_BUTTON_REVOKE_ENTITY,
    CONF_ENERGY_PUBLISH_ENABLED,
    CONF_MQTT_TOPIC_POWER_GRID,
    CONF_MQTT_TOPIC_POWER_SOLAR,
    CONF_MQTT_TOPIC_POWER_HOUSE,
    CONF_NOTIFY_SERVICE,
    CONF_NOTIFY_SERVICES,
    CONF_NOTIFICATIONS_ENABLED,
    CONF_NOTIFICATION_LANGUAGE,
    CONF_NOTIFICATION_CUSTOMIZE,
    CONF_NOTIFY_START_TITLE,
    CONF_NOTIFY_START_MESSAGE,
    CONF_NOTIFY_STOP_TITLE,
    CONF_NOTIFY_STOP_MESSAGE,
    CONF_WALLBOX_MODE_ENTITY,
    DEFAULT_CONTRACT_POWER_W,
    DEFAULT_BATTERY_CAPACITY_KWH,
    DEFAULT_ALLOWED_IMPORT_W,
    MIN_ALLOWED_IMPORT_W,
    MAX_ALLOWED_IMPORT_W,
    DEFAULT_MIN_CHARGE_CURRENT_A,
    DEFAULT_MAX_CHARGE_CURRENT_A,
    DEFAULT_MAX_LOAD_CURRENT_A,
    DEFAULT_NIGHT_POWER_LIMIT_W,
    DEFAULT_USER_SOC_TARGET,
    DEFAULT_VEHICLE_SOC_TARGET,
    DEFAULT_TARIFF_OFFPEAK_VALUE,
    DEFAULT_PV_START_CURRENT_A,
    DEFAULT_PV_STOP_CURRENT_A,
    DEFAULT_FV_HYGIENE_CURRENT_A,
    DEFAULT_PV_STOP_CONFIRM_CYCLES,
    DEFAULT_PV_START_CONFIRM_CYCLES,
    DEFAULT_MQTT_TOPIC_POWER_GRID,
    DEFAULT_MQTT_TOPIC_POWER_SOLAR,
    DEFAULT_MQTT_TOPIC_POWER_HOUSE,
    WB_STATE_CHARGING,
    WB_STATE_IDLE,
    WB_STATE_WAITING,
    WB_STATES_READY,
    CHARGING_MODE_IDLE,
    CHARGING_MODE_PV_SURPLUS,
    CHARGING_MODE_NIGHT,
    CHARGING_MODE_FORCE,
    CHARGING_MODE_MASTER_STOP,
    NOTIFICATION_LANGUAGE_AUTO,
)
from .notifications import notification_defaults, render_notification_template

_LOGGER = logging.getLogger(__name__)


class SuperSmartEvChargingCoordinator(DataUpdateCoordinator):
    """
    SuperSmart EV Charging coordinator.

    Replica funzionale delle automazioni YAML per Silla Prism + Skoda Enyaq/Elroq:

    PRIORITÀ (dalla più alta):
      1. MASTER STOP  → revoca auth, blocca tutto
      2. STOP SOC     → stop assoluto se SOC ≥ limite_auto
      3. FORCE CHARGE → mode 2 (normal) + modula entro contratto
      4. SURPLUS FV   → mode 1 (solar), start ≥7A / stop <5.5A per 60s
      5. NOTTE F3     → mode 2 (normal), solo se FV < 7A e SOC < limite_utente
      6. STOP SOC F3  → stop se SOC ≥ limite_utente in F3 notte
      7. IGIENE FV    → spegne solar_controller_active se FV < 7A per 60s senza caricare

    AUTORIZZAZIONE: via button.press su entità HA (button.silla_prism_autorizza/revoca),
    NON tramite topic MQTT separati – timestamp tracciati in variabili interne.

    MQTT:
      - set_mode:          prism/1/command/set_mode  (payload "1","2","3")
      - set_current_limit: prism/1/command/set_current_limit  (payload "6.0", "7.5", …)

    POTENZA ISTANTANEA (sensor.potenza_istantanea):
      Il sensore è un template: rete_power + fotovoltaico_power
      Se CONF_TOTAL_POWER_ENTITY è configurato, viene letto direttamente.
      Altrimenti viene derivato internamente con la stessa formula:
        potenza_istantanea = grid_w + pv_w
      Entrambi i sensori (rete_power e fotovoltaico_power) devono quindi
      essere sempre configurati come CONF_GRID_POWER_ENTITY e CONF_PV_POWER_ENTITY.

    POTENZA CASA (per la modulazione contratto):
      potenza_casa = potenza_istantanea - wallbox_potenza
      margine_w    = max(limite_w - potenza_casa, 0)
      amp          = margine_w / v_grid
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
        )
        self.entry = entry
        d = {**entry.data, **entry.options}

        # ── Feature flags
        self._mqtt_enabled: bool   = d.get(CONF_MQTT_ENABLED, True)
        self._tariff_enabled: bool = d.get(CONF_TARIFF_ENABLED, True)

        # ── MQTT topics & payloads (solo set_mode e set_current_limit per Silla Prism)
        self._topic_set_current = d.get(CONF_MQTT_TOPIC_SET_CURRENT, "prism/1/command/set_current_limit")
        self._topic_set_mode    = d.get(CONF_MQTT_TOPIC_SET_MODE,    "prism/1/command/set_mode")
        # Per wallbox generici senza button entities HA
        self._topic_authorize   = d.get(CONF_MQTT_TOPIC_AUTHORIZE,   "wallbox/command/authorize")
        self._topic_revoke      = d.get(CONF_MQTT_TOPIC_REVOKE,      "wallbox/command/revoke")
        self._payload_solar     = d.get(CONF_MQTT_PAYLOAD_MODE_SOLAR,   "1")
        self._payload_normal    = d.get(CONF_MQTT_PAYLOAD_MODE_NORMAL,  "2")
        self._payload_pause     = d.get(CONF_MQTT_PAYLOAD_MODE_PAUSE,   "3")
        self._energy_publish_enabled = d.get(CONF_ENERGY_PUBLISH_ENABLED, True)
        self._topic_power_grid  = d.get(CONF_MQTT_TOPIC_POWER_GRID, DEFAULT_MQTT_TOPIC_POWER_GRID)
        self._topic_power_solar = d.get(CONF_MQTT_TOPIC_POWER_SOLAR, DEFAULT_MQTT_TOPIC_POWER_SOLAR)
        self._topic_power_house = d.get(CONF_MQTT_TOPIC_POWER_HOUSE, DEFAULT_MQTT_TOPIC_POWER_HOUSE)

        # ── Entità button Silla Prism (autorizza/revoca via button.press)
        # Se configurate, vengono usate AL POSTO dei topic MQTT dedicati
        self._button_authorize_entity = d.get(CONF_BUTTON_AUTHORIZE_ENTITY, "")
        self._button_revoke_entity    = d.get(CONF_BUTTON_REVOKE_ENTITY,    "")

        # ── Entity IDs
        self._soc_entity             = d.get(CONF_VEHICLE_SOC_ENTITY,          "")
        self._charge_limit_entity    = d.get(CONF_VEHICLE_CHARGE_LIMIT_ENTITY, "")
        self._connected_entity       = d.get(CONF_VEHICLE_CONNECTED_ENTITY,    "")
        self._wallbox_state_entity   = d.get(CONF_WALLBOX_STATE_ENTITY,        "")  # sensor.silla_prism_stato_wallbox
        self._wallbox_power_entity   = d.get(CONF_WALLBOX_POWER_ENTITY,        "")
        self._wallbox_voltage_entity = d.get(CONF_WALLBOX_VOLTAGE_ENTITY,      "")
        self._grid_entity            = d.get(CONF_GRID_POWER_ENTITY,           "")  # sensor.rete_power
        self._pv_entity              = d.get(CONF_PV_POWER_ENTITY,             "")  # sensor.fotovoltaico_power
        # sensor.potenza_istantanea = rete_power + fotovoltaico_power (template HA).
        # Se l'entità è configurata viene letta direttamente; altrimenti viene
        # calcolata con la stessa formula per non richiedere una config entry aggiuntiva.
        self._total_power_entity     = d.get(CONF_TOTAL_POWER_ENTITY,          "")  # opzionale
        self._tariff_entity          = d.get(CONF_TARIFF_ENTITY,               "")  # sensor.pun_fascia_corrente
        self._tariff_offpeak         = d.get(CONF_TARIFF_OFFPEAK_VALUE, DEFAULT_TARIFF_OFFPEAK_VALUE)
        self._wallbox_mode_entity    = d.get(CONF_WALLBOX_MODE_ENTITY, "")
        legacy_notify_service = str(d.get(CONF_NOTIFY_SERVICE, "")).strip()
        notify_services = d.get(CONF_NOTIFY_SERVICES)
        if notify_services is None:
            notify_services = [legacy_notify_service] if legacy_notify_service else []
        elif isinstance(notify_services, str):
            notify_services = [notify_services]
        self._notify_services = [
            str(service).strip() for service in notify_services if str(service).strip()
        ]
        self._notifications_enabled = bool(
            d.get(CONF_NOTIFICATIONS_ENABLED, bool(self._notify_services))
        )
        self._notification_language = d.get(
            CONF_NOTIFICATION_LANGUAGE, NOTIFICATION_LANGUAGE_AUTO
        )
        self._notification_customize = bool(d.get(CONF_NOTIFICATION_CUSTOMIZE, False))
        self._notification_templates = {
            "start_title": d.get(CONF_NOTIFY_START_TITLE),
            "start_message": d.get(CONF_NOTIFY_START_MESSAGE),
            "stop_title": d.get(CONF_NOTIFY_STOP_TITLE),
            "stop_message": d.get(CONF_NOTIFY_STOP_MESSAGE),
        }

        # ── Power / capacity
        self._contract_power_w: float     = d.get(CONF_CONTRACT_POWER_W,     DEFAULT_CONTRACT_POWER_W)
        self._battery_capacity_kwh: float = d.get(CONF_BATTERY_CAPACITY_KWH, DEFAULT_BATTERY_CAPACITY_KWH)

        # ── Stato controllabile (esposto come entità HA)
        self.master_stop: bool             = False   # input_boolean.ev_master_stop
        self.force_charge: bool            = False   # input_boolean.forza_ricarica
        self.solar_controller_active: bool = False   # input_boolean.ev_solar_controller_active
        self.night_charging_enabled: bool  = True    # abilita logica notturna F3

        # Limiti SOC esposti come number entities
        self.user_soc_target: float    = float(d.get("initial_user_soc_target",    DEFAULT_USER_SOC_TARGET))
        self.vehicle_soc_target: float = float(d.get("initial_vehicle_soc_target", DEFAULT_VEHICLE_SOC_TARGET))

        # Limiti potenza esposti come number entities
        self.allowed_import_w: float    = DEFAULT_ALLOWED_IMPORT_W   # input_number.limite_import_permesso
        self.night_power_limit_w: float = DEFAULT_NIGHT_POWER_LIMIT_W  # input_number.ev_limite_notturno_w

        # ── Contatori isteresi FV (replicano i trigger template con for:)
        # FV stop: trigger YAML for:60s → 2 cicli da 30 s
        self._pv_below_stop_cycles: int  = 0
        # FV start: trigger YAML for:30s → 1 ciclo da 30 s
        self._pv_above_start_cycles: int = 0
        # Igiene controller: for:60s → 2 cicli da 30 s
        self._fv_hygiene_cycles: int     = 0
        self._pv_above_since: datetime | None = None
        self._pv_below_since: datetime | None = None
        self._force_below_since: datetime | None = None
        self._night_below_since: datetime | None = None
        self._hygiene_since: datetime | None = None

        # ── Stato derivato / calcolato
        self.charging_mode: str              = CHARGING_MODE_IDLE
        self.amp_fv_surplus: float           = 0.0   # corrente FV calcolata (A)
        self.wallbox_current_target_a: float = 0.0
        self.last_limit_sent_a: float        = 0.0
        self.last_authorization_ts: datetime | None = None
        self.last_revoke_ts: datetime | None        = None
        self.pv_surplus_w: float = 0.0
        self._logic_lock = asyncio.Lock()
        self._state_change_task: asyncio.Task | None = None
        self._notification_tasks: set[asyncio.Task] = set()
        self._last_notified_mode: str = "sconosciuta"
        self._vehicle_limit_sync_pending = False
        self._vehicle_limit_sync_task: asyncio.Task | None = None
        self._vehicle_limit_requested_value: float | None = None
        self._store: Store[dict[str, Any]] = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self._save_task: asyncio.Task | None = None

    async def async_restore_state(self) -> None:
        """Ripristina gli helper interni prima del primo aggiornamento.

        Il caricamento viene richiamato esplicitamente da ``async_setup_entry``
        per non dipendere dall'hook ``DataUpdateCoordinator._async_setup``, che
        non esiste nelle versioni meno recenti di Home Assistant.
        """
        saved = await self._store.async_load()
        if not saved:
            return
        self.master_stop = bool(saved.get("master_stop", self.master_stop))
        self.force_charge = bool(saved.get("force_charge", self.force_charge))
        self.solar_controller_active = bool(
            saved.get("solar_controller_active", self.solar_controller_active)
        )
        self.night_charging_enabled = bool(
            saved.get("night_charging_enabled", self.night_charging_enabled)
        )
        self.user_soc_target = float(saved.get("user_soc_target", self.user_soc_target))
        self.vehicle_soc_target = float(saved.get("vehicle_soc_target", self.vehicle_soc_target))
        saved_allowed_import = float(
            saved.get("allowed_import_w", self.allowed_import_w)
        )
        self.allowed_import_w = max(
            MIN_ALLOWED_IMPORT_W,
            min(saved_allowed_import, MAX_ALLOWED_IMPORT_W),
        )
        self.night_power_limit_w = float(saved.get("night_power_limit_w", self.night_power_limit_w))
        self._contract_power_w = float(saved.get("contract_power_w", self._contract_power_w))
        self.last_limit_sent_a = float(saved.get("last_limit_sent_a", self.last_limit_sent_a))
        self.charging_mode = str(saved.get("charging_mode", self.charging_mode))

    # ── DataUpdateCoordinator ──────────────────────────────────────────────────
    async def _async_update_data(self) -> dict[str, Any]:
        """Legge i sensori e calcola tutto lo stato derivato."""
        data: dict[str, Any] = {}
        try:
            # Wallbox
            wb_state   = self._get_state(self._wallbox_state_entity, default=WB_STATE_IDLE)
            wb_w       = abs(self._get_float(self._wallbox_power_entity))
            v_raw      = self._get_float(self._wallbox_voltage_entity, default=0.0)
            voltage    = clamp_voltage(v_raw)

            data["wallbox_state"]   = wb_state
            data["wallbox_power_w"] = wb_w
            data["wallbox_voltage_v"] = voltage
            data["critical_inputs_valid"] = all((
                self._has_value(self._wallbox_state_entity),
                self._has_numeric_value(self._wallbox_power_entity),
                self._has_numeric_value(self._grid_entity),
                self._has_numeric_value(self._pv_entity),
                not self._total_power_entity or self._has_numeric_value(self._total_power_entity),
            ))

            # Rete (+ = import dalla rete, - = export verso rete)
            grid_w = self._get_float(self._grid_entity)
            data["grid_power_w"] = grid_w

            # FV produzione
            pv_w = self._get_float(self._pv_entity)
            data["pv_power_w"] = pv_w

            # Potenza istantanea totale (casa + wallbox).
            # Formula template HA: rete_power + fotovoltaico_power
            # Se il sensore template è configurato viene letto direttamente,
            # altrimenti viene derivato con la stessa identica formula.
            if self._total_power_entity:
                total_w = self._get_float(self._total_power_entity)
            else:
                total_w = grid_w + pv_w   # replica: rete_power + fotovoltaico_power
            house_w = max(0.0, total_w - wb_w)
            data["total_power_w"] = total_w
            data["house_power_w"] = house_w

            # Replica esatta delle variabili del controller FV YAML:
            # delta_a = (-rete + offset) / V
            # amp_new_raw = corrente wallbox attuale + delta_a
            # Durante la carica è amp_new_raw, non delta_a, il nuovo setpoint.
            delta_a, amp_new_raw = pv_current_values(
                wb_w, grid_w, self.allowed_import_w, voltage
            )
            self.amp_fv_surplus = delta_a
            self.pv_surplus_w = max(0.0, -grid_w + self.allowed_import_w)
            data["amp_fv_surplus"] = delta_a
            data["amp_fv_target"] = amp_new_raw
            data["pv_surplus_w"] = self.pv_surplus_w

            # Veicolo
            soc, soc_valid = self._get_valid_float(self._soc_entity)
            data["vehicle_soc"]       = soc
            data["vehicle_soc_valid"] = soc_valid

            # Sync Auto -> integrazione. Il verso opposto è gestito dal number.
            if self._charge_limit_entity and not self._vehicle_limit_sync_pending:
                car_limit, car_limit_valid = self._get_valid_float(
                    self._charge_limit_entity
                )
                if car_limit_valid:
                    self.vehicle_soc_target = car_limit
                    if self.user_soc_target > self.vehicle_soc_target:
                        self.user_soc_target = self.vehicle_soc_target

            # Connessione veicolo:
            # Se configurata un'entità dedicata (binary_sensor o sensor), la usa.
            # Altrimenti la deriva dallo stato wallbox: qualsiasi stato != idle = connesso.
            # (Replica logica YAML: il veicolo è connesso se la wallbox non è idle)
            if self._connected_entity:
                connected_state = self._get_state(self._connected_entity, "").lower()
                vehicle_connected = connected_state in (
                    "on", "true", "connected", "yes", "1",
                    WB_STATE_WAITING, "pause", WB_STATE_CHARGING,
                )
            else:
                vehicle_connected = wb_state != WB_STATE_IDLE
            data["vehicle_connected"] = vehicle_connected

            # Fascia tariffaria
            if self._tariff_enabled and self._tariff_entity:
                tariff = self._get_state(self._tariff_entity, default="")
                is_offpeak = tariff == self._tariff_offpeak
            else:
                tariff, is_offpeak = "", False
            data["tariff_value"] = tariff
            data["is_offpeak"]   = is_offpeak

            # Sole sotto orizzonte (sun.sun)
            sun_state         = self._get_state("sun.sun", default="above_horizon")
            sun_below_horizon = sun_state == "below_horizon"
            data["sun_below_horizon"] = sun_below_horizon

            # Target SOC attivo
            target_soc = active_soc_target(
                self.charging_mode,
                self.force_charge,
                self.solar_controller_active,
                self.user_soc_target,
                self.vehicle_soc_target,
            )
            data["target_soc_active"] = target_soc

            # Il target è l'ultimo limite realmente inviato alla wallbox,
            # indipendentemente dalla modalità. La corrente effettiva è invece
            # stimata da potenza/tensione e viene esposta separatamente.
            self.wallbox_current_target_a = self.last_limit_sent_a
            data["wallbox_current_target_a"] = self.wallbox_current_target_a
            data["wallbox_current_actual_a"] = wallbox_current_from_power(
                wb_w,
                voltage,
            )

            # Stima tempo rimanente
            remaining_min = charging_time_minutes(
                soc,
                target_soc,
                self._battery_capacity_kwh,
                wb_w,
            )
            data["remaining_minutes"] = remaining_min
            data["charge_end_time"]   = (
                dt_util.now() + timedelta(minutes=remaining_min)
                if remaining_min is not None else None
            )

            # Diagnostica contatori
            data["pv_below_stop_cycles"]  = self._pv_below_stop_cycles
            data["pv_above_start_cycles"] = self._pv_above_start_cycles
            data["fv_hygiene_cycles"]     = self._fv_hygiene_cycles

            data["charging_mode"]           = self.charging_mode
            data["master_stop"]             = self.master_stop
            data["force_charge"]            = self.force_charge
            data["solar_controller_active"] = self.solar_controller_active

        except Exception as err:
            raise UpdateFailed(f"SuperSmart EV Charging – errore lettura dati: {err}") from err

        return data

    # ── Loop principale di decisione ───────────────────────────────────────────
    async def async_update_charging_logic(
        self,
        _now: datetime | None = None,
        trigger_entity: str | None = None,
    ) -> None:
        """Serializza le valutazioni avviate dal timer e dagli eventi di stato."""
        async with self._logic_lock:
            await self._async_update_charging_logic(_now, trigger_entity)

    async def _async_update_charging_logic(
        self,
        _now: datetime | None = None,
        trigger_entity: str | None = None,
    ) -> None:
        """
        Valuta le condizioni di ricarica ogni 30 s e invia comandi MQTT.

        Replica la logica delle automazioni YAML nell'ordine esatto di priorità:
          1. MASTER STOP
          2. SOC ≥ limite_auto → STOP assoluto (Gestione SOC)
          3. FORZA RICARICA (Gestione Carichi)
          4. SURPLUS FV ≥ 7A  → mode solar (Surplus FV)
          5. F3 + notte + SOC < limite_utente → mode normal (Gestione Fascia)
          6. F3 notte + SOC ≥ limite_utente + FV assente → STOP (Gestione SOC F3)
          7. IGIENE controller FV
        """
        await self.async_refresh()
        data = self.data
        if not data:
            return

        await self._publish_energy_data(data)

        wb_state          = data.get("wallbox_state", WB_STATE_IDLE)
        vehicle_connected = data.get("vehicle_connected", False)
        vehicle_soc       = data.get("vehicle_soc", 0.0)
        soc_valid         = data.get("vehicle_soc_valid", False)
        critical_valid    = data.get("critical_inputs_valid", False)
        is_offpeak        = data.get("is_offpeak", False)           # fascia F3
        sun_below         = data.get("sun_below_horizon", False)
        amp_fv            = data.get("amp_fv_surplus", 0.0)
        amp_fv_target     = data.get("amp_fv_target", 0.0)
        voltage           = data.get("wallbox_voltage_v", 230.0)

        # ── 0. Veicolo scollegato → reset tutto ───────────────────────────────
        # Le automazioni originali eseguono il reset sullo stato ``idle``
        # della wallbox, indipendentemente da un eventuale sensore veicolo.
        if wb_state == WB_STATE_IDLE:
            changed = any((
                self.master_stop,
                self.force_charge,
                self.solar_controller_active,
                self.charging_mode != CHARGING_MODE_IDLE,
            ))
            self.master_stop             = False
            self.solar_controller_active = False
            self.force_charge            = False
            self.charging_mode           = CHARGING_MODE_IDLE
            self._reset_pv_counters()
            self._fv_hygiene_cycles = 0
            if changed:
                _LOGGER.info("[SuperSmart] Veicolo scollegato (wallbox idle) – reset completo")
                self.async_update_listeners()
            return

        # Fail-safe: con ingressi critici non validi non vengono inviati comandi.
        if not soc_valid or not critical_valid:
            _LOGGER.debug("[SuperSmart] Input critico o SOC non valido – skip ciclo")
            return

        # ── 1. MASTER STOP – priorità assoluta ────────────────────────────────
        if self.master_stop:
            if self.charging_mode != CHARGING_MODE_MASTER_STOP:
                _LOGGER.warning("[SuperSmart] Master Stop attivo – revoca autorizzazione")
                self.solar_controller_active = False
                self.force_charge            = False
                await self._set_mode(self._payload_pause)
                await self._delay(2)
                await self._revoke()
                self.charging_mode = CHARGING_MODE_MASTER_STOP
                self._reset_pv_counters()
                self.async_update_listeners()
            return

        # ── 2. GESTIONE SOC – stop assoluto se SOC ≥ limite_auto ──────────────
        # Replica: "soc >= limite_auto and stato != 'pause'" → revoca + FV OFF + FORZA OFF
        if vehicle_soc >= self.vehicle_soc_target and wb_state != "pause":
            _LOGGER.info(
                "[SuperSmart] SOC %.0f%% ≥ limite_auto %.0f%% – stop assoluto",
                vehicle_soc, self.vehicle_soc_target,
            )
            self.force_charge = False
            await self._set_mode(self._payload_pause)
            await self._delay(1)
            await self._revoke()
            self.solar_controller_active = False
            self.charging_mode           = CHARGING_MODE_IDLE
            self._reset_pv_counters()
            self._fv_hygiene_cycles = 0
            self.async_update_listeners()
            return

        # ── 3. FORZA RICARICA (Gestione Carichi - FORZA ON) ───────────────────
        if self.force_charge:
            self._pv_above_start_cycles = 0
            self._fv_hygiene_cycles = 0

            amp_contratto = self._contratto_balanced_current(data, use_night_limit=False)

            if self.charging_mode != CHARGING_MODE_FORCE:
                # Avvio FORZA: waiting/pause + SOC < limite_auto + amp ≥ 7A
                if wb_state in WB_STATES_READY and amp_contratto >= 7:
                    _LOGGER.info("[SuperSmart] FORZA attivata – avvio ricarica mode 2")
                    await self._send_limit(6.0)
                    await self._set_mode(self._payload_normal)
                    await self._authorize()
                    self.charging_mode = CHARGING_MODE_FORCE
                    self._pv_below_stop_cycles = 0
                    self.async_update_listeners()
                elif wb_state == WB_STATE_CHARGING:
                    _LOGGER.info("[SuperSmart] FORZA attivata durante una carica – passa a mode 2")
                    await self._set_mode(self._payload_normal)
                    self.charging_mode = CHARGING_MODE_FORCE
                    self._force_below_since = None
                    if amp_contratto >= 6:
                        await self._send_limit_if_changed(amp_contratto)
            else:
                # Modulazione FORZA in corso: charging + diff ≥ 0.5A
                if wb_state == WB_STATE_CHARGING and amp_contratto >= 6:
                    self._pv_below_stop_cycles = 0
                    self._force_below_since = None
                    await self._send_limit_if_changed(amp_contratto)
                elif wb_state == WB_STATE_CHARGING and amp_contratto < DEFAULT_PV_STOP_CURRENT_A:
                    now = dt_util.now()
                    self._force_below_since = self._force_below_since or now
                    self._pv_below_stop_cycles = int((now - self._force_below_since).total_seconds() // 30)
                    if (now - self._force_below_since).total_seconds() >= 60:
                        _LOGGER.info("[SuperSmart] FORZA: margine < 5.5A per 60 s – verifica soft-stop")
                        await self._send_limit(6.0)
                        await self._delay_seconds(20)
                        wb_state_now = self._get_state(self._wallbox_state_entity, WB_STATE_IDLE)
                        amp_now = self._contratto_balanced_current_now(self._safe_voltage(), False)
                        if wb_state_now == WB_STATE_CHARGING and amp_now < DEFAULT_PV_STOP_CURRENT_A:
                            await self._set_mode(self._payload_pause)
                            await self._revoke()
                            self.charging_mode = CHARGING_MODE_IDLE
                        self._reset_pv_counters()
                else:
                    self._force_below_since = None
                    self._pv_below_stop_cycles = 0
            self.async_update_listeners()
            return

        # ── 4. SURPLUS FV – lavora in tutte le fasce ──────────────────────────
        # skip_in_f3: se F3 e SOC < limite_utente e amp_fv < 7 → lascia spazio alla logica notturna
        skip_in_f3 = (
            is_offpeak
            and vehicle_soc < self.user_soc_target
            and amp_fv < DEFAULT_PV_START_CURRENT_A
            and not self.solar_controller_active
        )

        if not skip_in_f3:
            # ── 4a. Stop FV: amp_fv < 5.5 per 60 s mentre carica ─────────────
            if self.solar_controller_active and wb_state == WB_STATE_CHARGING and amp_fv_target < DEFAULT_PV_STOP_CURRENT_A:
                now = dt_util.now()
                self._pv_below_since = self._pv_below_since or now
                self._pv_below_stop_cycles = int((now - self._pv_below_since).total_seconds() // 30)
                self._pv_above_start_cycles = 0
                _LOGGER.debug(
                    "[SuperSmart] FV sotto soglia %.1fA < %.1fA – ciclo %d/%d",
                    amp_fv_target, DEFAULT_PV_STOP_CURRENT_A,
                    self._pv_below_stop_cycles, DEFAULT_PV_STOP_CONFIRM_CYCLES,
                )
                if (now - self._pv_below_since).total_seconds() >= 60:
                    _LOGGER.info("[SuperSmart] FV calato – stop carica + revoca auth")
                    await self._set_mode(self._payload_pause)
                    await self._revoke()
                    self.solar_controller_active = False
                    self.charging_mode           = CHARGING_MODE_IDLE
                    self._reset_pv_counters()
                    self._fv_hygiene_cycles = 0
                    self.async_update_listeners()
                return
            self._pv_below_since = None
            self._pv_below_stop_cycles = 0

            # ── 4b. Avvio FV: amp_fv ≥ 7 per 30 s + waiting/pause ────────────
            if amp_fv_target >= DEFAULT_PV_START_CURRENT_A and wb_state in WB_STATES_READY:
                now = dt_util.now()
                self._pv_above_since = self._pv_above_since or now
                self._pv_above_start_cycles = int((now - self._pv_above_since).total_seconds() // 30)
                self._pv_below_stop_cycles   = 0
                self._fv_hygiene_cycles      = 0
                _LOGGER.debug(
                    "[SuperSmart] FV surplus %.1fA ≥ 7A – ciclo %d/%d",
                    amp_fv_target, self._pv_above_start_cycles, DEFAULT_PV_START_CONFIRM_CYCLES,
                )
                # Le YAML avviano subito sul cambio stato della wallbox (o
                # riattivando il controller FV); negli altri casi richiedono
                # che la soglia resti vera per 30 secondi.
                immediate_start = (
                    trigger_entity == self._wallbox_state_entity
                    or (
                        self.solar_controller_active
                        and trigger_entity == "solar_controller"
                    )
                )
                if immediate_start or (now - self._pv_above_since).total_seconds() >= 30:
                    _LOGGER.info("[SuperSmart] FV stabile – avvio ricarica solare mode 1")
                    self.solar_controller_active = True
                    await self._set_mode(self._payload_solar)
                    await self._send_limit(6.0)
                    await self._delay(2)
                    await self._authorize()
                    self.charging_mode = CHARGING_MODE_PV_SURPLUS
                    self._reset_pv_counters()
                    self._fv_hygiene_cycles = 0
                    self.async_update_listeners()
                return
            self._pv_above_since = None
            self._pv_above_start_cycles = 0

            # ── 4c. Modulazione FV: charging + solar_active + diff ≥ 0.5 ─────
            if self.solar_controller_active and wb_state == WB_STATE_CHARGING:
                self._pv_below_stop_cycles   = 0
                self._pv_above_start_cycles  = 0
                self._fv_hygiene_cycles      = 0
                wb_w = data.get("wallbox_power_w", 0.0)
                amp_limit = min(max(amp_fv_target, 0.0), DEFAULT_MAX_CHARGE_CURRENT_A)
                amp_limit   = round(amp_limit, 1)
                if wb_w > 500 and amp_limit >= 6:
                    await self._send_limit_if_changed(amp_limit)
                self.async_update_listeners()
                return

        # ── 5. GESTIONE FASCIA F3 NOTTE – avvio notturno ──────────────────────
        # Condizioni YAML: F3 + sole sotto orizzonte + solar_active=OFF + SOC < limite_utente
        #                  + amp (contratto) ≥ 7A + amp_fv < 6A + stato in [waiting, pause]
        if (self.night_charging_enabled
                and self._tariff_enabled
                and is_offpeak
                and sun_below
                and not self.solar_controller_active
                and vehicle_soc < self.user_soc_target
                and wb_state in WB_STATES_READY):

            # L'automazione "Gestione Fascia" usa il limite contrattuale per
            # decidere l'avvio. Solo la modulazione successiva usa il limite
            # notturno ridotto ("Gestione Carichi").
            amp_contratto = self._contratto_balanced_current(data, use_night_limit=False)
            if amp_contratto >= 7 and amp_fv < 6:
                _LOGGER.info(
                    "[SuperSmart] F3 notte – avvio ricarica notturna mode 2 (SOC %.0f%% < %.0f%%)",
                    vehicle_soc, self.user_soc_target,
                )
                self.solar_controller_active = False
                await self._send_limit(6.0)
                await self._set_mode(self._payload_normal)
                await self._delay(1)
                await self._authorize()
                self.charging_mode = CHARGING_MODE_NIGHT
                self._reset_pv_counters()
                self._fv_hygiene_cycles = 0
                self.async_update_listeners()
                return

        # ── 6. GESTIONE CARICHI NOTTURNA – modulazione in F3 ──────────────────
        # Condizioni: F3 + notte + solar_active=OFF + charging + SOC < limite_utente
        if (self.night_charging_enabled
                and self._tariff_enabled
                and is_offpeak
                and sun_below
                and not self.solar_controller_active
                and wb_state == WB_STATE_CHARGING
                and vehicle_soc < self.user_soc_target):

            amp_contratto = self._contratto_balanced_current(data, use_night_limit=True)

            if amp_contratto >= 6:
                self._pv_below_stop_cycles = 0
                self._night_below_since = None
                await self._send_limit_if_changed(amp_contratto)
                self.async_update_listeners()
                return
            elif self._contratto_balanced_current(
                data, use_night_limit=False
            ) < DEFAULT_PV_STOP_CURRENT_A:
                # Il trigger low_margin_60s delle YAML usa il limite
                # contrattuale anche nel ramo notturno. La modulazione sopra,
                # invece, resta correttamente basata sul limite notturno.
                now = dt_util.now()
                self._night_below_since = self._night_below_since or now
                self._pv_below_stop_cycles = int((now - self._night_below_since).total_seconds() // 30)
                if (now - self._night_below_since).total_seconds() >= 60:
                    _LOGGER.info("[SuperSmart] F3: margine potenza esaurito – stop ricarica")
                    await self._send_limit(6.0)
                    await self._delay_seconds(20)
                    # Rileggi stato dopo delay
                    wb_state_now = self._get_state(self._wallbox_state_entity, WB_STATE_IDLE)
                    v_now        = self._safe_voltage()
                    if wb_state_now == WB_STATE_CHARGING:
                        amp_contratto_now = self._contratto_balanced_current_now(
                            v_now, use_night_limit=False
                        )
                        if amp_contratto_now < DEFAULT_PV_STOP_CURRENT_A:
                            await self._set_mode(self._payload_pause)
                            await self._revoke()
                            self.charging_mode  = CHARGING_MODE_IDLE
                            self._reset_pv_counters()
                            self._fv_hygiene_cycles = 0
                self.async_update_listeners()
                return
            else:
                self._night_below_since = None
                self._pv_below_stop_cycles = 0

        # ── 7. GESTIONE SOC F3 – stop se SOC ≥ limite_utente in notte senza FV ─
        if (self.night_charging_enabled
                and self._tariff_enabled
                and is_offpeak
                and sun_below
                and not self.force_charge
                and vehicle_soc >= self.user_soc_target
                and amp_fv < 6
                and wb_state == WB_STATE_CHARGING):
            _LOGGER.info(
                "[SuperSmart] F3: SOC %.0f%% ≥ limite_utente %.0f%% – stop ricarica notturna",
                vehicle_soc, self.user_soc_target,
            )
            await self._set_mode(self._payload_pause)
            await self._delay(1)
            await self._revoke()
            self.solar_controller_active = False
            self.charging_mode           = CHARGING_MODE_IDLE
            self._reset_pv_counters()
            self._fv_hygiene_cycles      = 0
            self.async_update_listeners()
            return

        # ── 8. USCITA INTELLIGENTE DA FORZA (chiamata quando force_charge → OFF)
        # Gestita in ForceChargeSwitch.async_turn_off() → _handle_force_exit()

        # ── 9. IGIENE CONTROLLER FV – spegne solar_active se inutile ──────────
        # Condizioni YAML: (not forza) and solar_active and stato != 'charging' and amp_fv < 7
        if (not self.force_charge
                and self.solar_controller_active
                and wb_state != WB_STATE_CHARGING
                and amp_fv < DEFAULT_FV_HYGIENE_CURRENT_A):
            now = dt_util.now()
            self._hygiene_since = self._hygiene_since or now
            self._fv_hygiene_cycles = int((now - self._hygiene_since).total_seconds() // 30)
            _LOGGER.debug(
                "[SuperSmart] Igiene FV: controller attivo inutilmente – ciclo %d/2",
                self._fv_hygiene_cycles,
            )
            if (now - self._hygiene_since).total_seconds() >= 60:
                _LOGGER.info("[SuperSmart] Igiene FV – spegne solar_controller_active")
                self.solar_controller_active = False
                self._fv_hygiene_cycles      = 0
                self._hygiene_since = None
                if self.charging_mode == CHARGING_MODE_PV_SURPLUS:
                    self.charging_mode = CHARGING_MODE_IDLE
                self.async_update_listeners()
        else:
            self._fv_hygiene_cycles = 0
            self._hygiene_since = None

        self.async_update_listeners()

    # ── Uscita intelligente da FORZA ──────────────────────────────────────────
    async def _handle_force_exit(self) -> None:
        """
        Chiamata quando FORZA viene disattivata.
        Replica EV - Uscita intelligente da FORZA:
          - continua_fv (amp_fv ≥ 7) → attiva solar_controller
          - continua_notturna (F3 + SOC < limite_utente) → lascia andare Gestione Fascia
          - altrimenti → stop carica
        """
        wb_state = self._get_state(self._wallbox_state_entity, WB_STATE_IDLE)
        if wb_state != WB_STATE_CHARGING:
            return
        if self.master_stop:
            return

        soc, soc_valid = self._get_valid_float(self._soc_entity)
        if not soc_valid:
            return
        v_raw          = self._get_float(self._wallbox_voltage_entity, 0.0)
        voltage        = float(max(min(v_raw if v_raw > 0 else 230.0, 260.0), 180.0))
        grid_w         = self._get_float(self._grid_entity)
        wb_w           = abs(self._get_float(self._wallbox_power_entity))
        amp_fv_target  = (wb_w / voltage) + ((-grid_w + self.allowed_import_w) / voltage)
        tariff        = self._get_state(self._tariff_entity, "") if self._tariff_enabled else ""
        is_offpeak    = tariff == self._tariff_offpeak
        continua_notturna = self.night_charging_enabled and is_offpeak and (soc < self.user_soc_target)
        continua_fv       = amp_fv_target >= DEFAULT_PV_START_CURRENT_A

        # Stesso ordine del choose YAML: la prosecuzione F3 ha precedenza sul
        # FV quando entrambe le condizioni sono vere.
        if continua_notturna:
            _LOGGER.info("[SuperSmart] Uscita FORZA: F3 notturna – continua ricarica grid")
            self.charging_mode = CHARGING_MODE_NIGHT
        elif continua_fv:
            _LOGGER.info("[SuperSmart] Uscita FORZA: surplus FV disponibile – attiva solar controller")
            self.solar_controller_active = True
            self.charging_mode           = CHARGING_MODE_PV_SURPLUS
        else:
            _LOGGER.info("[SuperSmart] Uscita FORZA: nessuna condizione – stop ricarica")
            await self._set_mode(self._payload_pause)
            await self._revoke()
            self.solar_controller_active = False
            self.charging_mode           = CHARGING_MODE_IDLE

        self._reset_pv_counters()
        self.async_update_listeners()

    # ── Helpers calcolo corrente ───────────────────────────────────────────────
    def _contratto_balanced_current(self, data: dict[str, Any], use_night_limit: bool) -> float:
        """
        Corrente massima che non supera il limite di potenza.
        Replica la formula YAML di Gestione Fascia e Gestione Carichi:
          margine_w = max(limite_w - potenza_casa, 0)
          amp = margine_w / v_grid
        Potenza casa = potenza_tot - potenza_wallbox (NON usa grid+pv come il coordinatore originale).
        """
        voltage     = data.get("wallbox_voltage_v", 230.0)
        # limite_w: notturno (ev_limite_notturno_w) o contratto completo
        if use_night_limit:
            limite_w = self.night_power_limit_w
        else:
            limite_w = self._contract_power_w
        return balanced_current(
            limite_w,
            data.get("total_power_w", 0.0),
            data.get("wallbox_power_w", 0.0),
            voltage,
            DEFAULT_MAX_LOAD_CURRENT_A,
        )

    def _contratto_balanced_current_now(self, voltage: float, use_night_limit: bool) -> float:
        """
        Versione sincrona per ricalcolo intra-ciclo (dopo delay in stop-soft).
        Usa la stessa formula di _contratto_balanced_current:
          potenza_istantanea = total_power_entity  oppure  grid_w + pv_w
          potenza_casa       = potenza_istantanea - wallbox_potenza
        """
        wallbox_w = abs(self._get_float(self._wallbox_power_entity))
        if self._total_power_entity:
            total_w = self._get_float(self._total_power_entity)
        else:
            grid_w = self._get_float(self._grid_entity)
            pv_w   = self._get_float(self._pv_entity)
            total_w = grid_w + pv_w
        limite_w  = self.night_power_limit_w if use_night_limit else self._contract_power_w
        return balanced_current(
            limite_w, total_w, wallbox_w, voltage, DEFAULT_MAX_LOAD_CURRENT_A
        )

    def _safe_voltage(self) -> float:
        v_raw = self._get_float(self._wallbox_voltage_entity, 0.0)
        return clamp_voltage(v_raw)

    def _reset_pv_counters(self) -> None:
        self._pv_below_stop_cycles  = 0
        self._pv_above_start_cycles = 0
        self._pv_above_since = None
        self._pv_below_since = None
        self._force_below_since = None
        self._night_below_since = None

    def async_update_listeners(self) -> None:
        """Aggiorna le entità e persiste gli helper interni con debounce."""
        self._refresh_target_estimates()
        super().async_update_listeners()
        self._schedule_save()

    def _refresh_target_estimates(self) -> None:
        """Allinea target e stime anche dopo un cambio modalità interno."""
        if not self.data:
            return
        target_soc = active_soc_target(
            self.charging_mode,
            self.force_charge,
            self.solar_controller_active,
            self.user_soc_target,
            self.vehicle_soc_target,
        )
        self.data["target_soc_active"] = target_soc
        soc = float(self.data.get("vehicle_soc", 0.0))
        remaining_min = charging_time_minutes(
            soc,
            target_soc,
            self._battery_capacity_kwh,
            float(self.data.get("wallbox_power_w", 0.0)),
        )
        self.data["remaining_minutes"] = remaining_min
        self.data["charge_end_time"] = (
            dt_util.now() + timedelta(minutes=remaining_min)
            if remaining_min is not None
            else None
        )

    async def async_set_battery_capacity(self, value: float) -> None:
        """Update usable battery capacity and persist it in config options."""
        capacity = round(float(value), 1)
        self._battery_capacity_kwh = capacity
        self.async_update_listeners()
        options = {**self.entry.options, CONF_BATTERY_CAPACITY_KWH: capacity}
        self.hass.config_entries.async_update_entry(self.entry, options=options)

    def _schedule_save(self) -> None:
        if self._save_task and not self._save_task.done():
            self._save_task.cancel()
        self._save_task = self.hass.async_create_task(self._delayed_save())

    async def _delayed_save(self) -> None:
        task = asyncio.current_task()
        try:
            await asyncio.sleep(1)
            await self._save_state()
        except asyncio.CancelledError:
            return
        finally:
            if self._save_task is task:
                self._save_task = None

    async def _save_state(self) -> None:
        await self._store.async_save({
            "master_stop": self.master_stop,
            "force_charge": self.force_charge,
            "solar_controller_active": self.solar_controller_active,
            "night_charging_enabled": self.night_charging_enabled,
            "user_soc_target": self.user_soc_target,
            "vehicle_soc_target": self.vehicle_soc_target,
            "allowed_import_w": self.allowed_import_w,
            "night_power_limit_w": self.night_power_limit_w,
            "contract_power_w": self._contract_power_w,
            "last_limit_sent_a": self.last_limit_sent_a,
            "charging_mode": self.charging_mode,
        })

    # ── Eventi, sync target e notifiche ──────────────────────────────────────
    def schedule_state_change(self, entity_id: str, old_state: str, new_state: str) -> None:
        """Debounce degli eventi HA senza cancellare una decisione già in corso."""
        if entity_id == self._wallbox_state_entity and old_state != new_state:
            self._schedule_charge_notification(old_state, new_state)

        # Auto/MySkoda -> integrazione: nessun ritardo. Se durante l'attesa di
        # un comando HA arriva un valore diverso dall'auto, replica `mode:
        # restart` del vecchio YAML: annulla il comando in attesa e accetta
        # immediatamente il valore dell'auto. Un valore uguale a quello
        # richiesto è invece la conferma del nostro comando.
        if entity_id == self._charge_limit_entity:
            car_limit, car_limit_valid = self._get_valid_float(entity_id)
            if car_limit_valid:
                requested = self._vehicle_limit_requested_value
                if (
                    self._vehicle_limit_sync_pending
                    and requested is not None
                    and car_limit != requested
                ):
                    if (
                        self._vehicle_limit_sync_task
                        and not self._vehicle_limit_sync_task.done()
                    ):
                        self._vehicle_limit_sync_task.cancel()
                    self._vehicle_limit_sync_task = None
                    self._vehicle_limit_sync_pending = False
                    self._vehicle_limit_requested_value = None

                if not self._vehicle_limit_sync_pending or car_limit == requested:
                    self.vehicle_soc_target = car_limit
                    if self.user_soc_target > car_limit:
                        self.user_soc_target = car_limit
                    self.async_update_listeners()

        if self._state_change_task and not self._state_change_task.done():
            self._state_change_task.cancel()
        self._state_change_task = self.hass.async_create_task(
            self._debounced_logic(entity_id)
        )

    async def _debounced_logic(self, trigger_entity: str) -> None:
        task = asyncio.current_task()
        try:
            await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            return
        finally:
            if self._state_change_task is task:
                self._state_change_task = None
        await self.async_update_charging_logic(trigger_entity=trigger_entity)

    async def async_set_vehicle_soc_target(self, value: float) -> None:
        """Schedule HA -> vehicle sync after 3 seconds; latest value wins."""
        self.vehicle_soc_target = value
        if self.user_soc_target > value:
            self.user_soc_target = value

        if self._charge_limit_entity:
            if (
                self._vehicle_limit_sync_task
                and not self._vehicle_limit_sync_task.done()
            ):
                self._vehicle_limit_sync_task.cancel()
            self._vehicle_limit_sync_pending = True
            self._vehicle_limit_requested_value = value
            self._vehicle_limit_sync_task = self.hass.async_create_task(
                self._delayed_vehicle_soc_target_sync(value)
            )

        self.async_update_listeners()
        self.hass.async_create_task(self.async_update_charging_logic())

    async def _delayed_vehicle_soc_target_sync(self, value: float) -> None:
        """Send only the latest HA target after the 3-second activation delay."""
        task = asyncio.current_task()
        try:
            await asyncio.sleep(3)
            current = self._get_float(self._charge_limit_entity, value)
            if current == value:
                return
            domain = self._charge_limit_entity.split(".", 1)[0]
            await self.hass.services.async_call(
                domain,
                "set_value",
                {"entity_id": self._charge_limit_entity, "value": value},
                blocking=True,
            )
        except asyncio.CancelledError:
            return
        finally:
            if self._vehicle_limit_sync_task is task:
                self._vehicle_limit_sync_task = None
                self._vehicle_limit_sync_pending = False
                self._vehicle_limit_requested_value = None

    def _schedule_charge_notification(self, old_state: str, new_state: str) -> None:
        if not self._notifications_enabled or not self._notify_services:
            return
        if new_state == WB_STATE_CHARGING:
            task = self.hass.async_create_task(self._notify_charge_started())
        elif old_state == WB_STATE_CHARGING:
            task = self.hass.async_create_task(self._notify_charge_stopped())
        else:
            return
        self._notification_tasks.add(task)
        task.add_done_callback(self._notification_tasks.discard)

    async def _notify_charge_started(self) -> None:
        await asyncio.sleep(10)
        if self._get_state(self._wallbox_state_entity, WB_STATE_IDLE) != WB_STATE_CHARGING:
            return
        mode = self._notification_mode()
        self._last_notified_mode = mode
        soc = int(self._get_float(self._soc_entity))
        target = int(self.user_soc_target if mode == "notturna_f3" else self.vehicle_soc_target)
        defaults = notification_defaults(
            self._notification_language, self.hass.config.language
        )
        context = self._notification_context(mode, soc, target, defaults)
        await self._notify_from_template("start", context, defaults)

    async def _notify_charge_stopped(self) -> None:
        await asyncio.sleep(15)
        if self._get_state(self._wallbox_state_entity, WB_STATE_IDLE) == WB_STATE_CHARGING:
            return
        mode = self._last_notified_mode
        soc = int(self._get_float(self._soc_entity))
        target = int(
            self.user_soc_target if mode == "notturna_f3" else self.vehicle_soc_target
        )
        defaults = notification_defaults(
            self._notification_language, self.hass.config.language
        )
        context = self._notification_context(mode, soc, target, defaults)
        await self._notify_from_template("stop", context, defaults)
        self._last_notified_mode = "sconosciuta"

    def _notification_context(
        self,
        mode: str,
        soc: int,
        target: int,
        defaults: dict[str, Any],
    ) -> dict[str, Any]:
        """Build values exposed to optional user notification templates."""
        remaining = (self.data or {}).get("remaining_minutes")
        if remaining is None:
            time_remaining = "—"
        else:
            hours, minutes = divmod(max(0, int(remaining)), 60)
            time_remaining = f"{hours}h {minutes:02d}m" if hours else f"{minutes}m"
        end_time = (self.data or {}).get("charge_end_time")
        charge_end_time = (
            dt_util.as_local(end_time).strftime("%H:%M")
            if isinstance(end_time, datetime)
            else "—"
        )
        labels = defaults["modes"]
        return {
            "mode": labels.get(mode, labels["sconosciuta"]),
            "soc": soc,
            "target": target,
            "time_remaining": time_remaining,
            "charge_end_time": charge_end_time,
        }

    async def _notify_from_template(
        self,
        event: str,
        context: dict[str, Any],
        defaults: dict[str, Any],
    ) -> None:
        """Render localized defaults or the user's optional templates."""
        title_key = f"{event}_title"
        message_key = f"{event}_message"
        title_template = defaults[title_key]
        message_template = defaults[message_key]
        if self._notification_customize:
            title_template = self._notification_templates.get(title_key) or title_template
            message_template = self._notification_templates.get(message_key) or message_template
        try:
            title = render_notification_template(title_template, context)
            message = render_notification_template(message_template, context)
        except ValueError:
            _LOGGER.warning("Template notifica non valido; uso il testo predefinito")
            title = render_notification_template(defaults[title_key], context)
            message = render_notification_template(defaults[message_key], context)
        await self._notify(title, message)

    def _notification_mode(self) -> str:
        if self.force_charge or self.charging_mode == CHARGING_MODE_FORCE:
            return "forza"
        wb_mode = self._get_state(self._wallbox_mode_entity, "").lower()
        if self.solar_controller_active or wb_mode in ("solar", "solare"):
            return "fv_surplus"
        if self._get_state(self._tariff_entity, "") == self._tariff_offpeak:
            return "notturna_f3"
        return "sconosciuta"

    async def _notify(self, title: str, message: str) -> None:
        for notify_service in self._notify_services:
            try:
                domain, service = notify_service.split(".", 1)
            except ValueError:
                _LOGGER.warning("Servizio notifica non valido: %s", notify_service)
                continue
            if domain != "notify" or not self.hass.services.has_service(domain, service):
                _LOGGER.warning("Servizio notifica non disponibile: %s", notify_service)
                continue
            await self.hass.services.async_call(
                domain,
                service,
                {"title": title, "message": message},
                blocking=False,
            )

    async def async_shutdown(self) -> None:
        if self._state_change_task and not self._state_change_task.done():
            self._state_change_task.cancel()
        if (
            self._vehicle_limit_sync_task
            and not self._vehicle_limit_sync_task.done()
        ):
            self._vehicle_limit_sync_task.cancel()
        for task in list(self._notification_tasks):
            task.cancel()
        if self._save_task and not self._save_task.done():
            self._save_task.cancel()
        await self._save_state()
        await super().async_shutdown()

    async def _publish_energy_data(self, data: dict[str, Any]) -> None:
        """Replica i tre publish di "Prism - Invio Dati Energia"."""
        if not (self._mqtt_enabled and self._energy_publish_enabled):
            return
        values = (
            (self._topic_power_grid, data.get("grid_power_w", 0.0)),
            (self._topic_power_solar, data.get("pv_power_w", 0.0)),
            (self._topic_power_house, data.get("total_power_w", 0.0)),
        )
        for topic, value in values:
            if topic:
                try:
                    await mqtt.async_publish(
                        self.hass, topic, str(round(float(value))), qos=0
                    )
                except Exception as err:  # broker non disponibile: prossimo ciclo
                    _LOGGER.warning(
                        "[SuperSmart] Publish telemetria MQTT fallito su %s: %s",
                        topic,
                        err,
                    )

    # ── Comandi MQTT ──────────────────────────────────────────────────────────
    async def _authorize(self) -> None:
        """
        Autorizza ricarica.
        Se configurata un'entità button HA (Silla Prism), usa button.press.
        Altrimenti pubblica su topic MQTT generico.
        """
        self.last_authorization_ts = dt_util.now()
        if self._button_authorize_entity:
            await self._press_button(self._button_authorize_entity)
            _LOGGER.debug("[SuperSmart] Authorize → button.press %s", self._button_authorize_entity)
        elif self._mqtt_enabled:
            await mqtt.async_publish(self.hass, self._topic_authorize, "1", qos=1)
            _LOGGER.debug("[SuperSmart] Authorize → MQTT %s", self._topic_authorize)

    async def _revoke(self) -> None:
        """
        Revoca autorizzazione.
        Se configurata un'entità button HA (Silla Prism), usa button.press.
        Altrimenti pubblica su topic MQTT generico.
        """
        self.last_revoke_ts = dt_util.now()
        if self._button_revoke_entity:
            await self._press_button(self._button_revoke_entity)
            _LOGGER.debug("[SuperSmart] Revoke → button.press %s", self._button_revoke_entity)
        elif self._mqtt_enabled:
            await mqtt.async_publish(self.hass, self._topic_revoke, "1", qos=1)
            _LOGGER.debug("[SuperSmart] Revoke → MQTT %s", self._topic_revoke)

    async def _press_button(self, entity_id: str) -> None:
        """Preme un'entità button in HA (replica action: button.press)."""
        await self.hass.services.async_call(
            "button", "press", {"entity_id": entity_id}, blocking=True
        )

    async def _send_limit(self, current_a: float) -> None:
        """Invia limite corrente via MQTT. Salva last_limit_sent_a."""
        # La YAML usa float con 1 decimale: "6.0", "7.5" ecc. (NON int clamped)
        clamped = round(
            min(DEFAULT_MAX_LOAD_CURRENT_A, max(DEFAULT_MIN_CHARGE_CURRENT_A, current_a)),
            1,
        )
        if self._mqtt_enabled:
            await mqtt.async_publish(
                self.hass, self._topic_set_current, f"{clamped:.1f}", qos=1
            )
        self.last_limit_sent_a = clamped
        self.wallbox_current_target_a = clamped
        if self.data is not None:
            self.data["wallbox_current_target_a"] = clamped
        self.async_update_listeners()
        _LOGGER.debug("[SuperSmart] Corrente %.1fA → %s", clamped, self._topic_set_current)

    async def _send_limit_if_changed(self, current_a: float) -> None:
        """Invia limite solo se cambiato ≥ 0.5A (anti-spam YAML: diff ≥ 0.5)."""
        if abs(current_a - self.last_limit_sent_a) >= 0.5:
            await self._send_limit(current_a)

    async def _set_mode(self, payload: str) -> None:
        if not self._mqtt_enabled or not self._topic_set_mode:
            return
        await mqtt.async_publish(self.hass, self._topic_set_mode, payload, qos=1)
        _LOGGER.debug("[SuperSmart] Mode '%s' → %s", payload, self._topic_set_mode)

    async def _delay(self, seconds: int) -> None:
        """Delay asincrono (replica i 'delay:' nelle sequenze YAML)."""
        import asyncio
        await asyncio.sleep(seconds)

    async def _delay_seconds(self, seconds: int) -> None:
        import asyncio
        await asyncio.sleep(seconds)

    # ── Wrapper pubblici (usati da services e switch) ─────────────────────────
    async def authorize_charging(self) -> None:
        await self._authorize()

    async def revoke_charging(self) -> None:
        await self._revoke()

    async def set_current_limit(self, current_a: float) -> None:
        await self._send_limit(current_a)

    # ── Helpers stato ──────────────────────────────────────────────────────────
    def _get_state(self, entity_id: str, default: str = "unknown") -> str:
        if not entity_id:
            return default
        state = self.hass.states.get(entity_id)
        return state.state if state else default

    def _get_float(self, entity_id: str, default: float = 0.0) -> float:
        if not entity_id:
            return default
        state = self.hass.states.get(entity_id)
        if not state or state.state in ("unknown", "unavailable", ""):
            return default
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return default

    def _get_valid_float(self, entity_id: str) -> tuple[float, bool]:
        """Restituisce un numero finito e la sua validità senza sollevare errori."""
        if not entity_id:
            return 0.0, False
        state = self.hass.states.get(entity_id)
        if not state or state.state.lower() in ("unknown", "unavailable", "none", ""):
            return 0.0, False
        try:
            value = float(state.state)
        except (ValueError, TypeError):
            return 0.0, False
        return (value, True) if math.isfinite(value) else (0.0, False)

    def _get_bool(self, entity_id: str, default: bool = False) -> bool:
        if not entity_id:
            return default
        state = self.hass.states.get(entity_id)
        return state.state in ("on", "true", "connected", "yes", "1") if state else default

    def _has_value(self, entity_id: str) -> bool:
        if not entity_id:
            return False
        state = self.hass.states.get(entity_id)
        return bool(state and state.state not in ("unknown", "unavailable", "none", ""))

    def _has_numeric_value(self, entity_id: str) -> bool:
        return self._get_valid_float(entity_id)[1]

    @staticmethod
    def _w_to_a(watts: float, voltage: float) -> float:
        return (watts / voltage) if voltage > 0 else 0.0
