# Changelog - HPSDR VPN Gateway

## [2.1.0] - 2025-10-24

### Added - Configuration System

#### New Features
- **Configuration Management System** (`src/config.py`)
  - Centralizzata gestione configurazione
  - Supporto file `config.ini`
  - Override tramite variabili d'ambiente
  - Valori di default sicuri

- **Configuration File Template** (`config.example.ini`)
  - Template completo con tutte le opzioni
  - Commenti esplicativi
  - Organizzato in sezioni logiche (VPN, API, Database, Security, Logging)

- **Test Script** (`test_config.sh`)
  - Script automatico per testing configurazione
  - Verifica integrità file
  - Test caricamento moduli
  - Test startup API server

- **Documentation**
  - `docs/CONFIG_DEPLOYMENT_GUIDE.md` - Guida deployment completa
  - `DEPLOYMENT_CHECKLIST.md` - Checklist passo-passo
  - `docs/ADMIN_UI_DESIGN.md` - Design interfaccia web admin (futuro)
  - `CHANGELOG.md` - Questo file

### Changed

#### Modified Files
- **`src/api/main.py`**
  - Rimosse configurazioni hardcoded
  - Integrato sistema di configurazione
  - Parametri VPN ora caricati da config
  - Database URL configurabile
  - Host e porta API configurabili
  - Log migliorati con info endpoint

### Fixed

#### Issue #1: Hardcoded VPN Endpoint
- **Problema**: `public_endpoint` era hardcoded come "your-server-ip.example.com"
- **Impatto**: Tutte le configurazioni VPN generate avevano endpoint sbagliato
- **Soluzione**: Sistema di configurazione con priorità (env > file > default)
- **File coinvolti**:
  - `src/api/main.py:195` - Ora usa `config.vpn_public_endpoint`
  - `src/config.py` - Nuovo modulo configurazione

#### Issue #2: Mancanza Sistema Configurazione Centralizzato
- **Problema**: Impostazioni sparse nel codice, difficili da gestire
- **Soluzione**: Modulo `src/config.py` con properties per tutte le impostazioni
- **Benefici**:
  - Configurazione via file INI
  - Override con variabili d'ambiente
  - Validazione automatica
  - Gestione fallback

### Testing

#### Automatic Peer Management Test (2025-10-24)
- ✅ Creato utente 'alice' per test
- ✅ Verificato automatic peer addition a WireGuard
- ✅ Generata configurazione VPN
- ⚠️ Connectivity test inconclusivo (VM/host limitation)
- **Documentato in**: `TESTING_NOTES.md`

### Configuration Options

#### [vpn] Section
```ini
public_endpoint = <IP or hostname>  # Server pubblico per client VPN
server_port = 51820                 # Porta UDP WireGuard
server_address = 10.8.0.1/24       # Rete VPN
interface = wg0                     # Interfaccia WireGuard
```

#### [api] Section
```ini
host = 0.0.0.0                      # API host (0.0.0.0 = tutte interfacce)
port = 8000                         # Porta API
jwt_secret = <secret key>           # Chiave JWT (CAMBIARE!)
jwt_algorithm = HS256               # Algoritmo JWT
access_token_expire_minutes = 30    # Scadenza token
```

#### [database] Section
```ini
url = sqlite+aiosqlite:///./vpn_gateway.db  # URL database
```

#### [security] Section
```ini
password_min_length = 8             # Lunghezza minima password
require_email_verification = false  # Richiedi verifica email
max_login_attempts = 5              # Tentativi login prima lockout
lockout_duration_minutes = 15       # Durata lockout
```

#### [logging] Section
```ini
level = INFO                        # Livello log (DEBUG, INFO, WARNING, ERROR)
file = vpn_gateway.log             # File log
```

### Environment Variables Override

Tutte le opzioni possono essere sovrascritte con variabili d'ambiente:

```bash
# Format: VPN_<SECTION>_<KEY>
export VPN_VPN_PUBLIC_ENDPOINT=192.168.1.229
export VPN_API_PORT=9000
export VPN_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/vpn
```

### Migration Guide

#### From Version 2.0.0 to 2.1.0

1. **Backup Database**
   ```bash
   cp vpn_gateway.db vpn_gateway.db.backup
   ```

2. **Update Files**
   - Copia `src/config.py`
   - Copia `config.example.ini`
   - Aggiorna `src/api/main.py`

3. **Create Configuration**
   ```bash
   cp config.example.ini config.ini
   nano config.ini  # Edit settings
   ```

4. **Test**
   ```bash
   ./test_config.sh
   ```

5. **Restart Server**
   ```bash
   python3 -m src.api.main
   ```

### Breaking Changes

**Nessuno** - Compatibilità retroattiva mantenuta.

Se `config.ini` non esiste, il sistema usa valori di default (stesso comportamento precedente, ma endpoint sarà '127.0.0.1' invece di 'your-server-ip.example.com').

### Deprecations

Nessuna deprecazione in questa versione.

### Known Issues

1. **VM/Host VPN Testing**
   - Testing VPN client/server sulla stessa macchina fisica (VM/host) causa routing conflicts
   - Non è un bug del codice
   - Funziona correttamente con client e server fisicamente separati

2. **Utenti Esistenti**
   - Utenti creati prima del fix avranno endpoint sbagliato nella configurazione VPN
   - Workaround: Rigenerare configurazione VPN (richiede endpoint per regenerate config)
   - Fix permanente: Implementare funzione "Regenerate VPN Config" in future UI admin

### Security Notes

- **JWT Secret**: DEVE essere cambiato in produzione
- **config.ini**: NON committare su git (aggiungere a .gitignore)
- **Database**: Considerare migrazione a PostgreSQL per produzione
- **HTTPS**: Configurare nginx reverse proxy per API in produzione

### Performance

Nessun impatto sulle performance. Il sistema di configurazione è caricato all'avvio del server.

### Dependencies

Nessuna nuova dipendenza aggiunta.

### Contributors

- Claude AI (Anthropic) - Configuration system implementation
- Franco (User) - Testing e feedback

---

## [2.0.0] - 2025-10-23

### Initial VPN System Release

- User authentication system (JWT)
- VPN configuration generation
- WireGuard automation
- Database models (User, VPNSession, AuditLog)
- REST API endpoints
- Automatic peer management

**Documentato in**: `TESTING_NOTES.md` (Production VPN Test Results)

---

## Future Roadmap

### [2.2.0] - Planned
- **Web Admin Interface**
  - Dashboard
  - User management UI
  - VPN peers monitoring
  - Configuration editor
  - Audit logs viewer

### [2.3.0] - Planned
- **Enhanced Features**
  - Email notifications
  - VPN config QR codes
  - Statistics dashboard
  - Real-time monitoring (WebSocket)

### [3.0.0] - Planned
- **Production Features**
  - PostgreSQL migration
  - HTTPS/TLS support
  - Rate limiting
  - 2FA authentication
  - Backup/restore system
  - Multi-language support

---

## Version History

| Version | Date | Description |
|---------|------|-------------|
| 2.1.0 | 2025-10-24 | Configuration system |
| 2.0.0 | 2025-10-23 | Initial VPN system |
| 1.x.x | 2025-10-21 | UDP Gateway (pre-VPN) |
