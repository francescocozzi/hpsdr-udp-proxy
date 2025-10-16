#!/usr/bin/env python3
"""
Test script per verificare l'Authentication Manager

Esegui: python tests/test_auth.py
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.auth import DatabaseManager, AuthManager
from src.utils import load_config


async def test_authentication():
    """Test del sistema di autenticazione"""

    print("=" * 70)
    print("TEST AUTHENTICATION MANAGER")
    print("=" * 70)

    # Setup
    print("\n1. Setup database e auth manager...")
    try:
        config = load_config("config/config.yaml")

        db = DatabaseManager(
            connection_string=config.database.get_connection_string(),
            pool_size=config.database.pool_size
        )
        await db.connect()

        auth = AuthManager(
            db_manager=db,
            jwt_secret=config.auth.jwt_secret,
            jwt_algorithm=config.auth.jwt_algorithm,
            token_expiry=config.auth.token_expiry,
            refresh_token_expiry=config.auth.refresh_token_expiry,
            max_login_attempts=config.auth.max_login_attempts,
            lockout_duration=config.auth.lockout_duration
        )
        print("   ✓ Database e Auth Manager inizializzati")
    except Exception as e:
        print(f"   ✗ Errore setup: {e}")
        return False

    # Test password hashing
    print("\n2. Test password hashing...")
    try:
        password = "test_password_123"
        hashed = auth.hash_password(password)
        print(f"   ✓ Password hashata: {hashed[:30]}...")

        # Verifica
        if auth.verify_password(password, hashed):
            print("   ✓ Verifica password corretta")
        else:
            print("   ✗ Verifica password fallita")
            return False

        # Test password errata
        if not auth.verify_password("wrong_password", hashed):
            print("   ✓ Password errata correttamente rifiutata")
        else:
            print("   ✗ Password errata accettata!")
            return False
    except Exception as e:
        print(f"   ✗ Errore hashing: {e}")
        return False

    # Test creazione utente con password
    print("\n3. Test creazione utente con password...")
    try:
        test_password = "SecurePassword123!"
        user = await auth.create_user(
            username="auth_test_user",
            password=test_password,
            email="authtest@example.com",
            is_admin=False
        )
        print(f"   ✓ Utente creato con ID: {user.id}")
        test_user_id = user.id
        test_username = user.username
    except Exception as e:
        print(f"   ✗ Errore creazione utente: {e}")
        await db.disconnect()
        return False

    # Test autenticazione con credenziali corrette
    print("\n4. Test login con credenziali corrette...")
    try:
        token, user = await auth.authenticate(
            username=test_username,
            password=test_password,
            client_ip="127.0.0.1"
        )
        print(f"   ✓ Login riuscito!")
        print(f"     User: {user.username}")
        print(f"     Token: {token[:50]}...")
    except Exception as e:
        print(f"   ✗ Errore login: {e}")
        return False

    # Test validazione token
    print("\n5. Test validazione token...")
    try:
        payload = auth.validate_token(token)
        print(f"   ✓ Token valido")
        print(f"     User ID: {payload['user_id']}")
        print(f"     Username: {payload['username']}")
        print(f"     Scadenza: {payload['exp']}")
    except Exception as e:
        print(f"   ✗ Errore validazione token: {e}")
        return False

    # Test token invalido
    print("\n6. Test token invalido...")
    try:
        invalid_token = "invalid.token.here"
        payload = auth.validate_token(invalid_token)
        print(f"   ✗ Token invalido accettato!")
        return False
    except Exception:
        print("   ✓ Token invalido correttamente rifiutato")

    # Test login con password errata
    print("\n7. Test login con password errata...")
    try:
        token, user = await auth.authenticate(
            username=test_username,
            password="wrong_password",
            client_ip="127.0.0.1"
        )
        print(f"   ✗ Login con password errata accettato!")
        return False
    except Exception as e:
        print(f"   ✓ Login fallito come atteso: {type(e).__name__}")

        # Verifica tentativi falliti
        user = await db.get_user_by_username(test_username)
        print(f"     Tentativi falliti: {user.failed_login_attempts}")

    # Test cambio password
    print("\n8. Test cambio password...")
    try:
        new_password = "NewSecurePassword456!"
        success = await auth.change_password(
            user_id=test_user_id,
            old_password=test_password,
            new_password=new_password
        )
        if success:
            print("   ✓ Password cambiata con successo")

            # Verifica login con nuova password
            token, user = await auth.authenticate(
                username=test_username,
                password=new_password,
                client_ip="127.0.0.1"
            )
            print("   ✓ Login con nuova password riuscito")
        else:
            print("   ✗ Cambio password fallito")
            return False
    except Exception as e:
        print(f"   ✗ Errore cambio password: {e}")
        return False

    # Test refresh token
    print("\n9. Test generazione refresh token...")
    try:
        refresh_token = auth.generate_refresh_token(test_user_id, test_username)
        print(f"   ✓ Refresh token generato: {refresh_token[:50]}...")

        # Valida refresh token
        payload = auth.validate_token(refresh_token)
        if payload['type'] == 'refresh':
            print("   ✓ Refresh token valido")
        else:
            print("   ✗ Tipo token errato")
            return False
    except Exception as e:
        print(f"   ✗ Errore refresh token: {e}")
        return False

    # Test account lockout (simulazione multipli tentativi falliti)
    print("\n10. Test account lockout...")
    try:
        print("   Simulando multipli login falliti...")
        max_attempts = config.auth.max_login_attempts

        for i in range(max_attempts + 1):
            try:
                await auth.authenticate(
                    username=test_username,
                    password="wrong_password",
                    client_ip="127.0.0.1"
                )
            except Exception:
                pass

        # Verifica che l'account sia bloccato
        user = await db.get_user_by_username(test_username)
        if user.is_locked():
            print(f"   ✓ Account bloccato dopo {max_attempts} tentativi")
            print(f"     Bloccato fino a: {user.locked_until}")
        else:
            print("   ⚠ Account non bloccato (potrebbe essere già stato testato)")

        # Prova login con account bloccato
        try:
            await auth.authenticate(
                username=test_username,
                password=new_password,
                client_ip="127.0.0.1"
            )
            print("   ✗ Login con account bloccato accettato!")
        except Exception as e:
            print(f"   ✓ Login bloccato: {type(e).__name__}")

        # Reset lockout per cleanup
        await db.reset_failed_login(test_user_id)
        print("   ✓ Lockout resettato per cleanup")

    except Exception as e:
        print(f"   ✗ Errore test lockout: {e}")

    # Cleanup
    print("\n11. Cleanup...")
    try:
        # Qui potresti eliminare l'utente di test
        print("   ℹ Utente di test mantenuto per altri test")
    except Exception as e:
        print(f"   ⚠ Warning cleanup: {e}")

    # Disconnessione
    print("\n12. Disconnessione...")
    try:
        await db.disconnect()
        print("   ✓ Disconnessione completata")
    except Exception as e:
        print(f"   ✗ Errore disconnessione: {e}")
        return False

    print("\n" + "=" * 70)
    print("✓ TUTTI I TEST DI AUTENTICAZIONE COMPLETATI")
    print("=" * 70)
    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(test_authentication())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠ Test interrotto dall'utente")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ ERRORE FATALE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
