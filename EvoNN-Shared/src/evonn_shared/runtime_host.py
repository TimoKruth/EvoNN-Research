"""Stable, versioned host identity; network names never identify new runs."""
import hashlib
import json
from pathlib import Path
import platform
import plistlib
import subprocess
import uuid

PREFIX = "machine-v1:"


def _machine_id(system):
    if system == "Darwin":
        result = subprocess.run(["/usr/sbin/ioreg", "-rd1", "-c", "IOPlatformExpertDevice", "-a"],
                                capture_output=True, timeout=3, check=True)
        return plistlib.loads(result.stdout)[0]["IOPlatformUUID"]
    if system == "Linux":
        for path in (Path("/etc/machine-id"), Path("/var/lib/dbus/machine-id")):
            if path.is_file():
                return path.read_text().strip()
        raise ValueError("OS machine ID unavailable")
    if system == "Windows":
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography",
                            0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            return winreg.QueryValueEx(key, "MachineGuid")[0]
    raise ValueError("Unsupported OS for stable machine identity")


def machine_token():
    system = platform.system()
    try:
        identifier = uuid.UUID(_machine_id(system).strip())
        if identifier.int in (0, (1 << 128) - 1):
            raise ValueError("Unprovisioned machine ID")
    except (OSError, ValueError, KeyError, IndexError, TypeError, AttributeError,
            subprocess.SubprocessError, plistlib.InvalidFileException):
        # Never include raw hardware identifiers or command output in errors.
        raise ValueError("Stable machine identity unavailable; refusing hostname fallback") from None
    payload = f"evonn-machine-v1\0{system}\0{identifier.hex}".encode()
    return PREFIX + hashlib.sha256(payload).hexdigest()


def host_fields():
    return {"host": machine_token(), "system": platform.system(),
            "machine": platform.machine(), "processor": platform.processor()}


if __name__ == "__main__":
    print(json.dumps(host_fields()))
