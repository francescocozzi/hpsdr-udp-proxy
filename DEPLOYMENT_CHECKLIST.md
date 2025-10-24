# HPSDR VPN Gateway - Deployment Checklist

## Quick Start per Deployment sul Server Ubuntu

Segui questi passi in ordine per deployare il nuovo sistema di configurazione.

### Pre-requisiti
- [ ] Server Ubuntu con WireGuard installato
- [ ] Python 3.7+ installato
- [ ] Accesso SSH al server
- [ ] Git configurato (opzionale)

---

## Step 1: Trasferimento File

### Opzione A: Con Git (Consigliato)

Sul **server Ubuntu**:
```bash
cd ~/hpsdr-udp-proxy
git pull origin main
```

### Opzione B: Copia Manuale via SCP

Dal **Mac**:
```bash
scp ~/Documents/udp-gateway/src/config.py francoz@192.168.1.229:~/hpsdr-udp-proxy/src/
scp ~/Documents/udp-gateway/config.example.ini francoz@192.168.1.229:~/hpsdr-udp-proxy/
scp ~/Documents/udp-gateway/test_config.sh francoz@192.168.1.229:~/hpsdr-udp-proxy/
scp ~/Documents/udp-gateway/src/api/main.py francoz@192.168.1.229:~/hpsdr-udp-proxy/src/api/
```

**Checklist:**
- [ ] `src/config.py` copiato
- [ ] `config.example.ini` copiato
- [ ] `test_config.sh` copiato
- [ ] `src/api/main.py` aggiornato

---

## Step 2: Creazione config.ini

Sul **server Ubuntu**:

```bash
cd ~/hpsdr-udp-proxy

# Crea config.ini
cp config.example.ini config.ini

# Modifica con nano
nano config.ini
```

**Modifiche da fare:**

1. **Sezione [vpn]**
   ```ini
   public_endpoint = 192.168.1.229    # ← INSERISCI IL TUO IP!
   ```

2. **Sezione [api]**
   ```ini
   jwt_secret = XXXXX    # ← GENERA UNA CHIAVE SICURA!
   ```

   Genera chiave con:
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

**Checklist:**
- [ ] `config.ini` creato
- [ ] `public_endpoint` impostato correttamente
- [ ] `jwt_secret` cambiato (non usare il default!)
- [ ] File salvato (Ctrl+O, Ctrl+X in nano)

---

## Step 3: Test Configurazione

```bash
cd ~/hpsdr-udp-proxy
chmod +x test_config.sh
./test_config.sh
```

**Output atteso:**
```
✅ config.ini found
✅ Configuration module loaded successfully
✅ API server started successfully
✅ Configuration Test Complete!
```

**Checklist:**
- [ ] Script eseguito senza errori
- [ ] Public endpoint mostrato correttamente
- [ ] API server si avvia

**Se il test fallisce:**
- Verifica che `src/config.py` esista
- Controlla sintassi di `config.ini`
- Vedi `docs/CONFIG_DEPLOYMENT_GUIDE.md` per troubleshooting

---

## Step 4: Backup Database Esistente

```bash
cd ~/hpsdr-udp-proxy

# Backup database
cp vpn_gateway.db vpn_gateway.db.backup.$(date +%Y%m%d)

# Backup config (se esiste)
[ -f config.ini ] && cp config.ini config.ini.backup
```

**Checklist:**
- [ ] Database backup creato
- [ ] Config backup creato (se esistente)

---

## Step 5: Riavvio API Server

```bash
cd ~/hpsdr-udp-proxy

# Ferma server esistente
pkill -f "python.*src.api.main"

# Attendi 2 secondi
sleep 2

# Avvia nuovo server
source venv/bin/activate
python3 -m src.api.main
```

**Verifica log di startup:**
Dovresti vedere:
```
INFO:src.api.main:Starting HPSDR VPN Gateway API...
INFO:src.api.main:Database initialized
INFO:src.api.main:WireGuard manager initialized: 192.168.1.229:51820
```

**Checklist:**
- [ ] Server vecchio fermato
- [ ] Nuovo server avviato
- [ ] Log mostra IP endpoint corretto
- [ ] Nessun errore all'avvio

**In caso di errori:**
```bash
# Ripristina backup
mv vpn_gateway.db.backup.YYYYMMDD vpn_gateway.db
python3 -m src.api.main
```

---

## Step 6: Test Creazione Nuovo Utente

In un **altro terminale** (o in background):

```bash
# Crea utente bob
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"username": "bob", "email": "bob@example.com", "password": "BobPassword123"}'

# Login bob
TOKEN=$(curl -s -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "bob", "password": "BobPassword123"}' | jq -r '.access_token')

# Ottieni config VPN
curl -X GET "http://localhost:8000/users/me/vpn-config" \
  -H "Authorization: Bearer $TOKEN" | jq -r '.config'
```

**Verifica output:**
La configurazione VPN deve contenere:
```
Endpoint = 192.168.1.229:51820
```

**Checklist:**
- [ ] Utente bob creato correttamente
- [ ] Login riuscito
- [ ] VPN config generata
- [ ] **Endpoint è CORRETTO** (192.168.1.229:51820)

---

## Step 7: Verifica WireGuard Peer

```bash
sudo wg show wg0 | grep -A 5 "peer:"
```

**Output atteso:**
Dovresti vedere il peer di bob con:
- Public key
- Allowed IPs: `10.8.0.4/32` (o IP successivo disponibile)

**Checklist:**
- [ ] Peer automaticamente aggiunto
- [ ] IP corretto assegnato

---

## Step 8: Test Completo (Opzionale)

Se hai un client WireGuard disponibile:

1. **Salva config bob:**
   ```bash
   curl -X GET "http://localhost:8000/users/me/vpn-config" \
     -H "Authorization: Bearer $TOKEN" | jq -r '.config' > bob-vpn.conf
   ```

2. **Trasferisci bob-vpn.conf al client**

3. **Importa e attiva tunnel WireGuard**

4. **Ping al server VPN:**
   ```bash
   ping 10.8.0.1
   ```

**Checklist:**
- [ ] Config importata su client
- [ ] Tunnel attivato
- [ ] Ping funziona
- [ ] Handshake visibile sul server

---

## Step 9: Cleanup (Opzionale)

Se tutto funziona, puoi rimuovere i file di test:

```bash
# Rimuovi utente bob (se era solo test)
# curl -X DELETE "http://localhost:8000/admin/users/{bob_id}" -H "Authorization: Bearer $ADMIN_TOKEN"

# Mantieni i backup per almeno 1 settimana
```

**Checklist:**
- [ ] Vecchi backup rimossi (dopo 7+ giorni)
- [ ] Utenti di test rimossi (opzionale)

---

## Configurazione Systemd (Prossimo Step)

Per avvio automatico del server:

```bash
# Crea servizio systemd
sudo nano /etc/systemd/system/vpn-gateway.service
```

Contenuto:
```ini
[Unit]
Description=HPSDR VPN Gateway API
After=network.target wg-quick@wg0.service

[Service]
Type=simple
User=francoz
WorkingDirectory=/home/francoz/hpsdr-udp-proxy
Environment="PATH=/home/francoz/hpsdr-udp-proxy/venv/bin"
ExecStart=/home/francoz/hpsdr-udp-proxy/venv/bin/python3 -m src.api.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Attiva:
```bash
sudo systemctl daemon-reload
sudo systemctl enable vpn-gateway
sudo systemctl start vpn-gateway
sudo systemctl status vpn-gateway
```

---

## Rollback (Se Necessario)

Se qualcosa va storto:

```bash
cd ~/hpsdr-udp-proxy

# Ferma server
pkill -f "python.*src.api.main"

# Ripristina backup
cp vpn_gateway.db.backup.YYYYMMDD vpn_gateway.db

# Rimuovi config.ini (usa valori default)
mv config.ini config.ini.broken

# Riavvia
python3 -m src.api.main
```

---

## Riepilogo File Creati/Modificati

### Nuovi File
- ✅ `src/config.py` - Modulo configurazione
- ✅ `config.example.ini` - Template config
- ✅ `config.ini` - Configurazione attiva (NON committare!)
- ✅ `test_config.sh` - Script di test
- ✅ `docs/CONFIG_DEPLOYMENT_GUIDE.md` - Guida dettagliata
- ✅ `DEPLOYMENT_CHECKLIST.md` - Questa checklist

### File Modificati
- ✅ `src/api/main.py` - Usa nuovo sistema config

---

## Prossimi Passi

Dopo deployment riuscito:

1. **Configura systemd** (avvio automatico)
2. **Setup HTTPS** con nginx reverse proxy
3. **Implementa UI Web Admin** (opzionale)
4. **Configura backup automatici** database
5. **Monitoring e alerting**

---

## Supporto

**Documentazione:**
- `docs/CONFIG_DEPLOYMENT_GUIDE.md` - Guida completa
- `docs/VPN_SETUP.md` - Setup iniziale VPN
- `docs/ADMIN_UI_DESIGN.md` - Design interfaccia web
- `TESTING_NOTES.md` - Note di test

**Troubleshooting:**
- Controlla log: `tail -f vpn_gateway.log`
- Test config: `python3 -c "from src.config import config; print(config.vpn_public_endpoint)"`
- Verifica WireGuard: `sudo wg show wg0`

---

## ✅ Deployment Completato!

Se tutti i check sono ✅, il deployment è riuscito!

**Risultato finale:**
- Sistema di configurazione funzionante
- Endpoint VPN configurabile
- Nuovi utenti con endpoint corretto
- Sistema pronto per production
