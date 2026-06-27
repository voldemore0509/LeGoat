# -*- coding: utf-8 -*-
"""Chargement des logos et images (LogoLoader)."""
from __future__ import annotations

import base64
import re
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .config import AppConfig

# Racine du projet (dossier contenant ui.py, Logo/, PhotoProfile/, Banniere/).
# assets.py se trouve dans goat/, donc la racine est le dossier parent.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================
# Chargement des ressources graphiques
# ============================================================

class LogoLoader:
    """
    Charge les logos de l'application sous forme de data URI base64
    pour les injecter directement dans le HTML (pas de fichier statique servi).

    Priorité de recherche pour le logo principal :
      AppConfig.LOGO_PATHS → dossier du script → répertoire courant
    """
    @classmethod
    def get_data_uri(cls, paths: Optional[Sequence[Path]] = None) -> str:
        """Retourne un data URI base64 du logo principal, ou un SVG de secours."""
        search = list(paths) if paths else cls._build_search_paths()
        for p in search:
            try:
                if p.is_file():
                    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
                    return f"data:image/png;base64,{b64}"
            except OSError:
                continue
        return cls._fallback_svg()  # Logo SVG généré si aucun fichier trouvé

    @classmethod
    def _build_search_paths(cls) -> List[Path]:
        """Construit la liste des chemins de recherche sans doublons."""
        base = _PROJECT_ROOT
        cwd = Path.cwd()
        seen, result = set(), []
        for p in [*AppConfig.LOGO_PATHS, base / "le_goat.png", cwd / "le_goat.png"]:
            key = str(p)
            if key not in seen:
                seen.add(key)
                result.append(p)
        return result

    @classmethod
    def _load_file_as_data_uri(cls, filepath: Path) -> str:
        """Charge un fichier image et retourne un data URI base64, ou "" si absent."""
        try:
            if filepath.is_file():
                b64 = base64.b64encode(filepath.read_bytes()).decode("ascii")
                return f"data:image/png;base64,{b64}"
        except OSError:
            pass
        return ""

    @classmethod
    def get_icon_path(cls) -> Optional[str]:
        """
        Retourne le chemin absolu de l'icône pour la fenêtre native pywebview.

        Ordre de priorité :
          .ico (recommandé Windows) → PNG depuis dossier Logo → PNG racine
        """
        base = _PROJECT_ROOT
        logo_dir = base / "Logo"
        candidates = [
            base / "le_goat.ico",                          # .ico optimal taskbar Windows
            base / "logo_goat.ico",
            logo_dir / "le_goat.ico",
            logo_dir / "Image_LeGoat_FondBlanc.png",       # PNG clair (fallback)
            logo_dir / "Image_LeGoat_FondNoire.png",
            base / "le_goat.png",
            base / "logo_goat.png",
        ]
        for p in candidates:
            try:
                if p.is_file():
                    return str(p)
            except OSError:
                continue
        return None

    @classmethod
    def get_themed_logos(cls) -> Dict[str, str]:
        """Charge les logos LeGoat et Goatistique pour les thèmes clair et sombre."""
        base = _PROJECT_ROOT
        logo_dir = base / "Logo"
        return {
            "legoat_light":       cls._load_file_as_data_uri(logo_dir / "Image_LeGoat_FondBlanc.png"),
            "legoat_dark":        cls._load_file_as_data_uri(logo_dir / "Image_LeGoat_FondNoire.png"),
            "legoat_pixel_light": cls._load_file_as_data_uri(logo_dir / "Image_LeGoat_Pixel_FondBlanc.png"),
            "legoat_pixel_dark":  cls._load_file_as_data_uri(logo_dir / "Image_LeGoat_Pixel_FondNoir.png"),
            "goatistique_light":  cls._load_file_as_data_uri(logo_dir / "Logo Goatistique fond blanc.png"),
            "goatistique_dark":   cls._load_file_as_data_uri(logo_dir / "logo goatistique fond noire.png"),
        }

    @classmethod
    def get_profile_presets(cls) -> Dict[str, list]:
        """
        Charge les images de profil et de bannière depuis les dossiers
        PhotoProfile/ et Bannière/ et les retourne comme des listes de
        dicts {id, label, src} prêtes à être injectées en JSON dans le JS.
        """
        base = _PROJECT_ROOT
        avatar_dir = base / "PhotoProfile"
        banner_dir = base / "Bannière"
        avatars = []
        banners = []
        # Chargement des photos de profil
        if avatar_dir.is_dir():
            for img_path in sorted(avatar_dir.iterdir()):
                if img_path.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'):
                    data_uri = cls._load_file_as_data_uri(img_path)
                    if data_uri:
                        label = img_path.stem  # Nom sans extension
                        safe_id = re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')
                        avatars.append({"id": safe_id, "label": label, "src": data_uri})
        # Chargement des bannières
        if banner_dir.is_dir():
            for img_path in sorted(banner_dir.iterdir()):
                if img_path.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'):
                    data_uri = cls._load_file_as_data_uri(img_path)
                    if data_uri:
                        label = img_path.stem
                        safe_id = re.sub(r'[^a-z0-9]+', '-', label.lower()).strip('-')
                        banners.append({"id": safe_id, "label": label, "src": data_uri})
        return {"avatars": avatars, "banners": banners}

    @staticmethod
    def _fallback_svg() -> str:
        """SVG minimaliste généré si aucun fichier logo n'est trouvé."""
        svg = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 128 128'><defs><linearGradient id='g' x1='0%' y1='0%' x2='100%' y2='100%'><stop offset='0%' stop-color='#19b7ff'/><stop offset='100%' stop-color='#2f5bff'/></linearGradient></defs><rect width='128' height='128' rx='28' fill='#050816'/><circle cx='44' cy='46' r='9' fill='url(#g)'/><circle cx='84' cy='46' r='9' fill='url(#g)'/><path d='M34 84c9-10 18-15 30-15s21 5 30 15' fill='none' stroke='url(#g)' stroke-width='10' stroke-linecap='round'/></svg>"
        import urllib.parse
        return "data:image/svg+xml," + urllib.parse.quote(svg)


