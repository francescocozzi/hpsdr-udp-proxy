#!/usr/bin/env python3
"""
Test script per verificare il Packet Handler HPSDR

Esegui: python tests/test_packets.py
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import PacketHandler, HPSDRPacketType


def test_packet_handler():
    """Test del packet handler HPSDR"""

    print("=" * 70)
    print("TEST HPSDR PACKET HANDLER")
    print("=" * 70)

    # Inizializza handler
    print("\n1. Inizializzazione PacketHandler...")
    try:
        handler = PacketHandler()
        print("   ✓ PacketHandler inizializzato")
    except Exception as e:
        print(f"   ✗ Errore: {e}")
        return False

    # Test discovery request packet (dal client)
    print("\n2. Test Discovery Request packet...")
    try:
        # Discovery request: EFFE02 seguito da zeri
        discovery_request = bytes([0xEF, 0xFE, 0x02]) + bytes(60)

        packet = handler.parse(discovery_request)

        if packet.packet_type == HPSDRPacketType.DISCOVERY:
            print("   ✓ Tipo pacchetto: DISCOVERY")
            print(f"     È response: {packet.is_response}")
            print(f"     MAC address: {packet.mac_address}")

            if not packet.is_response:
                print("   ✓ Correttamente identificato come REQUEST")
            else:
                print("   ✗ Erroneamente identificato come RESPONSE")
                return False
        else:
            print(f"   ✗ Tipo errato: {packet.packet_type}")
            return False
    except Exception as e:
        print(f"   ✗ Errore parsing: {e}")
        return False

    # Test discovery response packet (dalla radio)
    print("\n3. Test Discovery Response packet...")
    try:
        # Discovery response: EFFE02 + MAC address
        mac_bytes = bytes([0x00, 0x1C, 0xC0, 0xA2, 0x12, 0x34])
        discovery_response = bytes([0xEF, 0xFE, 0x02]) + mac_bytes + bytes(54)

        packet = handler.parse(discovery_response)

        if packet.packet_type == HPSDRPacketType.DISCOVERY:
            print("   ✓ Tipo pacchetto: DISCOVERY")
            print(f"     È response: {packet.is_response}")
            print(f"     MAC address: {packet.mac_address}")

            if packet.is_response and packet.mac_address == "00:1c:c0:a2:12:34":
                print("   ✓ Correttamente identificato come RESPONSE con MAC")
            else:
                print("   ✗ MAC address o tipo response errato")
                return False
        else:
            print(f"   ✗ Tipo errato: {packet.packet_type}")
            return False
    except Exception as e:
        print(f"   ✗ Errore parsing: {e}")
        return False

    # Test data packet (Protocol 1)
    print("\n4. Test Data packet (Protocol 1)...")
    try:
        # Data packet: EFFE01 + endpoint + sequence + payload
        data_packet = bytes([0xEF, 0xFE, 0x01, 0x04])  # Endpoint 4
        data_packet += bytes([0x00, 0x01, 0x02, 0x03])  # Sequence
        data_packet += bytes(1024)  # Payload (512 campioni I/Q)

        packet = handler.parse(data_packet)

        if packet.packet_type == HPSDRPacketType.DATA:
            print("   ✓ Tipo pacchetto: DATA")
            print(f"     Endpoint: {packet.endpoint if hasattr(packet, 'endpoint') else 'N/A'}")
            print(f"     Sequence: {packet.sequence if hasattr(packet, 'sequence') else 'N/A'}")
            print(f"     Dimensione: {len(packet.raw_data)} bytes")
        else:
            print(f"   ✗ Tipo errato: {packet.packet_type}")
            return False
    except Exception as e:
        print(f"   ✗ Errore parsing: {e}")
        return False

    # Test pacchetto invalido
    print("\n5. Test pacchetto invalido...")
    try:
        invalid_packet = bytes([0x00, 0x00, 0x00])  # Nessun sync pattern valido

        packet = handler.parse(invalid_packet)

        if packet.packet_type == HPSDRPacketType.UNKNOWN:
            print("   ✓ Pacchetto invalido correttamente identificato come UNKNOWN")
        else:
            print(f"   ⚠ Tipo inaspettato: {packet.packet_type}")
    except Exception as e:
        print(f"   ⚠ Eccezione (accettabile): {e}")

    # Test statistiche
    print("\n6. Test statistiche parser...")
    try:
        stats = handler.get_statistics()
        print("   ✓ Statistiche:")
        print(f"     Totale pacchetti: {stats['total_packets']}")
        print(f"     Discovery: {stats['discovery_packets']}")
        print(f"     Data: {stats['data_packets']}")
        print(f"     Unknown: {stats['unknown_packets']}")
        print(f"     Errori: {stats['error_packets']}")
    except Exception as e:
        print(f"   ✗ Errore statistiche: {e}")
        return False

    # Test generazione discovery request
    print("\n7. Test generazione Discovery Request...")
    try:
        generated = handler.create_discovery_request()
        print(f"   ✓ Discovery request generato ({len(generated)} bytes)")

        # Verifica che sia parsabile
        parsed = handler.parse(generated)
        if parsed.packet_type == HPSDRPacketType.DISCOVERY and not parsed.is_response:
            print("   ✓ Discovery request generato è valido")
        else:
            print("   ✗ Discovery request generato non è valido")
            return False
    except Exception as e:
        print(f"   ✗ Errore generazione: {e}")
        return False

    # Test generazione discovery response
    print("\n8. Test generazione Discovery Response...")
    try:
        test_mac = "00:1C:C0:A2:12:34"
        generated = handler.create_discovery_response(
            mac_address=test_mac,
            board_id=0x06,  # Hermes Lite 2
            firmware_version=0x20
        )
        print(f"   ✓ Discovery response generato ({len(generated)} bytes)")

        # Verifica che sia parsabile
        parsed = handler.parse(generated)
        if parsed.packet_type == HPSDRPacketType.DISCOVERY and parsed.is_response:
            print("   ✓ Discovery response generato è valido")
            print(f"     MAC: {parsed.mac_address}")

            if parsed.mac_address == test_mac.lower():
                print("   ✓ MAC address corretto")
            else:
                print(f"   ✗ MAC address errato: {parsed.mac_address} vs {test_mac.lower()}")
                return False
        else:
            print("   ✗ Discovery response generato non è valido")
            return False
    except Exception as e:
        print(f"   ✗ Errore generazione: {e}")
        return False

    # Test pacchetti di dimensione variabile
    print("\n9. Test pacchetti di dimensioni diverse...")
    try:
        sizes = [63, 512, 1032]  # Dimensioni comuni HPSDR
        for size in sizes:
            test_packet = bytes([0xEF, 0xFE, 0x02]) + bytes(size - 3)
            packet = handler.parse(test_packet)
            print(f"   ✓ Pacchetto da {size} bytes parsato correttamente")
    except Exception as e:
        print(f"   ✗ Errore parsing dimensioni: {e}")
        return False

    print("\n" + "=" * 70)
    print("✓ TUTTI I TEST DEL PACKET HANDLER COMPLETATI")
    print("=" * 70)
    return True


if __name__ == "__main__":
    try:
        result = test_packet_handler()
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n\n⚠ Test interrotto dall'utente")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ ERRORE FATALE: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
