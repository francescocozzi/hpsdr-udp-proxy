# 🧪 Guida Rapida al Testing - HPSDR UDP Proxy

**Per iniziare subito con i test pratici!**

---

## ⚡ Quick Start (5 minuti)

### 1. Preparazione Base
```bash
cd /Users/macbookair/Documents/udp-gateway
source venv/bin/activate
```

### 2. Verifica Configurazione
```bash
# Controlla che esista
cat config/config.yaml

# Se manca, crealo
cp config/config.yaml.example config/config.yaml
nano config/config.yaml
```

**IMPORTANTE**: Genera un JWT secret sicuro:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
Copia l'output in `config.yaml` alla voce `auth.jwt_secret`

### 3. Inizializza Database
```bash
python scripts/init_db.py
```

Dovresti vedere:
```
✓ Database creato
✓ Tabelle create
✓ Utente admin creato (username: admin, password: admin123)
```

---

## 🎯 Test Rapidi (Ordine Consigliato)

### Test 1: Database (2 minuti)
```bash
python tests/test_database.py
```

**✅ Se passa**: Database funziona correttamente
**❌ Se fallisce**: Controlla che database sia inizializzato

---

### Test 2: Autenticazione (2 minuti)
```bash
python tests/test_auth.py
```

**✅ Se passa**: JWT e password hashing funzionano
**❌ Se fallisce**: Verifica `jwt_secret` in config.yaml

---

### Test 3: Packet Handler (1 minuto)
```bash
python tests/test_packets.py
```

**✅ Se passa**: Parsing HPSDR funziona
**❌ Se fallisce**: Raramente fallisce, indica bug nel codice

---

### Test 4: Avvio Proxy (Test End-to-End Base)
```bash
python main.py -v
```

**Dovresti vedere:**
```
======================================================================
HPSDR UDP Proxy/Gateway v0.2.0-alpha Starting...
======================================================================
Initializing components...
✓ Packet handler initialized
✓ Database connected
✓ Authentication manager initialized
✓ Session manager started
✓ UDP listener started on 0.0.0.0:1024
✓ Packet forwarder started
======================================================================
All components initialized successfully!
======================================================================
🚀 Proxy is now running. Press Ctrl+C to stop.
```

**✅ Se funziona**: Il proxy è operativo!
**❌ Se fallisce**: Vedi sezione Troubleshooting sotto

**Per fermare**: Premi `Ctrl+C`

---

## 🔧 Test con Hardware Reale

### Prerequisiti
- Radio HPSDR (Hermes Lite 2, Metis, etc.)
- Client SDR (deskHPSDR, PowerSDR, etc.)
- Stessa rete o routing configurato

### Setup Rapido

**1. Configura IP della tua radio in `config/config.yaml`:**
```yaml
radios:
  - name: "My Radio"
    ip: "192.168.1.100"  # <- IP REALE della tua radio
    port: 1024
    mac: "00:1C:C0:A2:12:34"  # <- MAC REALE della tua radio
    enabled: true
```

**2. Avvia il proxy:**
```bash
python main.py -v
```

**3. Configura deskHPSDR:**
- Setup → Radio → Protocol 1
- **Indirizzo**: IP del PC dove gira il proxy (NON la radio!)
- **Porta**: 1024
- Clicca "Discover"

**4. Dovresti vedere nel proxy:**
```
Discovery from <CLIENT_IP>:<PORT>
Assigning radio My Radio to client
Forwarding discovery to radio 192.168.1.100:1024
```

**5. Nel client:**
- La radio dovrebbe essere trovata
- Clicca "Start"
- Dovresti ricevere audio/SDR

---

## ⚠️ Problemi Comuni e Soluzioni Rapide

### Porta 1024 già in uso
```bash
# Trova cosa usa la porta
lsof -i :1024

# Termina processo (se sicuro)
kill -9 <PID>

# Oppure usa altra porta in config.yaml
```

### Permission denied (porta < 1024)
```bash
# Soluzione: Usa porta > 1024
nano config/config.yaml
# Cambia listen_port: 10240

# Aggiorna client per usare porta 10240
```

### Database locked
```bash
# Assicurati che non ci siano altri processi
pkill -f "python main.py"

# Rimuovi lock
rm database/test_proxy.db-journal

# Riavvia
python main.py -v
```

### Radio non risponde
```bash
# Verifica connettività
ping 192.168.1.100

# Verifica che radio sia accesa e connessa
# Verifica IP in config.yaml
# Chiudi altri client SDR che usano la radio
```

### Config file not found
```bash
# Crea da esempio
cp config/config.yaml.example config/config.yaml

# Modifica con tue impostazioni
nano config/config.yaml
```

---

## 📊 Metriche Attese (Operazione Normale)

- **Latenza aggiunta dal proxy**: < 5-10ms
- **Throughput**: > 1000 pacchetti/sec
- **CPU Usage**: 5-15%
- **RAM Usage**: 50-100 MB
- **Packet Loss**: < 0.1%

---

## 📚 Documentazione Completa

### Test Dettagliati
👉 **`docs/TESTING.md`** - Guida completa con troubleshooting avanzato

### Test Scripts
👉 **`tests/README.md`** - Reference per script di test

### Architettura
👉 **`docs/ARCHITECTURE.md`** - Architettura tecnica del sistema

### Installazione
👉 **`docs/INSTALLATION.md`** - Guida installazione dettagliata

---

## 🆘 Supporto

### Problemi durante i test?

1. **Controlla i log** - Modalità verbose: `python main.py -v`
2. **Leggi TESTING.md** - Troubleshooting dettagliato
3. **GitHub Issues** - https://github.com/francescocozzi/hpsdr-udp-proxy/issues

### Checklist Debug

- [ ] Config.yaml esiste e è valido
- [ ] JWT secret configurato
- [ ] Database inizializzato (`python scripts/init_db.py`)
- [ ] Porta non in uso da altri processi
- [ ] Firewall permette UDP porta 1024
- [ ] IP radio corretto in config
- [ ] Radio accesa e connessa alla rete

---

## ✅ Cosa Fare Dopo i Test

Se tutti i test passano:

1. **Test con hardware reale** (se disponibile)
2. **Performance testing** (stress test, latency benchmark)
3. **Production deployment** (systemd service, monitoring)
4. **Backup database** (setup automatico)

---

## 🎯 Test Success Checklist

Tutti questi devono passare:

- [ ] `python tests/test_database.py` → ✓ SUCCESS
- [ ] `python tests/test_auth.py` → ✓ SUCCESS
- [ ] `python tests/test_packets.py` → ✓ SUCCESS
- [ ] `python main.py -v` → Si avvia senza errori
- [ ] Proxy riceve discovery packets
- [ ] (Opzionale) Client SDR si connette tramite proxy
- [ ] (Opzionale) Audio/SDR funziona end-to-end

---

**Versione**: 1.0
**Data**: 16 Ottobre 2025
**License**: MIT

**Buon testing! 🚀**
