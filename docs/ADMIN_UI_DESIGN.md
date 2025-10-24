# HPSDR VPN Gateway - Admin UI Design

## Overview

Interfaccia web-based per la gestione degli utenti VPN e delle impostazioni di sistema.

## Architettura

### Frontend
- **Framework**: HTML/CSS/JavaScript puro (no framework pesanti)
- **Stile**: Bootstrap 5 per UI responsiva
- **Comunicazione**: API REST tramite fetch()
- **Autenticazione**: JWT token in localStorage

### Backend
- **Framework**: FastAPI (già esistente)
- **API**: Estensione degli endpoint esistenti
- **Static Files**: Serviti da FastAPI

## Funzionalità Principali

### 1. Dashboard
- **Panoramica sistema**
  - Numero totale utenti
  - Utenti attivi
  - Peers VPN connessi
  - Stato interfaccia WireGuard
  - Grafico connessioni ultime 24h (futuro)

### 2. Gestione Utenti
- **Lista utenti**
  - Tabella con: Username, Email, VPN IP, Stato, Ultima connessione
  - Filtro e ricerca
  - Ordinamento colonne
  - Paginazione

- **Azioni per utente**
  - Visualizza dettagli
  - Modifica (enable/disable VPN, activate/deactivate account)
  - Elimina (con conferma)
  - Scarica configurazione VPN
  - Reset password (futuro)

- **Creazione nuovo utente**
  - Form: Username, Email, Password
  - Generazione automatica credenziali VPN
  - Email notifica (futuro)

### 3. Configurazione Sistema
- **Impostazioni VPN**
  - Public endpoint (IP/hostname)
  - Server port
  - VPN network range
  - Interface name

- **Impostazioni API**
  - Host e porta
  - Token expiration

- **Sicurezza**
  - Min password length
  - Max login attempts
  - Lockout duration

- **Salvataggio**: Aggiornamento file config.ini

### 4. Monitoraggio VPN
- **Peers connessi**
  - Lista peers attivi
  - Ultimo handshake
  - Bytes sent/received
  - Endpoint IP
  - Kick peer (disconnect)

### 5. Logs e Audit
- **Audit log**
  - Tabella eventi: User, Action, Timestamp, Success, Details
  - Filtro per utente, azione, data
  - Export CSV

### 6. Statistiche
- **Grafici** (futuro con Chart.js)
  - Connessioni nel tempo
  - Traffico VPN
  - Login failures
  - User growth

## Layout UI

```
┌─────────────────────────────────────────────────┐
│ Header: HPSDR VPN Gateway Admin                │
│ User: admin | Logout                           │
├─────────────┬───────────────────────────────────┤
│             │                                   │
│ Sidebar     │  Main Content Area                │
│             │                                   │
│ - Dashboard │  [Dynamic content based on        │
│ - Users     │   selected menu item]             │
│ - VPN Peers │                                   │
│ - Config    │                                   │
│ - Logs      │                                   │
│ - Stats     │                                   │
│             │                                   │
│             │                                   │
│             │                                   │
└─────────────┴───────────────────────────────────┘
│ Footer: Version 2.0 | © 2025                   │
└─────────────────────────────────────────────────┘
```

## Pagine Principali

### Login Page
- Form login (username, password)
- Messaggio errore
- Link recupero password (futuro)

### Dashboard
- 4 Card statistiche (Total Users, Active Users, Connected Peers, VPN Status)
- Tabella ultimi log di sistema
- Quick actions (Add User, View Config)

### Users Page
- Search bar
- Filtri (Active/Inactive, VPN Enabled/Disabled)
- Tabella users
- Button "Add New User"
- Modal per add/edit user

### VPN Peers Page
- Tabella peers attivi
- Real-time status (auto-refresh ogni 10s)
- Button refresh manual

### Configuration Page
- Form con tutte le impostazioni
- Organizzato in sezioni (VPN, API, Security)
- Button Save Changes
- Alert conferma salvataggio

### Logs Page
- Tabella audit log
- Filtri avanzati
- Paginazione
- Button Export CSV

## API Endpoints Necessari

### Già Esistenti
- `POST /auth/login` - Login
- `GET /users/me` - Current user
- `GET /admin/users` - List users
- `PATCH /admin/users/{id}` - Update user
- `DELETE /admin/users/{id}` - Delete user
- `POST /auth/register` - Create user
- `GET /admin/vpn/peers` - List VPN peers
- `GET /stats/system` - System stats

### Da Aggiungere
- `GET /admin/config` - Get current configuration
- `PUT /admin/config` - Update configuration
- `GET /admin/logs` - Get audit logs with pagination
- `GET /admin/logs/export` - Export logs as CSV
- `POST /admin/vpn/peers/{id}/disconnect` - Disconnect peer
- `GET /admin/stats/connections` - Connection statistics
- `POST /admin/users/{id}/reset-password` - Reset user password

## Sicurezza

- **Authentication**: JWT token required per tutte le API admin
- **Authorization**: Solo utenti con `is_admin=true` possono accedere
- **HTTPS**: Richiesto in produzione (nginx reverse proxy)
- **CORS**: Configurato correttamente per dominio
- **Rate Limiting**: Protezione contro brute force
- **Input Validation**: Sanitizzazione dati form
- **SQL Injection**: Protezione via SQLAlchemy ORM

## Tecnologie

### Frontend
- Bootstrap 5.3
- Font Awesome 6 (icons)
- Vanilla JavaScript (ES6+)
- Fetch API per REST calls

### Backend
- FastAPI (Python)
- Jinja2 Templates (per servire HTML)
- SQLAlchemy (ORM)
- Pydantic (validation)

## File Structure

```
src/
├── admin/
│   ├── __init__.py
│   ├── routes.py          # Admin API routes
│   ├── static/
│   │   ├── css/
│   │   │   └── admin.css
│   │   └── js/
│   │       ├── api.js     # API client
│   │       ├── auth.js    # Authentication
│   │       ├── dashboard.js
│   │       ├── users.js
│   │       ├── peers.js
│   │       ├── config.js
│   │       └── logs.js
│   └── templates/
│       ├── layout.html     # Base template
│       ├── login.html
│       ├── dashboard.html
│       ├── users.html
│       ├── peers.html
│       ├── config.html
│       └── logs.html
```

## Responsive Design

- **Desktop**: Sidebar sempre visibile, layout a 2 colonne
- **Tablet**: Sidebar collapsibile, layout adattivo
- **Mobile**: Sidebar come menu hamburger, layout a colonna singola

## Future Enhancements

1. **Real-time Updates**: WebSocket per aggiornamenti live
2. **Notifications**: Sistema notifiche push
3. **Email Integration**: Invio email per registrazione/reset password
4. **2FA**: Two-factor authentication
5. **Dark Mode**: Toggle tema scuro
6. **Multi-language**: i18n support
7. **API Keys**: Gestione API keys per integrazione terze parti
8. **Backup/Restore**: Backup automatico database
9. **VPN Config QR Code**: QR code per mobile devices
10. **Advanced Analytics**: Dashboard avanzata con grafici dettagliati

## Installation

1. Files statici vengono serviti da FastAPI
2. Template rendering con Jinja2
3. No build process necessario (HTML/CSS/JS vanilla)
4. Deployment: copia files e restart API server

## Testing

- Test manuali su browser
- Responsive testing con Chrome DevTools
- API testing con Postman/curl
- Security testing (XSS, CSRF, SQL injection)
