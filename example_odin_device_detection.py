"""Example: Detect and read Samsung device in download mode (Odin mode).

This example demonstrates how to use the device package to detect and communicate
with Samsung devices in download mode using the Odin protocol.

Requirements:
    - Samsung device in download mode (Volume Down + Home + Power)
    - Samsung USB drivers installed (Windows)
    - pyserial package

Copyright (c) 2024 nanosamfw contributors
SPDX-License-Identifier: MIT
"""

# pylint: disable=all  # Disable informational messages for this file due to draft code

from device import DeviceNotFoundError, DeviceOdinError, detect_samsung_devices, read_device_info


def main():
    """Detect and read device information from Odin mode device."""
    print("=" * 70)
    print("Samsung Device Detection - Odin Download Mode Protocol")
    print("=" * 70)
    print()
    print("IMPORTANT: Device must be in download mode!")
    print("To enter download mode:")
    print("  1. Power off device completely")
    print("  2. Press and hold: Volume Down + Home + Power")
    print("  3. Press Volume Up when warning appears")
    print("  4. Device should show 'Downloading...' screen")
    print()
    print("-" * 70)

    # Step 1: Detect devices
    print("\n[1] Detecting Samsung devices in download mode...")
    try:
        devices = detect_samsung_devices()
    except (OSError, IOError) as ex:
        print(f"ERROR: Failed to enumerate devices: {ex}")
        return

    if not devices:
        print("ERROR: No Samsung devices found in download mode.")
        print("       Make sure device is in download mode and drivers are installed.")
        return

    print(f"Found {len(devices)} device(s):\n")
    for idx, device in enumerate(devices, 1):
        print(f"  Device {idx}:")
        print(f"    Port:         {device.port_name}")
        print(f"    Name:         {device.device_name}")
        print(f"    Manufacturer: {device.manufacturer}")
        if device.vid and device.pid:
            print(f"    VID:PID:      {device.vid}:{device.pid}")
        print()

    # Step 2: Open persistent connection and verify Odin mode
    selected = devices[0]
    print(f"[2] Opening persistent connection to {selected.port_name}...")

    import serial

    try:
        # Open port once and keep it open for both ODIN and DVIF
        port = serial.Serial(
            port=selected.port_name,
            baudrate=115200,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=2.0,
            rtscts=True,
        )
        # Don't set DTR/RTS - let hardware defaults handle it
        print(f"✓ Port opened: {selected.port_name}")
    except serial.SerialException as ex:
        print(f"ERROR: Failed to open port: {ex}")
        return

    try:
        # Step 3: Verify Odin mode using opened port
        print("\n[3] Verifying Odin mode...")
        import time

        from device.odin_client import LOKE_RESPONSE, ODIN_COMMAND

        port.reset_input_buffer()
        port.write(ODIN_COMMAND)
        time.sleep(0.4)

        bytes_waiting = port.in_waiting
        if bytes_waiting > 0:
            response = port.read(bytes_waiting)
            print(f"Raw response: {response}")
            if LOKE_RESPONSE in response:
                print("✓ Device is in Odin mode (LOKE response received)")
            else:
                print("✗ Device did not respond with LOKE")
                return
        else:
            print("✗ No response from device")
            return

        # Step 4: Read device information using same port
        print("\n[4] Reading device information via DVIF protocol...")
        # Wait a bit after ODIN before sending DVIF
        time.sleep(0.5)
        info = read_device_info(port_instance=port)
    except DeviceNotFoundError:
        print("ERROR: Device not found")
    except DeviceOdinError as ex:
        print(f"ERROR: Failed to read device info: {ex}")
    except ValueError as ex:
        print(f"ERROR: Failed to parse device response: {ex}")
    else:
        # Step 5: Display information (only if successful)
        print("\n" + "=" * 70)
        print("DEVICE INFORMATION (from DVIF protocol)")
        print("=" * 70)
        print()

        if info.model:
            print(f"  Model:          {info.model}")
        if info.product:
            print(f"  Product:        {info.product}")
        if info.fwver:
            print(f"  Firmware:       {info.fwver}")
        if info.sales:
            print(f"  Sales Code:     {info.sales}")
        if info.ver:
            print(f"  Build:          {info.ver}")
        if info.vendor:
            print(f"  Vendor:         {info.vendor}")
        if info.did:
            print(f"  Device ID:      {info.did}")
        if info.un:
            print(f"  Unique Number:  {info.un}")
        if info.capa:
            print(f"  Capability:     {info.capa}")
        if info.tmu_temp:
            print(f"  TMU Temp:       {info.tmu_temp}")
        if info.prov:
            print(f"  Provision:      {info.prov}")

        print()
        print("Raw response:")
        print(f"  {info.raw_response}")
        print()
        print("=" * 70)
        print("Protocol: Odin/LOKE (based on SharpOdinClient)")
        print("=" * 70)
    finally:
        # Always close the port
        if port.is_open:
            port.close()


if __name__ == "__main__":
    main()
