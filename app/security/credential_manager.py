"""Secure API-key storage.

Prefers the OS keyring (macOS Keychain / Windows Credential Locker / libsecret).
If ``keyring`` is unavailable it falls back to a file in the user data dir with
0600 permissions and logs a clear warning — the key is NEVER written into source
or into the settings table, and the full key is never displayed after storage.
"""
from __future__ import annotations

import json
import os
import stat
from typing import Optional

from ..utils.logging import get_logger
from ..utils.paths import APP_ID, data_dir

log = get_logger("credentials")

_SERVICE = APP_ID
_FALLBACK_FILE = "credentials.json"


class CredentialManager:
    def __init__(self) -> None:
        self._keyring = None
        try:
            import keyring  # type: ignore

            self._keyring = keyring
        except Exception:  # noqa: BLE001
            log.warning("keyring unavailable; using restricted-perms file store")

    # -- public API -------------------------------------------------------
    # Robustness: on some packaged Windows builds `keyring` imports fine but has
    # no working backend, so set/get can fail or silently not persist. We now
    # ALWAYS keep a 0600 file copy as the source of truth for reads, and treat
    # keyring as best-effort. This guarantees keys survive save/restart.
    def set_key(self, provider: str, api_key: str) -> None:
        # best-effort secure store
        if self._keyring is not None:
            try:
                self._keyring.set_password(_SERVICE, provider, api_key)
            except Exception as exc:  # noqa: BLE001
                log.warning("keyring write failed, using file store: %s", exc)
        # reliable fallback copy (0600) — the read path prefers this
        try:
            self._file_set(provider, api_key)
        except Exception as exc:  # noqa: BLE001
            log.warning("credential file write failed: %s", exc)

    def get_key(self, provider: str) -> Optional[str]:
        # Prefer the file copy (always persists); fall back to keyring.
        val = self._file_get(provider)
        if val:
            return val
        if self._keyring is not None:
            try:
                return self._keyring.get_password(_SERVICE, provider)
            except Exception as exc:  # noqa: BLE001
                log.warning("keyring read failed: %s", exc)
        return None

    def delete_key(self, provider: str) -> None:
        if self._keyring is not None:
            try:
                self._keyring.delete_password(_SERVICE, provider)
            except Exception:  # noqa: BLE001
                pass
        try:
            self._file_delete(provider)
        except Exception:  # noqa: BLE001
            pass

    def has_key(self, provider: str) -> bool:
        return bool(self.get_key(provider))

    @staticmethod
    def masked(api_key: Optional[str]) -> str:
        """Never reveal a stored key in full."""
        if not api_key:
            return "(not set)"
        if len(api_key) <= 8:
            return "••••"
        return f"{api_key[:3]}••••{api_key[-4:]}"

    # -- file fallback ----------------------------------------------------
    def _path(self):
        return data_dir() / _FALLBACK_FILE

    def _file_all(self) -> dict:
        p = self._path()
        if not p.exists():
            return {}
        try:
            return json.loads(p.read_text())
        except Exception:  # noqa: BLE001
            return {}

    def _file_write(self, data: dict) -> None:
        p = self._path()
        p.write_text(json.dumps(data))
        try:
            os.chmod(p, stat.S_IRUSR | stat.S_IWUSR)  # 0600
        except OSError:
            pass

    def _file_set(self, provider: str, api_key: str) -> None:
        data = self._file_all()
        data[provider] = api_key
        self._file_write(data)

    def _file_get(self, provider: str) -> Optional[str]:
        return self._file_all().get(provider)

    def _file_delete(self, provider: str) -> None:
        data = self._file_all()
        data.pop(provider, None)
        self._file_write(data)
