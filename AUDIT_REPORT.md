# Audit di parità con le automazioni Home Assistant

## Esito

La versione ricevuta non era equivalente al set YAML e non era pronta per essere
installata senza correzioni. La versione 1.4.0 contenuta in questo repository
corregge i difetti bloccanti e integra le funzioni mancanti.

## Difetti bloccanti corretti

1. **Calcolo FV errato durante la carica**: veniva usato soltanto
   `(-rete + offset) / V`. Le YAML usano `corrente_attuale + delta`; vicino allo
   zero-scambio il vecchio codice poteva ridurre il target sotto 6 A o fermare
   una carica perfettamente sostenuta dal FV.
2. **Soft-stop FORZA assente**: il commento dichiarava la funzione, ma nessun
   ramo la eseguiva.
3. **Switch F3 ignorato**: `night_charging_enabled` non partecipava a nessuna
   condizione.
4. **Master Stop non resettato allo scollegamento**.
5. **Sync limite SOC auto non implementato**, nonostante l'entità fosse richiesta
   dalla configurazione.
6. **Sensore FV rotto**: leggeva `coordinator.pv_surplus_w`, attributo inesistente.
7. **Opzioni ignorate**: il coordinator leggeva solo `entry.data` e non
   `entry.options`.
8. **Notifiche e telemetria energia mancanti**.
9. **Select modalità incompleto**: esponeva opzioni che non eseguivano alcuna
   azione. È stato rimosso; la modalità resta un sensore diagnostico.
10. **Helper interni non persistenti**: target e switch sarebbero tornati ai
    default dopo un riavvio. Ora sono salvati nello storage di Home Assistant.

## Parità implementata

- Master Stop con mode 3, revoca e reset allo scollegamento.
- FORZA con ingresso anche durante una ricarica già attiva, load balancing,
  target veicolo e soft-stop 60 s + verifica 20 s.
- FV in tutte le fasce, corrente incrementale, isteresi temporale reale 30/60 s,
  limite 25 A e anti-spam 0,5 A.
- F3 sotto orizzonte con target utente, limite notturno e priorità al FV.
- Stop SOC assoluto e stop SOC utente in F3 senza FV.
- Igiene controller FV.
- Uscita intelligente da FORZA.
- Protezione `target utente ≤ target veicolo`.
- Sync bidirezionale ritardato HA → auto e immediato auto → integrazione.
- Publish dei tre topic `prism/energy_data/...`.
- Notifiche opzionali con conferma di 10 s all'avvio e 15 s allo stop.

## Scelte intenzionali rispetto alle incongruenze delle sorgenti

Le sorgenti non sono perfettamente concordi. Sono state privilegiate la tabella
`Logica.xlsx`, le descrizioni delle automazioni e le priorità dei diagrammi:

- In uscita da FORZA, se sono disponibili sia F3 sia FV, viene scelto il FV.
  Nel file YAML il ramo `continua_notturna` precede `continua_fv`, mentre il foglio
  di debug assegna correttamente la priorità al controller FV.
- In F3 il soft-stop usa il limite di potenza notturno. Nel template trigger YAML
  compare invece il limite contrattuale, nonostante la modulazione e l'helper
  dedicato usino il limite notturno.
- Attivare FORZA durante una carica FV forza esplicitamente mode 2. Il solo YAML
  poteva restare bloccato perché richiedeva contemporaneamente FORZA attiva e
  controller FV spento.
- Con un sensore critico non disponibile il controller non invia comandi. Le
  conversioni Jinja originali con `float(0)` potevano invece calcolare un margine
  artificiale.

## Verifiche eseguite

- compilazione sintattica di tutti i moduli Python;
- validazione JSON di manifest, stringhe e traduzioni;
- validazione YAML di `services.yaml`;
- cinque test di regressione sui calcoli FV, soglia 5,5 A, soglia 7 A,
  bilanciamento carichi e clamp tensione;
- controllo struttura repository HACS.

## Riferimenti tecnici

- Home Assistant Developer Docs – DataUpdateCoordinator:
  https://developers.home-assistant.io/docs/integration_fetching_data/
- Home Assistant Developer Docs – Options flow:
  https://developers.home-assistant.io/docs/core/integration/options_flow/
- Home Assistant – Working with states e conversioni Jinja:
  https://www.home-assistant.io/docs/templating/states/
- HACS – requisiti delle integrazioni:
  https://hacs.xyz/docs/publish/integration/
