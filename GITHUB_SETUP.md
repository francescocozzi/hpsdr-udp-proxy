# Come Caricare su GitHub

## Passo 1: Crea la Repository su GitHub

1. Vai su https://github.com/new
2. Inserisci il nome della repository: **hpsdr-udp-proxy** (o il nome che preferisci)
3. Descrizione: "High-performance UDP proxy/gateway for HPSDR protocol with authentication"
4. Scegli "Public" o "Private"
5. **NON** aggiungere README, .gitignore o license (li abbiamo già)
6. Clicca "Create repository"

## Passo 2: Collega il Repository Locale

Dopo aver creato la repository su GitHub, copia l'URL che appare (es: `https://github.com/tuousername/hpsdr-udp-proxy.git`)

Poi esegui questi comandi:

```bash
# Aggiungi il remote
git remote add origin https://github.com/tuousername/hpsdr-udp-proxy.git

# Verifica
git remote -v

# Rinomina il branch in main (se preferisci)
git branch -M main

# Push del codice
git push -u origin main
```

## Passo 3: Verifica

Vai su GitHub e ricarica la pagina della tua repository. Dovresti vedere tutti i file caricati!

## Comandi Git Utili per il Futuro

```bash
# Vedere lo stato
git status

# Aggiungere modifiche
git add .

# Commit
git commit -m "Descrizione delle modifiche"

# Push su GitHub
git push

# Pull da GitHub
git pull

# Vedere i log
git log --oneline

# Creare un nuovo branch
git checkout -b nome-branch

# Tornare al branch principale
git checkout main
```

## Suggerimenti per il README su GitHub

Una volta caricato, GitHub mostrerà automaticamente il tuo `README.md` sulla homepage della repository.

Potresti voler aggiungere:
- Badges (build status, license, version)
- Screenshot o diagrammi
- Link a documentazione
- Contributors section

## Topics Suggeriti per GitHub

Quando sei sulla pagina della repository, clicca su "Add topics" e aggiungi:
- `sdr`
- `hpsdr`
- `radio`
- `ham-radio`
- `hermes-lite-2`
- `udp-proxy`
- `python`
- `asyncio`
- `amateur-radio`

Questo aiuterà altri a trovare il progetto!

## Note Finali

- Il file `config/config.yaml` NON verrà caricato (è in .gitignore)
- I file nel folder `logs/` NON verranno caricati
- Il database `database/proxy.db` NON verrà caricato
- L'ambiente virtuale `venv/` NON verrà caricato

Questo è corretto per sicurezza e per evitare file non necessari.
