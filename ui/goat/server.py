# -*- coding: utf-8 -*-
"""Serveur HTTP local et couche applicative (GoatWebApp)."""
from __future__ import annotations

import base64
import json
import os
import platform
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import List, Optional

from .config import AppConfig
from .chat import ChatSession
from .assets import LogoLoader
from .template import build_index_html
from .safety import _local_image_safety_check
from .pdf_export import _build_profile_pdf

class GoatWebApp:
    """
    Couche applicative principale — coordonne session et rendu HTML.

    C'est le point d'entrée de toutes les requêtes traitées par
    GoatRequestHandler. Une seule instance est créée au démarrage
    et partagée par tous les threads du serveur.
    """

    def __init__(self) -> None:
        self.session      = ChatSession()               # Session de chat active
        self.logo_uri     = LogoLoader.get_data_uri()   # Logo encodé en base64
        self.themed_logos = LogoLoader.get_themed_logos() # Logos clair/sombre

    def render_index(self) -> str:
        """Génère et retourne la page HTML complète avec l'état actuel."""
        return build_index_html(
            self.logo_uri,
            self.session.messages,
            self.themed_logos,
            metas=self.session.metas,
        )

    def submit_message(
        self,
        message: str,
        mode: str = "",
        style: str = "",
        model: str = "",
        custom_model_name: str = "",
        attachments: Optional[List[dict]] = None,
    ) -> dict:
        """Envoie un message à l'IA et retourne la réponse + historique + métas."""
        reply = self.session.submit(
            message, mode, style, model, custom_model_name, attachments,
        )
        if not reply:
            return {"ok": False, "error": "Veuillez saisir un message."}
        return {
            "ok": True,
            "reply": reply,
            "messages": self.session.messages,
            "metas": self.session.metas,
        }

    def regenerate(
        self,
        mode: str = "",
        style: Optional[str] = None,
        model: Optional[str] = None,
        custom_model_name: Optional[str] = None,
        attachments: Optional[List[dict]] = None,
    ) -> dict:
        """Relance le dernier message et retourne la nouvelle réponse + métas."""
        reply = self.session.regenerate(
            mode, style, model, custom_model_name, attachments,
        )
        if not reply:
            return {"ok": False, "error": "Aucun message à relancer."}
        return {
            "ok": True,
            "reply": reply,
            "messages": self.session.messages,
            "metas": self.session.metas,
        }

    def new_chat(self) -> dict:
        """Réinitialise la session et retourne un historique vide."""
        self.session.reset()
        return {
            "ok": True,
            "messages": self.session.messages,
            "metas": self.session.metas,
        }

    def moderate_profile_image(self, filename: str, data_url: str) -> dict:
        safe, reason = _local_image_safety_check(filename, data_url)
        return {"ok": True, "safe": safe, "reason": reason}

    def export_profile_pdf(self, payload: dict) -> dict:
        profile = payload.get('profile', {}) if isinstance(payload, dict) else {}
        if not isinstance(profile, dict):
            profile = {}
        chat_count = int(payload.get('chatCount', 0) or 0)
        goat_score = int(payload.get('goatScore', 0) or 0)
        include_score = bool(payload.get('includeScore', False))
        try:
            pdf_bytes = _build_profile_pdf(profile, chat_count, goat_score, include_score)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        full_name = ' '.join([str(profile.get('firstname') or '').strip(), str(profile.get('lastname') or '').strip()]).strip() or 'profil-goat'
        label = 'profil-complet' if include_score else 'profil-professionnel'
        filename = f"{_sanitize_pdf_filename(full_name)}-{label}.pdf"
        return {"ok": True, "data": base64.b64encode(pdf_bytes).decode('ascii'), "filename": filename}

    def trigger_profile_screenshot(self) -> dict:
        """Déclenche l'outil de capture Windows (Win + Shift + S)."""
        if platform.system().lower() != 'windows':
            return {"ok": True, "triggered": False}
        try:
            import ctypes
            user32 = ctypes.windll.user32
            KEYEVENTF_KEYUP = 0x0002
            VK_LWIN = 0x5B
            VK_SHIFT = 0x10
            S_KEY = 0x53
            user32.keybd_event(VK_LWIN, 0, 0, 0)
            user32.keybd_event(VK_SHIFT, 0, 0, 0)
            time.sleep(0.02)
            user32.keybd_event(S_KEY, 0, 0, 0)
            time.sleep(0.02)
            user32.keybd_event(S_KEY, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
            return {"ok": True, "triggered": True}
        except Exception:
            return {"ok": True, "triggered": False}

    def trigger_voice_shortcut(self) -> dict:
        if platform.system().lower() != 'windows':
            return {"ok": True, "triggered": False}
        try:
            import ctypes
            user32 = ctypes.windll.user32
            KEYEVENTF_KEYUP = 0x0002
            VK_LWIN = 0x5B
            H_KEY = 0x48
            user32.keybd_event(VK_LWIN, 0, 0, 0)
            time.sleep(0.02)
            user32.keybd_event(H_KEY, 0, 0, 0)
            time.sleep(0.02)
            user32.keybd_event(H_KEY, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
            return {"ok": True, "triggered": True}
        except Exception:
            return {"ok": True, "triggered": False}

    def open_app_folder(self) -> dict:
        """
        Ouvre l'explorateur de fichiers sur le dossier contenant ce programme
        (Fichier → Emplacement du/des programmes dans la barre de menu).
        Multi-plateforme : Windows (explorer), macOS (open), Linux (xdg-open).
        """
        try:
            folder = os.path.dirname(os.path.abspath(__file__))
        except Exception:
            folder = os.getcwd()
        if not os.path.isdir(folder):
            return {"ok": False, "error": "Dossier du programme introuvable."}
        try:
            system = platform.system().lower()
            if system == 'windows':
                # startfile ouvre le dossier dans l'explorateur Windows.
                os.startfile(folder)  # type: ignore[attr-defined]
            elif system == 'darwin':
                import subprocess
                subprocess.Popen(['open', folder])
            else:
                import subprocess
                subprocess.Popen(['xdg-open', folder])
            return {"ok": True, "folder": folder}
        except Exception as exc:
            return {"ok": False, "error": f"Impossible d'ouvrir le dossier : {exc}"}


class GoatHTTPServer(ThreadingHTTPServer):
    """
    Serveur HTTP multi-thread qui expose l'instance GoatWebApp aux handlers.

    L'attribut `app` est accessible depuis GoatRequestHandler via self.server.app.
    ThreadingHTTPServer gère chaque requête dans un thread séparé.
    """

    def __init__(self, addr: tuple, handler_cls, app: GoatWebApp) -> None:
        super().__init__(addr, handler_cls)
        self.app = app  # Partagé entre tous les threads — ChatSession n'est pas thread-safe


class GoatRequestHandler(BaseHTTPRequestHandler):
    """
    Handler HTTP — route les requêtes vers GoatWebApp.

    Routes disponibles
    ------------------
    GET  /              → page HTML complète (render_index)
    GET  /api/history   → historique JSON de la session
    POST /api/send      → envoyer un message {message, mode}
    POST /api/regenerate→ relancer le dernier message {mode}
    POST /api/new_chat  → réinitialiser la session {}

    Pour ajouter une route :
      - GET  : ajoutez un elif dans do_GET()
      - POST : ajoutez une entrée lambda dans le dict handlers de do_POST()
    """

    server: GoatHTTPServer  # Typage pour accès à self.server.app

    def log_message(self, fmt, *args) -> None:
        pass  # Silence les logs HTTP dans la console (trop verbeux)

    def _send(self, body: str, status: int = 200, ct: str = "text/html; charset=utf-8") -> None:
        """Envoie une réponse HTTP texte avec les headers appropriés."""
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, payload: dict, status: int = 200) -> None:
        """Sérialise un dict en JSON et l'envoie comme réponse HTTP."""
        self._send(json.dumps(payload, ensure_ascii=False), status, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        """Gère toutes les requêtes GET."""
        if self.path == "/":
            self._send(self.server.app.render_index())
        elif self.path == "/api/history":
            self._json({
                "ok": True,
                "messages": self.server.app.session.messages,
                "metas": self.server.app.session.metas,
            })
        elif self.path in {"/favicon.ico", "/favicon.png"}:
            self.send_response(204)
            self.end_headers()
        else:
            self._json({"ok": False, "error": "Not found."}, 404)

    def do_POST(self) -> None:
        """Gère toutes les requêtes POST via un dispatch par chemin."""
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
            if not isinstance(payload, dict):
                payload = {}
        except json.JSONDecodeError:
            self._json({"ok": False, "error": "JSON invalide."}, 400)
            return

        # Pièces jointes : on n'accepte qu'une liste de dicts pour éviter
        # qu'un payload mal formé ne fasse planter le sanitizer.
        raw_attachments = payload.get("attachments")
        attachments_list = raw_attachments if isinstance(raw_attachments, list) else None

        handlers = {
            "/api/send":       lambda: self.server.app.submit_message(
                                   str(payload.get("message", "")),
                                   str(payload.get("mode", "")),
                                   str(payload.get("style", "")),
                                   str(payload.get("model", "")),
                                   str(payload.get("customModelName", "")),
                                   attachments_list,
                               ),
            "/api/regenerate": lambda: self.server.app.regenerate(
                                   str(payload.get("mode", "")),
                                   payload.get("style") if "style" in payload else None,
                                   payload.get("model") if "model" in payload else None,
                                   payload.get("customModelName") if "customModelName" in payload else None,
                                   attachments_list if "attachments" in payload else None,
                               ),
            "/api/new_chat":   lambda: self.server.app.new_chat(),
            "/api/moderate_profile_image": lambda: self.server.app.moderate_profile_image(
                                   str(payload.get("filename", "")),
                                   str(payload.get("dataUrl", ""))
                               ),
            "/api/export_profile_pdf": lambda: self.server.app.export_profile_pdf(payload),
            "/api/profile_screenshot": lambda: self.server.app.trigger_profile_screenshot(),
            "/api/voice_shortcut": lambda: self.server.app.trigger_voice_shortcut(),
            "/api/open_app_folder": lambda: self.server.app.open_app_folder(),
        }

        fn = handlers.get(self.path)
        if fn:
            result = fn()
            self._json(result, 200 if result.get("ok") else 400)
        else:
            self._json({"ok": False, "error": "Not found."}, 404)


