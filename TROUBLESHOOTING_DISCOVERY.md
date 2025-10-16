# 🔧 Troubleshooting Discovery - deskHPSDR

## Problema: Discovery Non Trova la Radio

### Sintomo
```
deskHPSDR → Discover → Nessuna radio trovata
Log proxy: WARNING - Discovery from unauthenticated client
```

---

## ✅ Soluzione: Disabilita Autenticazione

### Perché?
deskHPSDR e altri client HPSDR standard **non supportano autenticazione JWT**.
Inviano pacchetti UDP discovery "nudi" senza token.

### Fix Rapido

Modifica `config/config.yaml`:

```yaml
security:
  require_authentication: false  # ← Cambia da true a false
  allow_anonymous_discovery: true  # ← Cambia da false a true
```

### Riavvia il Proxy
```bash
# Ferma proxy se in esecuzione (Ctrl+C)
# Poi riavvia:
cd /Users/macbookair/Documents/udp-gateway
source venv/bin/activate
python3 main.py -v
```

### Prova di Nuovo in deskHPSDR
- Setup → Radio → Protocol 1
- Indirizzo: `localhost` (se proxy sullo stesso PC)
- Porta: `1024`
- Discover

---

## 📋 Log Corretto

### Prima (NON funziona) - Autenticazione richiesta
```
WARNING - Discovery from unauthenticated client 127.0.0.1:53647
```

### Prima (NON funziona) - Nessuna sessione creata
```
INFO - Discovery from 127.0.0.1:53647
# Nessun log di forwarding - pacchetto droppato silenziosamente
```

### Dopo (FUNZIONA)
```
INFO - Discovery from 127.0.0.1:53647
DEBUG - Created anonymous session for 127.0.0.1:53647
INFO - Assigned radio IO7T Radio to client 127.0.0.1:53647
INFO - Forwarding discovery to radio io7t.ddns.net:1024
DEBUG - Forwarded XX bytes from 127.0.0.1:53647 to radio
```

---

## 🔍 Altri Problemi di Discovery

### 1. Radio Non Risponde

**Sintomo**: Discovery inviato ma nessuna risposta dalla radio

**Verifica**:
```bash
# Test connettività
ping io7t.ddns.net

# Se non risponde al ping:
# - Radio spenta?
# - DDNS non aggiornato?
# - Firewall blocca ICMP?
```

**Log Atteso**:
```
INFO - Discovery from 127.0.0.1:XXXX
INFO - Forwarding discovery to radio
(... attesa risposta radio ...)
INFO - Forwarding from radio to client  ← Dovrebbe apparire
```

### 2. Porta Sbagliata

**Sintomo**: Connection refused o timeout

**Verifica**:
```bash
# In config.yaml, verifica:
radios:
  - port: 1024  # ← Porta corretta della TUA radio

proxy:
  listen_port: 1024  # ← Porta dove il proxy ascolta
```

**Fix**: Assicurati che:
- Proxy ascolti su `1024` (o altra porta libera)
- Radio sia configurata con la sua porta corretta
- deskHPSDR punti alla porta del PROXY (non della radio)

### 3. Firewall Blocca UDP

**Sintomo**: Pacchetti non arrivano

**macOS Firewall**:
```bash
# Verifica se firewall blocca Python
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate

# Permetti Python (se necessario)
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /usr/local/bin/python3
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --unblockapp /usr/local/bin/python3
```

**Router/Firewall Esterno**:
- Porta UDP 1024 deve essere aperta in ENTRAMBE le direzioni
- NAT/Port forwarding configurato se necessario

### 4. Radio Già in Uso

**Sintomo**: Radio non risponde o risponde parzialmente

**Cause**:
- Altro client SDR già connesso
- Altra istanza del proxy in esecuzione
- Software SDR nativo della radio attivo

**Fix**:
```bash
# Chiudi tutti i client SDR
# Verifica nessun altro processo sulla porta:
lsof -i :1024

# Se trovi altri processi, terminali:
kill -9 <PID>
```

### 5. Indirizzo Proxy Sbagliato in deskHPSDR

**Sintomo**: Timeout o connessione rifiutata

**Setup Corretto**:

| Scenario | Indirizzo in deskHPSDR | Porta |
|----------|------------------------|-------|
| Proxy sullo stesso PC | `localhost` o `127.0.0.1` | `1024` |
| Proxy su altro PC (LAN) | IP del PC proxy (es. `192.168.1.50`) | `1024` |
| Proxy remoto | IP pubblico o DDNS del proxy | `1024` |

**❌ SBAGLIATO**: Usare indirizzo della radio
**✅ CORRETTO**: Usare indirizzo del PROXY

### 6. Loop Infinito di Discovery

**Sintomo**: Log mostra discovery ripetuti in rapida successione dalla stessa sorgente
```
INFO - Discovery from 93.44.225.156:1024
INFO - Forwarding discovery to radio
INFO - Discovery from 93.44.225.156:1024
INFO - Forwarding discovery to radio
...continua all'infinito...
```

**Causa**: Il proxy riceve i pacchetti che lui stesso invia alla radio, creando un loop. Questo accade quando proxy e radio usano la stessa porta (1024).

**Soluzione**:
1. **AUTOMATICA (fix v0.2.0)**: Il proxy ora riconosce i pacchetti provenienti dalla radio e li inoltra al client invece di riprocessarli
2. **MANUALE (alternativa)**: Cambia la porta del proxy in config.yaml:
   ```yaml
   proxy:
     listen_port: 10240  # Usa porta diversa da 1024
   ```
   Poi in deskHPSDR usa porta `10240` invece di `1024`

**Verifica Fix**:
- Con fix automatico: Log dovrebbe mostrare `Received response from radio` invece di loop
- Con porta diversa: Nessun loop perché proxy e radio non condividono la stessa porta

### 7. Discovery Broadcast Non Funziona

**Sintomo**: deskHPSDR invia discovery ma proxy non riceve

**Debug**:
```bash
# Mentre il proxy è in esecuzione, in altra terminal:
sudo tcpdump -i any -n udp port 1024

# Dovresti vedere:
# - Pacchetti IN da 127.0.0.1 (deskHPSDR)
# - Pacchetti OUT verso radio
```

**Se non vedi pacchetti IN**:
- deskHPSDR configurato con porta sbagliata
- Proxy non in ascolto (verifica con `lsof -i :1024`)
- Firewall locale blocca

---

## 🎯 Checklist Rapida

Quando discovery non funziona, verifica nell'ordine:

- [ ] Proxy in esecuzione (`python3 main.py -v`)
- [ ] Autenticazione disabilitata in config.yaml
- [ ] deskHPSDR punta a `localhost:1024` (non alla radio)
- [ ] Log proxy mostra "Discovery from..." (non WARNING)
- [ ] Radio raggiungibile (`ping io7t.ddns.net`)
- [ ] Nessun altro client usa la radio
- [ ] Firewall permette UDP 1024
- [ ] Porta corretta in config.yaml

---

## 📊 Test di Connettività Completo

### Test 1: Proxy in Ascolto
```bash
lsof -i :1024
# Dovresti vedere: Python3 ... UDP *:1024
```

### Test 2: Radio Raggiungibile
```bash
ping -c 4 io7t.ddns.net
# Dovresti vedere: 4 packets transmitted, 4 received
```

### Test 3: Porta Radio Aperta (se possibile)
```bash
nc -zvu io7t.ddns.net 1024
# O usa nmap: nmap -sU -p 1024 io7t.ddns.net
```

### Test 4: Discovery Manuale
```bash
# Invia discovery packet al proxy:
echo -ne '\xef\xfe\x02' | nc -u localhost 1024

# Nel log del proxy dovresti vedere:
# INFO - Discovery from 127.0.0.1:XXXX
```

---

## ⚙️ Configurazione Ottimale per deskHPSDR

### config.yaml
```yaml
proxy:
  listen_address: "0.0.0.0"
  listen_port: 1024

security:
  require_authentication: false  # ← IMPORTANTE!
  allow_anonymous_discovery: true  # ← IMPORTANTE!

radios:
  - name: "My Radio"
    ip: "io7t.ddns.net"  # ← Il tuo DDNS
    port: 1024
    enabled: true
```

### deskHPSDR Setup
```
Protocol: Protocol 1
Radio Address: localhost (o IP del Mac con proxy)
Port: 1024
```

---

## 🔐 Nota Sicurezza

### Autenticazione Disabilitata

**OK per**:
- ✅ Testing locale
- ✅ Rete domestica privata
- ✅ Uso personale su LAN

**NON OK per**:
- ❌ Internet pubblico senza VPN
- ❌ Reti condivise/pubbliche
- ❌ Accesso multi-utente

### Alternative Sicure

Se devi esporre su internet:

1. **VPN** (consigliato)
   - Wireguard
   - OpenVPN
   - Tailscale

2. **SSH Tunnel**
   ```bash
   ssh -L 1024:localhost:1024 user@proxy-server
   ```

3. **Implementare Auth in deskHPSDR** (avanzato)
   - Modificare deskHPSDR per inviare token JWT
   - Non standard, richiede sviluppo custom

---

## 📚 Riferimenti

- **Config Example**: `config/config.yaml.example`
- **Full Testing Guide**: `docs/TESTING.md`
- **Architecture**: `docs/ARCHITECTURE.md`
- **Quick Start**: `QUICK_TEST_GUIDE.md`

---

## 🆘 Ancora Problemi?

1. **Abilita debug completo**:
   ```yaml
   logging:
     level: "DEBUG"  # In config.yaml
   ```

2. **Cattura traffico**:
   ```bash
   sudo tcpdump -i any -n -X udp port 1024
   ```

3. **Controlla log dettagliato**:
   ```bash
   python3 main.py -v 2>&1 | tee proxy_debug.log
   ```

4. **GitHub Issues**:
   https://github.com/francescocozzi/hpsdr-udp-proxy/issues

---

**Ultima revisione**: 16 Ottobre 2025
**Problema comune**: Discovery fallisce con auth abilitata
**Soluzione**: Disabilita `require_authentication` in config.yaml
