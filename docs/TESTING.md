# Guida al Testing - HPSDR UDP Proxy

Questa guida ti aiuterà a testare il proxy HPSDR in modo progressivo, dai test base ai test end-to-end con hardware reale.

## 📋 Indice

1. [Preparazione](#preparazione)
2. [Test Componenti Individuali](#test-componenti-individuali)
3. [Test End-to-End](#test-end-to-end)
4. [Test con Hardware Reale](#test-con-hardware-reale)
5. [Troubleshooting](#troubleshooting)

---

## Preparazione

### 1. Setup Ambiente

```bash
# Assicurati di essere nella directory del progetto
cd /Users/macbookair/Documents/udp-gateway

# Attiva ambiente virtuale
source venv/bin/activate

# Verifica dipendenze
pip install -r requirements.txt
```

### 2. Configurazione

```bash
# Copia configurazione se non l'hai già fatto
cp config/config.yaml.example config/config.yaml

# Modifica config.yaml con le tue impostazioni
nano config/config.yaml
```

**Configurazione minima richiesta:**

```yaml
database:
  type: "sqlite"  # Usa SQLite per i test
  sqlite_path: "database/test_proxy.db"

auth:
  jwt_secret: "your-test-secret-key-here"  # GENERA UNA CHIAVE!

radios:
  - name: "Test Radio"
    ip: "192.168.1.100"  # IP della tua radio
    port: 1024
    mac: "00:1C:C0:A2:12:34"  # MAC della tua radio
    enabled: true

proxy:
  listen_address: "0.0.0.0"
  listen_port: 1024
```

**Genera JWT secret sicuro:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Inizializza Database

```bash
# Crea il database e tabelle
python scripts/init_db.py

# Dovresti vedere:
# ✓ Database creato
# ✓ Tabelle create
# ✓ Utente admin creato
```

---

## Test Componenti Individuali

### Test 1: Database Manager

Testa le operazioni database (CRUD, connessioni, etc.)

```bash
python tests/test_database.py
```

**Output atteso:**
```
======================================================================
TEST DATABASE MANAGER
======================================================================

1. Caricamento configurazione...
   ✓ Configurazione caricata

2. Connessione al database...
   ✓ Connessione stabilita

3. Health check database...
   ✓ Database sano e funzionante

4. Test creazione utente...
   ✓ Utente creato con ID: 2

5. Test recupero utente per username...
   ✓ Utente recuperato: test_user
     Email: test@example.com
     Ruolo: user

[... più test ...]

✓ TUTTI I TEST COMPLETATI CON SUCCESSO
```

**Cosa viene testato:**
- ✅ Connessione database
- ✅ Health check
- ✅ Creazione utenti
- ✅ Recupero utenti (per username, per ID)
- ✅ Creazione radio
- ✅ Creazione sessioni
- ✅ Activity logging

**Se fallisce:**
- Verifica che `config/config.yaml` esista
- Verifica path database in config
- Verifica che il database sia stato inizializzato

---

### Test 2: Authentication Manager

Testa JWT, password hashing, login, account lockout

```bash
python tests/test_auth.py
```

**Output atteso:**
```
======================================================================
TEST AUTHENTICATION MANAGER
======================================================================

1. Setup database e auth manager...
   ✓ Database e Auth Manager inizializzati

2. Test password hashing...
   ✓ Password hashata: $2b$12$...
   ✓ Verifica password corretta
   ✓ Password errata correttamente rifiutata

3. Test creazione utente con password...
   ✓ Utente creato con ID: 3

4. Test login con credenziali corrette...
   ✓ Login riuscito!
     User: auth_test_user
     Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

[... più test ...]

✓ TUTTI I TEST DI AUTENTICAZIONE COMPLETATI
```

**Cosa viene testato:**
- ✅ Password hashing con bcrypt
- ✅ Verifica password
- ✅ Creazione utente con password
- ✅ Login con credenziali
- ✅ Generazione token JWT
- ✅ Validazione token
- ✅ Cambio password
- ✅ Refresh token
- ✅ Account lockout dopo tentativi falliti

**Se fallisce:**
- Verifica che `jwt_secret` sia configurato
- Verifica che il database sia inizializzato
- Controlla i log per errori specifici

---

### Test 3: Packet Handler

Testa il parsing dei pacchetti HPSDR

```bash
python tests/test_packets.py
```

**Output atteso:**
```
======================================================================
TEST HPSDR PACKET HANDLER
======================================================================

1. Inizializzazione PacketHandler...
   ✓ PacketHandler inizializzato

2. Test Discovery Request packet...
   ✓ Tipo pacchetto: DISCOVERY
     È response: False
     MAC address: None
   ✓ Correttamente identificato come REQUEST

3. Test Discovery Response packet...
   ✓ Tipo pacchetto: DISCOVERY
     È response: True
     MAC address: 00:1c:c0:a2:12:34
   ✓ Correttamente identificato come RESPONSE con MAC

[... più test ...]

✓ TUTTI I TEST DEL PACKET HANDLER COMPLETATI
```

**Cosa viene testato:**
- ✅ Parsing discovery request
- ✅ Parsing discovery response
- ✅ Parsing data packets
- ✅ Identificazione pacchetti invalidi
- ✅ Generazione discovery packets
- ✅ Statistiche parser

**Se fallisce:**
- Il packet handler è stato testato estensivamente, errori indicano problemi nel codice
- Verifica che i test siano aggiornati con l'implementazione

---

## Test End-to-End

### Test 4: Avvio del Proxy

Test base: avvia il proxy e verifica che tutto si inizializzi correttamente

```bash
# Avvia in modalità verbose
python main.py -v
```

**Output atteso:**
```
======================================================================
HPSDR UDP Proxy/Gateway v0.2.0-alpha Starting...
======================================================================
Initializing components...
✓ Packet handler initialized
Connecting to database...
✓ Database connected
✓ Authentication manager initialized
✓ Session manager started
✓ UDP listener started on 0.0.0.0:1024
✓ Packet forwarder started
Configuration: 1 radio(s), auth=required
  - Radio: Test Radio (192.168.1.100:1024)
======================================================================
All components initialized successfully!
======================================================================
🚀 Proxy is now running. Press Ctrl+C to stop.
```

**Cosa viene testato:**
- ✅ Caricamento configurazione
- ✅ Inizializzazione database
- ✅ Inizializzazione auth manager
- ✅ Inizializzazione session manager
- ✅ Avvio UDP listener
- ✅ Avvio packet forwarder

**Se fallisce:**
- Leggi il messaggio di errore specifico
- Controlla config.yaml
- Verifica che la porta 1024 non sia già in uso: `lsof -i :1024`
- Verifica permessi firewall

**Per fermare:**
Premi `Ctrl+C` per graceful shutdown

---

### Test 5: Test Discovery Locale

Invia un discovery packet al proxy da localhost

**Opzione A: Con netcat (nc)**

Terminal 1 - Avvia il proxy:
```bash
python main.py -v
```

Terminal 2 - Invia discovery:
```bash
# Crea discovery packet e invialo
echo -ne '\xef\xfe\x02' | cat - <(dd if=/dev/zero bs=60 count=1 2>/dev/null) | nc -u localhost 1024
```

**Output atteso nel Terminal 1:**
```
Discovery from 127.0.0.1:XXXXX
```

**Opzione B: Script Python**

Crea `tests/test_discovery_client.py`:

```python
import socket

# Crea socket UDP
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Discovery request packet
discovery = b'\xef\xfe\x02' + bytes(60)

# Invia al proxy
sock.sendto(discovery, ('localhost', 1024))
print("Discovery packet inviato!")

# Attendi response (timeout 2 sec)
sock.settimeout(2.0)
try:
    data, addr = sock.recvfrom(1024)
    print(f"Response ricevuta da {addr}: {len(data)} bytes")
except socket.timeout:
    print("Nessuna response (timeout)")

sock.close()
```

Esegui:
```bash
python tests/test_discovery_client.py
```

---

## Test con Hardware Reale

### Prerequisiti Hardware

- **Radio HPSDR**: Hermes Lite 2, Metis, Hermes, o compatibile
- **Client SDR**: deskHPSDR, PowerSDR, Spark SDR, o compatibile
- **Network**: Tutti i dispositivi sulla stessa rete o con routing appropriato

### Setup di Rete

```
[Client PC]  <-----> [Proxy PC] <-----> [Radio HPSDR]
192.168.1.10       192.168.1.50      192.168.1.100
```

**Configurazione consigliata:**
1. Client su PC/Mac con deskHPSDR
2. Proxy su Linux server o Raspberry Pi
3. Radio (Hermes Lite 2) sulla rete

### Configurazione Radio

In `config/config.yaml`:

```yaml
radios:
  - name: "My Hermes Lite 2"
    ip: "192.168.1.100"  # IP REALE della tua radio
    port: 1024
    mac: "XX:XX:XX:XX:XX:XX"  # MAC REALE della tua radio
    enabled: true
```

**Come trovare MAC address della radio:**
```bash
# Avvia il proxy e manda un discovery broadcast
# Il proxy loggerà il MAC quando la radio risponde

# Oppure usa Wireshark per catturare discovery response
```

### Test 1: Avvio Proxy

```bash
# Sul PC dove gira il proxy
python main.py -v
```

Dovresti vedere:
```
✓ UDP listener started on 0.0.0.0:1024
  - Radio: My Hermes Lite 2 (192.168.1.100:1024)
🚀 Proxy is now running
```

### Test 2: Configurazione Client deskHPSDR

1. **Avvia deskHPSDR**

2. **Setup → Radio → Protocol 1**

3. **Imposta indirizzo radio:**
   - Invece dell'IP della radio, usa l'IP del PROXY
   - Esempio: `192.168.1.50` (IP del PC dove gira il proxy)
   - Porta: `1024`

4. **Clicca "Discover"**

**Cosa dovrebbe succedere:**

Sul proxy vedrai:
```
Discovery from 192.168.1.10:51234
Assigning radio My Hermes Lite 2 to client
Forwarding discovery to radio 192.168.1.100:1024
```

Sul client deskHPSDR:
- Dovrebbe trovare la radio come se fosse diretta
- Nome/modello dovrebbe corrispondere

5. **Clicca "Start"**

Il proxy dovrebbe loggare:
```
Data packet from 192.168.1.10:51234
Forwarding to radio 192.168.1.100:1024
Forwarding from radio to client 192.168.1.10:51234
```

6. **Verifica Audio/SDR**
   - Dovresti ricevere audio dalla radio
   - Puoi cambiare frequenza
   - PTT dovrebbe funzionare

### Test 3: Monitoring

**Terminale proxy** - Dovresti vedere:
```
Active sessions: 1
Packets forwarded: XXXXX
Latency: ~3-5ms
```

**Premi Ctrl+C per fermare** - Vedrai statistiche finali:
```
Final Statistics:
  Packets processed: 125847
    - Discovery: 2
    - Data: 125845
  UDP: 125847 received, 518MB bytes
  Forwarded: 62924 to radio, 62923 to client
  Sessions: 1 total, 0 expired
```

---

## Troubleshooting

### Problema: Porta 1024 già in uso

**Errore:**
```
OSError: [Errno 48] Address already in use
```

**Soluzione:**
```bash
# Trova processo che usa porta 1024
lsof -i :1024

# Termina processo (se è sicuro)
kill -9 <PID>

# Oppure usa altra porta in config.yaml
proxy:
  listen_port: 1025
```

### Problema: Permission denied porta 1024

**Errore:**
```
PermissionError: [Errno 13] Permission denied
```

**Soluzione (porte < 1024 richiedono root):**
```bash
# Opzione 1: Usa porta > 1024
proxy:
  listen_port: 10240

# Opzione 2: Esegui con sudo (NON raccomandato per produzione)
sudo python main.py

# Opzione 3: Capability Linux
sudo setcap 'cap_net_bind_service=+ep' $(which python3)
```

### Problema: Database locked

**Errore:**
```
sqlite3.OperationalError: database is locked
```

**Soluzione:**
```bash
# Assicurati che solo un'istanza del proxy sia in esecuzione
pkill -f "python main.py"

# Rimuovi lock file se presente
rm database/test_proxy.db-journal

# Riavvia proxy
python main.py -v
```

### Problema: Radio non risponde

**Sintomi:**
- Discovery inviato ma nessuna response
- Timeout nella comunicazione

**Checklist:**
1. **Verifica IP radio in config.yaml**
   ```bash
   ping 192.168.1.100
   ```

2. **Verifica che la radio sia accesa e connessa**

3. **Verifica firewall** (sia sul proxy che sulla radio)
   ```bash
   # Disabilita temporaneamente firewall per test
   sudo ufw disable
   ```

4. **Verifica con Wireshark:**
   ```bash
   # Cattura pacchetti UDP porta 1024
   sudo tcpdump -i any -n udp port 1024
   ```

5. **Verifica che la radio non sia già in uso**
   - Chiudi altri client SDR
   - Resetta la radio

### Problema: Client non trova radio

**Sintomi:**
- deskHPSDR non trova radio tramite proxy
- Discovery timeout

**Debug:**

1. **Verifica che il proxy riceva il discovery:**
   ```bash
   # Nel log del proxy dovresti vedere:
   Discovery from <CLIENT_IP>:<PORT>
   ```

2. **Verifica forwarding al radio:**
   ```bash
   # Dovresti vedere:
   Forwarding discovery to radio 192.168.1.100:1024
   ```

3. **Verifica response dalla radio:**
   ```bash
   # Con tcpdump sul proxy:
   sudo tcpdump -i any -n 'udp and src host 192.168.1.100'
   ```

4. **Test diretto senza proxy:**
   - Configura deskHPSDR per connettersi direttamente alla radio
   - Se funziona → problema nel proxy
   - Se non funziona → problema nella rete/radio

### Problema: Alta latenza

**Sintomi:**
- Audio choppy
- Latenza > 50ms

**Soluzioni:**

1. **Verifica rete:**
   ```bash
   ping -c 100 192.168.1.100
   ```

2. **Verifica CPU proxy:**
   ```bash
   top -p $(pgrep -f "python main.py")
   ```

3. **Ottimizza config:**
   ```yaml
   proxy:
     buffer_size: 2048  # Aumenta se necessario

   performance:
     stats_enabled: false  # Disabilita stats per ridurre overhead
   ```

4. **Usa rete cablata** invece di WiFi

### Problema: Autenticazione fallisce

**Sintomi:**
- Login non funziona
- Token invalido

**Debug:**

1. **Verifica JWT secret in config:**
   ```yaml
   auth:
     jwt_secret: "deve-essere-configurato"
   ```

2. **Reset utente admin:**
   ```bash
   python scripts/init_db.py --force
   ```

3. **Test autenticazione manualmente:**
   ```bash
   python tests/test_auth.py
   ```

---

## Metriche di Performance Attese

### Normale Operazione

- **Latenza aggiunta**: < 5-10ms
- **Throughput**: > 1000 pacchetti/secondo
- **Uso CPU**: 5-15%
- **Uso RAM**: 50-100 MB
- **Packet loss**: < 0.1%

### Come Misurare

```bash
# Durante l'operazione, in altra terminal:
watch -n 1 'lsof -i :1024 | tail -n +2 | wc -l'  # Connessioni attive

# CPU usage
top -p $(pgrep -f "python main.py")

# Network usage
iftop -i <interface>
```

---

## Log Analysis

### Dove trovare i log

```bash
# Log file (se configurato)
tail -f logs/proxy.log

# Output console
python main.py -v  # Verbose mode
```

### Log importanti da cercare

**Operazione normale:**
```
✓ Database connected
✓ UDP listener started
Discovery from <IP>:<PORT>
Active sessions: N
```

**Errori comuni:**
```
ERROR - Connection refused
ERROR - Permission denied
ERROR - Database locked
WARNING - Session timeout
WARNING - Invalid token
```

### Aumentare verbosità

```yaml
# In config.yaml
logging:
  level: "DEBUG"  # Invece di INFO
```

---

## Prossimi Passi

Dopo aver completato questi test:

1. **Performance Testing**
   - Stress test con client multipli
   - Benchmark latency
   - Long-running stability test

2. **Unit Testing**
   - Scrivi test pytest per componenti critici
   - Code coverage

3. **Production Deployment**
   - Setup systemd service
   - Monitoring con Prometheus
   - Backup automatici database

---

## Supporto

Per problemi o domande:

- **GitHub Issues**: https://github.com/francescocozzi/hpsdr-udp-proxy/issues
- **Documentation**: `docs/` folder
- **Logs**: Allega sempre i log quando riporti problemi

---

**Ultima revisione**: 16 Ottobre 2025
**Versione guida**: 1.0
