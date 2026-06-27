# -*- coding: utf-8 -*-
"""Type Message, backend IA (generate_reply) et session de chat."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from .config import AppConfig

# ============================================================
# Types de données
# ============================================================

# Un message est un tuple (expéditeur: str, texte: str)
# Ex. : ("Vous", "Bonjour !") ou ("Le Goat", "Réponse de l'IA")
Message = Tuple[str, str]


# ============================================================
# Backend IA — stub à implémenter
# ============================================================

def generate_reply(message: str, mode: str = "") -> str:
    """
    Point d'entrée principal du backend IA.

    Cette fonction est appelée par ChatSession.submit() et ChatSession.regenerate()
    à chaque fois que l'utilisateur envoie un message.

    Paramètres
    ----------
    message : str
        Le texte envoyé par l'utilisateur (déjà normalisé et non vide).
    mode : str
        L'identifiant du mode actif (ex. "fast", "reflection", "").
        Chaîne vide si aucun mode n'est sélectionné.

    Retour
    ------
    str
        La réponse textuelle à afficher dans l'interface.

    Implémentation suggérée
    -----------------------
    Connectez ici votre backend Ollama, OpenAI, ou tout autre LLM :

        import requests
        def generate_reply(message, mode=""):
            payload = {"model": "mistral", "prompt": message, "stream": False}
            r = requests.post("http://localhost:11434/api/generate", json=payload)
            return r.json()["response"]

    Pour l'instant, cette implémentation renvoie un placeholder.
    """
    return f"[IA non connectée] Votre message : « {message} » (mode : {mode or 'aucun'})"


# ============================================================
# Session de chat
# ============================================================

@dataclass
class ChatSession:
    """
    Gère l'historique d'une conversation et les appels au backend IA.

    Chaque instance représente une session unique (chat standard ou chat privé).
    Les messages sont stockés en mémoire — aucune persistance disque par défaut.

    Attributs
    ---------
    messages : list[Message]
        Historique complet de la conversation (utilisateur + IA).
    metas : list[dict]
        Méta-données parallèles à `messages` (un dict par message).
        Pour un message utilisateur : {"role": "user", "request_ts": ...}
        Pour une réponse IA       : {"role": "assistant", "mode", "style",
                                     "model", "custom_model_name",
                                     "attachments", "request_ts",
                                     "response_ts", "duration_ms"}
        Cette liste alimente le panneau « Spécificité » du frontend.
    last_user_message : str
        Dernier message utilisateur (pour la fonction Relancer).
    last_mode_id / last_style_id / last_model_id / last_custom_model_name :
        Contexte du dernier envoi (réutilisé par regenerate() si non fourni).
    last_attachments : list[dict]
        Pièces jointes du dernier envoi (ré-attachées par regenerate par défaut).
    """
    messages: List[Message] = field(default_factory=list)
    metas: List[dict] = field(default_factory=list)
    last_user_message: str = ""
    last_mode_id: str = ""
    last_style_id: str = ""
    last_model_id: str = ""
    last_custom_model_name: str = ""
    last_attachments: List[dict] = field(default_factory=list)

    @staticmethod
    def _sanitize_attachments(attachments) -> List[dict]:
        """Filtre les pièces jointes pour ne garder que les méta-données utiles
        (nom, type, taille, kind) — les données binaires (dataUrl) sont écartées
        afin de ne pas alourdir le panneau « Spécificité »."""
        result: List[dict] = []
        if not isinstance(attachments, list):
            return result
        for att in attachments:
            if not isinstance(att, dict):
                continue
            result.append({
                "name": str(att.get("name", "") or ""),
                "kind": str(att.get("kind", "") or ""),
                "type": str(att.get("type", "") or ""),
                "size": int(att.get("size") or 0) if str(att.get("size", "")).isdigit() or isinstance(att.get("size"), (int, float)) else 0,
            })
        return result

    def _build_assistant_meta(
        self,
        mode: str,
        style: str,
        model: str,
        custom_model_name: str,
        attachments: List[dict],
        request_ts: float,
        response_ts: float,
    ) -> dict:
        """Construit le dict de méta-données associé à une réponse IA."""
        return {
            "role": "assistant",
            "mode": mode or "",
            "style": style or "",
            "model": model or "",
            "custom_model_name": custom_model_name or "",
            "attachments": list(attachments),
            "request_ts": request_ts,
            "response_ts": response_ts,
            "duration_ms": int(round(max(0.0, response_ts - request_ts) * 1000)),
        }

    def submit(
        self,
        text: str,
        mode: str = "",
        style: str = "",
        model: str = "",
        custom_model_name: str = "",
        attachments: Optional[List[dict]] = None,
    ) -> str:
        """Normalise le texte, l'envoie au backend IA et stocke le résultat.

        Les paramètres additionnels (style, model, attachments…) ne modifient pas
        le comportement de generate_reply() — ils sont conservés à des fins
        d'affichage dans le panneau « Spécificité » côté frontend.
        """
        cleaned = " ".join(text.strip().split())  # Collapse des espaces multiples
        if not cleaned:
            return ""
        attachments_clean = self._sanitize_attachments(attachments)
        self.last_user_message = cleaned
        self.last_mode_id = mode
        self.last_style_id = style
        self.last_model_id = model
        self.last_custom_model_name = custom_model_name
        self.last_attachments = list(attachments_clean)

        request_ts = time.time()
        self.messages.append(("Vous", cleaned))
        self.metas.append({
            "role": "user",
            "request_ts": request_ts,
            "attachments": list(attachments_clean),
        })
        try:
            reply = generate_reply(cleaned, mode)
        except Exception as exc:
            reply = f"Erreur backend IA : {exc}"
        response_ts = time.time()
        self.messages.append((AppConfig.DEFAULT_TITLE, reply))
        self.metas.append(self._build_assistant_meta(
            mode, style, model, custom_model_name,
            attachments_clean, request_ts, response_ts,
        ))
        return reply

    def regenerate(
        self,
        mode: Optional[str] = None,
        style: Optional[str] = None,
        model: Optional[str] = None,
        custom_model_name: Optional[str] = None,
        attachments: Optional[List[dict]] = None,
    ) -> str:
        """Relance le dernier message utilisateur avec un contexte optionnel différent."""
        if not self.last_user_message:
            return ""
        active_mode  = mode  if mode  is not None else self.last_mode_id
        active_style = style if style is not None else self.last_style_id
        active_model = model if model is not None else self.last_model_id
        active_custom = custom_model_name if custom_model_name is not None else self.last_custom_model_name
        active_attachments = (
            self._sanitize_attachments(attachments)
            if attachments is not None else list(self.last_attachments)
        )

        request_ts = time.time()
        try:
            reply = generate_reply(self.last_user_message, active_mode)
        except Exception as exc:
            reply = f"Erreur backend IA : {exc}"
        response_ts = time.time()

        self.last_mode_id = active_mode
        self.last_style_id = active_style
        self.last_model_id = active_model
        self.last_custom_model_name = active_custom
        self.last_attachments = list(active_attachments)

        new_meta = self._build_assistant_meta(
            active_mode, active_style, active_model, active_custom,
            active_attachments, request_ts, response_ts,
        )

        # Remplace la dernière réponse IA si elle existe, sinon l'ajoute
        if self.messages and self.messages[-1][0] != "Vous":
            self.messages[-1] = (AppConfig.DEFAULT_TITLE, reply)
            if self.metas:
                self.metas[-1] = new_meta
            else:
                self.metas.append(new_meta)
        else:
            self.messages.append((AppConfig.DEFAULT_TITLE, reply))
            self.metas.append(new_meta)
        return reply

    def reset(self) -> None:
        """Vide complètement la session (nouvelle discussion)."""
        self.messages.clear()
        self.metas.clear()
        self.last_user_message = ""
        self.last_mode_id = ""
        self.last_style_id = ""
        self.last_model_id = ""
        self.last_custom_model_name = ""
        self.last_attachments = []


