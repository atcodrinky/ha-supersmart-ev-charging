# SuperSmart EV Charging per Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://www.hacs.xyz/)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.1%2B-blue.svg)](https://www.home-assistant.io/)

🇮🇹 Italiano · [🇬🇧 English](README.en.md)

SuperSmart EV Charging riunisce in un'unica integrazione Home Assistant la
gestione della ricarica da surplus fotovoltaico, la ricarica notturna, il
bilanciamento dinamico dei carichi e i comandi manuali della wallbox.

Nasce dalla logica delle automazioni per **Skoda Elroq/Enyaq e Silla Prism**, ma
può essere configurata per altri veicoli e wallbox che espongono entità e
comandi equivalenti.

> [!WARNING]
> Disattiva le vecchie automazioni EV prima di attivare l'integrazione: due
> controller contemporanei potrebbero inviare comandi concorrenti alla wallbox.

## Funzionalità

| Funzione | Descrizione |
|---|---|
| ☀️ **Surplus FV** | Modula la corrente usando l'energia solare disponibile e un offset di rete configurabile |
| 🌙 **Ricarica notturna** | Carica nella fascia off-peak scelta, per esempio F3, fino al target SOC utente |
| ⚡ **Load balancing** | Limita la ricarica in base alla potenza contrattuale e ai consumi dell'abitazione |
| 🔋 **Doppio target SOC** | Target utente per la notte e target veicolo per FV e Forza Ricarica |
| 🚀 **Forza Ricarica** | Avvia la ricarica indipendentemente da fascia tariffaria e surplus FV |
| 🛑 **Master Stop** | Revoca immediatamente l'autorizzazione e blocca ogni modalità di ricarica |
| 🔄 **Sincronizzazione SOC** | Sincronizza il target veicolo con il limite di carica dell'auto, se configurato |
| ⏱️ **Stime di ricarica** | Calcola tempo rimanente e ora di fine usando SOC, capacità utile e potenza reale |
| 📡 **MQTT configurabile** | Topic, payload e telemetria configurabili; autorizzazione e revoca possono usare button HA |
| 🛡️ **Protezioni operative** | Ingressi validati, isteresi FV, corrente minima, limiti massimi e anti-spam dei comandi |

## Compatibilità e requisiti

### Requisiti

- Home Assistant 2024.1 o successivo;
- HACS per l'installazione come repository personalizzato;
- un sensore del SOC del veicolo;
- sensori di potenza rete, produzione FV, stato e potenza wallbox;
- MQTT configurato in Home Assistant se si desidera il controllo automatico
  della modalità e della corrente della wallbox.

### Convenzioni richieste

- La potenza di rete deve essere **positiva in import** e **negativa in export**.
- Le potenze devono essere espresse in Watt.
- Lo stato wallbox deve esporre i valori `idle`, `waiting`, `pause` e
  `charging`.
- Per wallbox diverse da Silla Prism occorrono topic e payload equivalenti a
  quelli richiesti dalla configurazione MQTT.
- Un ingresso critico `unknown` o `unavailable` sospende l'invio di nuovi
  comandi fino al ritorno di dati validi.

## Installazione via HACS

1. Apri **HACS → Integrazioni**.
2. Dal menu ⋮ scegli **Repository personalizzati**.
3. Inserisci
   `https://github.com/atcodrinky/ha-supersmart-ev-charging` e seleziona la
   categoria **Integrazione**.
4. Installa SuperSmart EV Charging e riavvia Home Assistant.
5. Vai in **Impostazioni → Dispositivi e servizi → Aggiungi integrazione** e
   cerca **SuperSmart EV Charging**.

## Configurazione guidata

### Passaggio 1 — Parametri generali

| Campo | Descrizione | Valore iniziale |
|---|---|---|
| Potenza contrattuale | Limite disponibile dell'abitazione | 5700 W |
| Capacità utile batteria | Capacità realmente utilizzabile, modificabile nel tempo | 60 kWh |
| Target SOC utente | Obiettivo usato dalla ricarica notturna | 50% |
| Target SOC veicolo | Obiettivo usato da FV e Forza Ricarica | 80% |
| Fascia off-peak | Abilita la logica della ricarica notturna | Attiva |
| MQTT | Abilita il controllo della wallbox tramite MQTT | Attivo |
| Telemetria energia MQTT | Pubblica i dati energetici sui topic configurati | Attiva |

### Passaggio 2 — Entità Home Assistant

#### Entità obbligatorie

| Ruolo | Requisito | Esempio |
|---|---|---|
| SOC veicolo | Percentuale numerica | `sensor.elroq_percentuale_batteria` |
| Potenza rete | W, positivo import e negativo export | `sensor.rete_power` |
| Produzione FV | Potenza in W | `sensor.fotovoltaico_power` |
| Stato wallbox | `idle`, `waiting`, `pause`, `charging` | `sensor.silla_prism_stato_wallbox` |
| Potenza wallbox | Potenza in W; il segno viene ignorato | `sensor.wallbox_potenza` |
| Fascia tariffaria | Necessaria solo se la fascia off-peak è attiva | `sensor.pun_fascia_corrente` |

#### Entità opzionali

| Ruolo | Comportamento se non configurato |
|---|---|
| Veicolo collegato | Derivato dallo stato wallbox: `idle` indica scollegato |
| Limite di carica veicolo | Il target interno resta utilizzabile, senza sincronizzazione con l'auto |
| Potenza istantanea totale | Calcolata come potenza rete + produzione FV |
| Tensione wallbox | Usa 230 V; i valori letti sono limitati internamente a 180–260 V |
| Modalità/porta wallbox | Usata soltanto per migliorare la classificazione delle notifiche |
| Button autorizza/revoca | Usa come fallback i topic MQTT configurati |
| Servizio notifiche | Le notifiche non vengono inviate |

Se la fascia off-peak è attiva, seleziona anche il sensore tariffario e indica il
valore che identifica la fascia economica, per esempio `F3`.

### Passaggio 3 — Comandi MQTT

Il passaggio compare quando MQTT è abilitato.

| Funzione | Valore predefinito |
|---|---|
| Topic autorizza | `wallbox/command/authorize` |
| Topic revoca | `wallbox/command/revoke` |
| Topic limite corrente | `prism/1/command/set_current_limit` |
| Topic modalità | `prism/1/command/set_mode` |
| Payload Solare / Normale / Pausa | `1` / `2` / `3` |
| Telemetria rete | `prism/energy_data/power_grid` |
| Telemetria FV | `prism/energy_data/power_solar` |
| Telemetria casa | `prism/energy_data/power_house` |

Per Silla Prism è consigliato selezionare i button Home Assistant di
autorizzazione e revoca. I relativi topic MQTT sono pensati come fallback o per
wallbox differenti.

## Cosa crea in Home Assistant

L'integrazione appare nella scheda **Integrazioni** e crea un dispositivo
SuperSmart EV Charging con tutte le entità collegate. Non è necessario creare
manualmente helper `input_boolean`, `input_number`, `input_select` o
`input_datetime`.

I nomi visualizzati vengono tradotti nella lingua del backend Home Assistant al
momento della prima creazione. Gli entity ID possono quindi variare: verifica
quelli effettivi in **Impostazioni → Dispositivi e servizi → Entità**.

### Sensori

| Sensore | Descrizione |
|---|---|
| Modalità ricarica | `idle`, `pv_surplus`, `night`, `force` o `master_stop` |
| Surplus FV | Margine FV già corretto con l'offset import/export configurato |
| Target SOC attivo | Target veicolo in FV/Forza, target utente nella ricarica notturna |
| Tempo ricarica rimanente | Durata stimata alla potenza istantanea |
| Fine ricarica stimata | Timestamp con fuso orario, formattato da Home Assistant |
| Corrente target wallbox | Ultimo limite di corrente effettivamente inviato |
| Corrente effettiva wallbox | Stima ottenuta da potenza wallbox e tensione |

### Switch

| Switch | Funzione |
|---|---|
| Master Stop | Blocca la ricarica e revoca l'autorizzazione |
| Forza Ricarica | Carica fino al target SOC veicolo con bilanciamento contrattuale |
| Controller Solare Attivo | Abilita o disabilita la gestione del surplus FV |
| Ricarica Notturna F3 | Abilita o disabilita la modalità off-peak |

### Number

| Number | Intervallo | Valore iniziale |
|---|---:|---:|
| Target SOC utente | 10–100% | 50% |
| Target SOC veicolo | 20–100% | 80% |
| Potenza contrattuale | 1500–22000 W | 5700 W |
| Import rete permesso / offset FV | -500–+500 W | 200 W |
| Limite potenza notturna | 1000–22000 W | 3000 W |
| Capacità utile batteria | 1–250 kWh | 60 kWh |

Il target utente non può superare il target veicolo. Un offset FV negativo
richiede un margine di esportazione: per esempio `-200 W` mira a mantenere
circa 200 W ceduti alla rete.

La potenza contrattuale è il **tetto operativo totale di casa e wallbox**, non
un obiettivo di consumo garantito. La potenza reale può restare più bassa per i
consumi domestici, la tensione effettiva, i limiti interni della wallbox o la
corrente richiesta dall'auto.

### Azioni

```yaml
action: supersmart_ev_charging.authorize_charging
```

```yaml
action: supersmart_ev_charging.revoke_charging
```

```yaml
action: supersmart_ev_charging.set_charge_limit
data:
  current_a: 10
```

`current_a` accetta valori da 6 a 32 A.

## Schema del processo interno

```text
Cambio di stato o controllo periodico ogni 30 s
                         │
                         ▼
             Lettura e validazione ingressi
                         │
              dati critici non validi
                         └──────────────→ nessun nuovo comando
                         │ validi
                         ▼
Veicolo scollegato / wallbox idle? ── sì ─→ reset completo
                         │ no
                         ▼
Master Stop? ─────────────── sì ─→ Pausa + revoca autorizzazione
                         │ no
                         ▼
SOC ≥ target veicolo? ────── sì ─→ Stop assoluto + revoca
                         │ no
                         ▼
Forza Ricarica? ───────────── sì ─→ Normale + target veicolo
                         │ no        + bilanciamento contratto
                         ▼
Surplus FV utilizzabile? ──── sì ─→ Solare + target veicolo
                         │ no        + regolazione incrementale
                         ▼
Fascia off-peak + notte? ──── sì ─→ Normale + target utente
                         │ no        + limite potenza notturna
                         ▼
                        IDLE
```

Le decisioni sono serializzate per evitare comandi MQTT sovrapposti.

### Bilanciamento e calcolo FV

In Forza Ricarica e di notte, la corrente disponibile deriva dalla potenza
selezionata meno il consumo della casa:

```text
consumo_casa          = max(potenza_totale - potenza_wallbox, 0)
corrente_disponibile = (limite_potenza - consumo_casa) / tensione
```

In modalità FV il controller corregge la corrente già erogata:

```text
delta_A      = (-potenza_rete + offset_import) / tensione
corrente_ora = potenza_wallbox / tensione
target_A     = corrente_ora + delta_A
```

La ricarica FV parte con almeno 7 A disponibili per 30 secondi e si arresta se
il target scende sotto 5,5 A per 60 secondi. Il minimo operativo è 6 A; il
massimo è 25 A in FV e 32 A in Forza/notte. Un nuovo limite viene inviato solo
se varia di almeno 0,5 A.

### Target SOC e stime

- **Forza Ricarica e FV:** target SOC veicolo.
- **Ricarica notturna:** target SOC utente.

La stima del tempo usa:

```text
((target SOC - SOC attuale) / 100 × capacità utile kWh) / potenza wallbox kW
```

Il rendimento è assunto pari al 100%. Sotto 100 W, tempo rimanente e fine
stimata non sono disponibili.

Se viene configurata l'entità limite di carica dell'auto, una modifica fatta
dall'integrazione viene inviata al veicolo dopo 3 secondi, così l'auto ha tempo
di attivarsi. Una modifica proveniente dall'auto o dalla relativa app aggiorna
invece immediatamente il target dell'integrazione.

## Diagramma completo

![Diagramma del flusso SuperSmart EV Charging](assets/ev_energy_manager_flow.svg)

## Licenza

MIT License — vedi [LICENSE](LICENSE).
