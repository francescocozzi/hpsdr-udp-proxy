# Test Suite - HPSDR UDP Proxy

Questa directory contiene gli script di test per verificare i componenti del proxy.

## 📋 Test Disponibili

### Test Componenti Base

#### 1. test_database.py
Test delle operazioni database:
```bash
python tests/test_database.py
```

**Verifica:**
- ✅ Connessione database
- ✅ CRUD operations (Create, Read, Update, Delete)
- ✅ Gestione utenti, radio, sessioni
- ✅ Health check
- ✅ Activity logging

---

#### 2. test_auth.py
Test del sistema di autenticazione:
```bash
python tests/test_auth.py
```

**Verifica:**
- ✅ Password hashing (bcrypt)
- ✅ JWT token generation/validation
- ✅ Login flow
- ✅ Account lockout
- ✅ Refresh tokens
- ✅ Change password

---

#### 3. test_packets.py
Test del packet handler HPSDR:
```bash
python tests/test_packets.py
```

**Verifica:**
- ✅ Discovery packet parsing
- ✅ Data packet parsing
- ✅ Packet generation
- ✅ Protocol 1 support
- ✅ Statistics collection

---

## 🚀 Esecuzione Rapida

### Esegui tutti i test
```bash
# Test database
python tests/test_database.py

# Test autenticazione
python tests/test_auth.py

# Test packet handler
python tests/test_packets.py
```

### Esegui con pytest (se installato)
```bash
# Installa pytest se necessario
pip install pytest pytest-asyncio

# Esegui tutti i test
pytest tests/

# Con coverage
pytest --cov=src tests/

# Verbose
pytest -v tests/
```

---

## 📝 Requisiti

Assicurati di avere:

1. **Database inizializzato:**
   ```bash
   python scripts/init_db.py
   ```

2. **Configurazione valida:**
   ```bash
   cp config/config.yaml.example config/config.yaml
   # Edita config.yaml con le tue impostazioni
   ```

3. **Dipendenze installate:**
   ```bash
   pip install -r requirements.txt
   ```

---

## 🔍 Output Atteso

### Test Database
```
======================================================================
TEST DATABASE MANAGER
======================================================================

1. Caricamento configurazione...
   ✓ Configurazione caricata

2. Connessione al database...
   ✓ Connessione stabilita

[...]

✓ TUTTI I TEST COMPLETATI CON SUCCESSO
```

### Test Autenticazione
```
======================================================================
TEST AUTHENTICATION MANAGER
======================================================================

1. Setup database e auth manager...
   ✓ Database e Auth Manager inizializzati

2. Test password hashing...
   ✓ Password hashata

[...]

✓ TUTTI I TEST DI AUTENTICAZIONE COMPLETATI
```

### Test Packets
```
======================================================================
TEST HPSDR PACKET HANDLER
======================================================================

1. Inizializzazione PacketHandler...
   ✓ PacketHandler inizializzato

[...]

✓ TUTTI I TEST DEL PACKET HANDLER COMPLETATI
```

---

## ⚠️ Note

- I test del database creano dati di test che vengono poi eliminati
- I test di autenticazione possono lasciare utenti di test nel database
- I test sono idempotenti: puoi eseguirli multiple volte
- I test NON richiedono hardware HPSDR reale

---

## 📚 Documentazione Completa

Per una guida completa sul testing, inclusi test end-to-end con hardware reale:

👉 Vedi: `docs/TESTING.md`

---

## 🐛 Troubleshooting

### Errore: Database locked
```bash
# Assicurati che il proxy non sia in esecuzione
pkill -f "python main.py"
```

### Errore: Module not found
```bash
# Assicurati di essere nella directory root del progetto
cd /path/to/udp-gateway
python tests/test_xxx.py
```

### Errore: Configuration file not found
```bash
# Verifica che config.yaml esista
ls -la config/config.yaml

# Se manca, copialo dall'esempio
cp config/config.yaml.example config/config.yaml
```

---

## 📊 Exit Codes

- **0**: Tutti i test passati con successo
- **1**: Almeno un test fallito
- Exit code può essere usato in CI/CD pipeline

---

**Versione**: 1.0
**Ultima revisione**: 16 Ottobre 2025
