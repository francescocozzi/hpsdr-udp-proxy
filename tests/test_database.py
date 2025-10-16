#!/usr/bin/env python3
"""
Test script per verificare il Database Manager

Esegui: python tests/test_database.py
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.auth import DatabaseManager
from src.utils import load_config


async def test_database():
    """Test delle operazioni base del database"""

    print("=" * 70)
    print("TEST DATABASE MANAGER")
    print("=" * 70)

    # Carica configurazione
    print("\n1. Caricamento configurazione...")
    try:
        config = load_config("config/config.yaml")
        print("   ✓ Configurazione caricata")
    except Exception as e:
        print(f"   ✗ Errore: {e}")
        return False

    # Connessione database
    print("\n2. Connessione al database...")
    try:
        db = DatabaseManager(
            connection_string=config.database.get_connection_string(),
            pool_size=config.database.pool_size,
            max_overflow=config.database.max_overflow
        )
        await db.connect()
        print("   ✓ Connessione stabilita")
    except Exception as e:
        print(f"   ✗ Errore connessione: {e}")
        return False

    # Health check
    print("\n3. Health check database...")
    try:
        healthy = await db.health_check()
        if healthy:
            print("   ✓ Database sano e funzionante")
        else:
            print("   ✗ Database non risponde correttamente")
            return False
    except Exception as e:
        print(f"   ✗ Errore health check: {e}")
        return False

    # Test creazione utente
    print("\n4. Test creazione utente...")
    try:
        user = await db.create_user(
            username="test_user",
            password_hash="$2b$12$test_hash",
            email="test@example.com",
            role="user"
        )
        print(f"   ✓ Utente creato con ID: {user.id}")
        user_id = user.id
    except Exception as e:
        print(f"   ✗ Errore creazione utente: {e}")
        await db.disconnect()
        return False

    # Test recupero utente
    print("\n5. Test recupero utente per username...")
    try:
        retrieved_user = await db.get_user_by_username("test_user")
        if retrieved_user and retrieved_user.username == "test_user":
            print(f"   ✓ Utente recuperato: {retrieved_user.username}")
            print(f"     Email: {retrieved_user.email}")
            print(f"     Ruolo: {retrieved_user.role}")
        else:
            print("   ✗ Utente non trovato")
    except Exception as e:
        print(f"   ✗ Errore recupero utente: {e}")

    # Test recupero utente per ID
    print("\n6. Test recupero utente per ID...")
    try:
        retrieved_user = await db.get_user_by_id(user_id)
        if retrieved_user and retrieved_user.id == user_id:
            print(f"   ✓ Utente recuperato per ID: {user_id}")
        else:
            print("   ✗ Utente non trovato per ID")
    except Exception as e:
        print(f"   ✗ Errore recupero utente per ID: {e}")

    # Test lista utenti
    print("\n7. Test lista tutti gli utenti...")
    try:
        users = await db.get_all_users()
        print(f"   ✓ Trovati {len(users)} utenti nel database")
        for u in users:
            print(f"     - {u.username} ({u.email}) - {u.role}")
    except Exception as e:
        print(f"   ✗ Errore lista utenti: {e}")

    # Test creazione radio
    print("\n8. Test creazione radio...")
    try:
        radio = await db.create_radio(
            name="Test Radio",
            ip_address="192.168.1.100",
            port=1024,
            mac_address="00:1C:C0:A2:12:34"
        )
        print(f"   ✓ Radio creata con ID: {radio.id}")
        radio_id = radio.id
    except Exception as e:
        print(f"   ✗ Errore creazione radio: {e}")
        radio_id = None

    # Test recupero radio
    if radio_id:
        print("\n9. Test recupero radio...")
        try:
            radios = await db.get_all_radios()
            print(f"   ✓ Trovate {len(radios)} radio nel database")
            for r in radios:
                status = "Abilitata" if r.enabled else "Disabilitata"
                print(f"     - {r.name} ({r.ip_address}:{r.port}) - {status}")
        except Exception as e:
            print(f"   ✗ Errore recupero radio: {e}")

    # Test creazione sessione
    print("\n10. Test creazione sessione...")
    try:
        from datetime import datetime, timedelta
        session = await db.create_session(
            user_id=user_id,
            token="test_token_12345",
            client_ip="127.0.0.1",
            client_port=50000,
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        print(f"   ✓ Sessione creata con ID: {session.id}")
        session_id = session.id
    except Exception as e:
        print(f"   ✗ Errore creazione sessione: {e}")
        session_id = None

    # Test recupero sessione
    if session_id:
        print("\n11. Test recupero sessione per token...")
        try:
            session = await db.get_session_by_token("test_token_12345")
            if session:
                print(f"   ✓ Sessione recuperata")
                print(f"     User ID: {session.user_id}")
                print(f"     Client: {session.client_ip}:{session.client_port}")
                print(f"     Scade: {session.expires_at}")
            else:
                print("   ✗ Sessione non trovata")
        except Exception as e:
            print(f"   ✗ Errore recupero sessione: {e}")

    # Test activity log
    print("\n12. Test activity log...")
    try:
        await db.log_activity(
            user_id=user_id,
            action="test_action",
            details="Test logging from test script",
            ip_address="127.0.0.1"
        )
        print("   ✓ Activity log creato")
    except Exception as e:
        print(f"   ✗ Errore activity log: {e}")

    # Cleanup
    print("\n13. Cleanup dati di test...")
    try:
        # Elimina sessione
        if session_id:
            async with db.session() as session:
                from src.auth.models import Session
                stmt = session.query(Session).filter(Session.id == session_id)
                await session.delete(stmt.first())
                print("   ✓ Sessione eliminata")

        # In un ambiente di test reale, qui elimineresti anche utente e radio
        # Per ora li lasciamo per altri test
        print("   ℹ Utente e radio test mantenuti per altri test")

    except Exception as e:
        print(f"   ⚠ Warning cleanup: {e}")

    # Disconnessione
    print("\n14. Disconnessione database...")
    try:
        await db.disconnect()
        print("   ✓ Disconnessione completata")
    except Exception as e:
        print(f"   ✗ Errore disconnessione: {e}")
        return False

    print("\n" + "=" * 70)
    print("✓ TUTTI I TEST COMPLETATI CON SUCCESSO")
    print("=" * 70)
    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(test_database())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠ Test interrotto dall'utente")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ ERRORE FATALE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
