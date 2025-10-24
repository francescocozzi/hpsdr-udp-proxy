# Configuration System - Deployment Guide

## Overview

Il nuovo sistema di configurazione permette di gestire tutte le impostazioni del VPN Gateway attraverso:
1. File `config.ini`
2. Variabili d'ambiente (override il file config)
3. Valori di default (fallback)

## File Modificati

### Nuovi File
- `src/config.py` - Modulo gestione configurazione
- `config.example.ini` - Template configurazione
- `test_config.sh` - Script di test
- `docs/CONFIG_DEPLOYMENT_GUIDE.md` - Questa guida

### File Modificati
- `src/api/main.py` - Usa il nuovo sistema di configurazione

## Step 1: Trasferimento File sul Server Ubuntu

Sul tuo **server Ubuntu** (192.168.1.229):

```bash
# Naviga nella directory del progetto
cd ~/hpsdr-udp-proxy

# Assicurati di avere git configurato
git status

# Opzione A: Se hai git, pull delle modifiche
git pull origin main

# Opzione B: Se non hai git, copia i file manualmente
# (usa scp/sftp dal tuo Mac)
```

### Copia File da Mac a Ubuntu (se non usi git)

Sul tuo **Mac**:

```bash
# Copia i nuovi file sul server Ubuntu
scp -r ~/Documents/udp-gateway/src/config.py francoz@192.168.1.229:~/hpsdr-udp-proxy/src/
scp -r ~/Documents/udp-gateway/config.example.ini francoz@192.168.1.229:~/hpsdr-udp-proxy/
scp -r ~/Documents/udp-gateway/test_config.sh francoz@192.168.1.229:~/hpsdr-udp-proxy/
scp -r ~/Documents/udp-gateway/src/api/main.py francoz@192.168.1.229:~/hpsdr-udp-proxy/src/api/

# Rendi eseguibile lo script di test
ssh francoz@192.168.1.229 "chmod +x ~/hpsdr-udp-proxy/test_config.sh"
```

## Step 2: Creazione File config.ini

Sul **server Ubuntu**:

```bash
cd ~/hpsdr-udp-proxy

# Crea config.ini dal template
cp config.example.ini config.ini

# Modifica con le tue impostazioni
nano config.ini
```

### Impostazioni Consigliate per il Tuo Server

Modifica il file `config.ini` con questi valori:

```ini
[vpn]
# VPN Server Configuration
public_endpoint = 192.168.1.229    # <--- CAMBIA QUESTO!
server_port = 51820
server_address = 10.8.0.1/24
interface = wg0

[api]
# API Server Configuration
host = 0.0.0.0
port = 8000
jwt_secret = CHANGE-THIS-SECRET-KEY-IN-PRODUCTION    # <--- CAMBIA QUESTO!
jwt_algorithm = HS256
access_token_expire_minutes = 30

[database]
# Database Configuration
url = sqlite+aiosqlite:///./vpn_gateway.db
# For PostgreSQL in production:
# url = postgresql+asyncpg://user:password@localhost/vpn_gateway

[security]
# Security Settings
password_min_length = 8
require_email_verification = false
max_login_attempts = 5
lockout_duration_minutes = 15

[logging]
# Logging Configuration
level = INFO
file = vpn_gateway.log
```

**IMPORTANTE**: Cambia almeno questi valori:
- `public_endpoint` → Il tuo IP pubblico o hostname
- `jwt_secret` → Genera una chiave sicura

### Generare un JWT Secret Sicuro

```bash
# Genera una chiave random
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Copia l'output e incollalo in config.ini come jwt_secret
```

## Step 3: Test del Sistema di Configurazione

```bash
cd ~/hpsdr-udp-proxy

# Esegui lo script di test
./test_config.sh
```

**Output atteso:**
```
=========================================
HPSDR VPN Gateway - Configuration Test
=========================================

Step 1: Checking if config.ini exists...
✅ config.ini found

Step 2: Displaying current VPN configuration...
------------------------------------------------
[VPN Settings]
public_endpoint = 192.168.1.229
server_port = 51820
server_address = 10.8.0.1/24
interface = wg0

Step 3: Testing configuration module...
------------------------------------------------
VPN Public Endpoint: 192.168.1.229
VPN Server Port: 51820
VPN Server Address: 10.8.0.1/24
VPN Interface: wg0
API Host: 0.0.0.0
API Port: 8000
Database URL: sqlite+aiosqlite:///./vpn_gateway.db

✅ Configuration module loaded successfully

Step 4: Testing API server startup...
------------------------------------------------
✅ API server started successfully

=========================================
✅ Configuration Test Complete!
=========================================
```

## Step 4: Riavvio API Server

```bash
cd ~/hpsdr-udp-proxy

# Ferma il server API esistente (se in esecuzione)
pkill -f "python.*src.api.main"

# Avvia il server con la nuova configurazione
source venv/bin/activate
python3 -m src.api.main
```

**Verifica startup:**
Dovresti vedere questo messaggio di log:
```
INFO:src.api.main:WireGuard manager initialized: 192.168.1.229:51820
```

Se vedi il tuo IP corretto, significa che la configurazione funziona!

## Step 5: Test Creazione Nuovo Utente

Crea un utente di test per verificare che il VPN endpoint sia corretto:

```bash
# Registra un nuovo utente
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username": "bob", "email": "bob@example.com", "password": "BobPassword123"}'

# Login
TOKEN=$(curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "bob", "password": "BobPassword123"}' | jq -r '.access_token')

# Ottieni la configurazione VPN
curl -X GET "http://localhost:8000/users/me/vpn-config" \
  -H "Authorization: Bearer $TOKEN"
```

**Verifica l'output:**
Controlla che la configurazione VPN contenga:
```
Endpoint = 192.168.1.229:51820
```

Se vedi l'IP corretto, il sistema funziona perfettamente!

## Step 6: Verifica Peer WireGuard

```bash
# Controlla che il peer sia stato aggiunto
sudo wg show wg0

# Dovresti vedere il nuovo peer per bob
```

## Uso Avanzato: Variabili d'Ambiente

Puoi sovrascrivere qualsiasi impostazione con variabili d'ambiente:

```bash
# Formato: VPN_<SEZIONE>_<CHIAVE>
export VPN_VPN_PUBLIC_ENDPOINT=mio-dominio.dyndns.org
export VPN_API_PORT=9000

# Avvia il server
python3 -m src.api.main
```

Le variabili d'ambiente hanno la priorità sul file config.ini.

## Troubleshooting

### Problema: ModuleNotFoundError: No module named 'src.config'

**Soluzione:**
```bash
# Verifica che il file esista
ls -l src/config.py

# Riavvia da directory root del progetto
cd ~/hpsdr-udp-proxy
python3 -m src.api.main
```

### Problema: Config file not found

**Soluzione:**
```bash
# Il file config.ini non è obbligatorio, ma consigliato
cp config.example.ini config.ini
nano config.ini
```

### Problema: Endpoint ancora sbagliato

**Verifica:**
```bash
# Test configurazione
python3 -c "from src.config import config; print(config.vpn_public_endpoint)"

# Se mostra l'IP sbagliato, verifica config.ini
cat config.ini | grep public_endpoint
```

## Backup e Rollback

### Backup Configurazione Attuale

```bash
# Backup config e database
cp config.ini config.ini.backup
cp vpn_gateway.db vpn_gateway.db.backup
```

### Rollback (se necessario)

Se qualcosa va storto, puoi tornare alla versione precedente:

```bash
# Ripristina i file backup
mv config.ini.backup config.ini
mv vpn_gateway.db.backup vpn_gateway.db

# Riavvia il server
python3 -m src.api.main
```

## Prossimi Passi

Dopo aver verificato che il sistema di configurazione funziona:

1. **Testa con un client reale** - Importa la config VPN di bob su un client e verifica connessione
2. **Configura systemd** - Crea un servizio per avvio automatico
3. **Configura HTTPS** - Setup nginx reverse proxy per API
4. **Interfaccia Web Admin** - Opzionale: implementa UI web per gestione

## Domande Frequenti

**Q: Devo ricreare tutti gli utenti esistenti?**
A: No, gli utenti esistenti funzionano ancora. Solo i nuovi utenti avranno l'endpoint corretto.

**Q: Posso aggiornare l'endpoint per utenti esistenti?**
A: Sì, dovrai rigenerare le loro configurazioni VPN. Questo sarà più facile con la UI web admin.

**Q: Il file config.ini va committato su git?**
A: NO! Aggiungi `config.ini` a `.gitignore` perché contiene secrets. Committa solo `config.example.ini`.

**Q: Posso cambiare la configurazione senza riavviare?**
A: No, attualmente il server deve essere riavviato. In futuro si può implementare reload dinamico.

## Supporto

Se incontri problemi:
1. Controlla i log: `cat vpn_gateway.log`
2. Verifica permessi file: `ls -la config.ini`
3. Test manuale configurazione: `python3 -c "from src.config import config; print(vars(config))"`
