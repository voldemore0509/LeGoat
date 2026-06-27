# -*- coding: utf-8 -*-
"""Configuration centrale de l'application (AppConfig)."""
from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Dict

# ============================================================
# Configuration centrale de l'application
# ============================================================

class AppConfig:
    """
    Configuration statique de Le Goat.

    Tous les réglages globaux (titre, port, thème, modes, modèles…) sont
    centralisés ici pour faciliter la maintenance et la contribution.
    Modifier une valeur ici propage le changement à toute l'application.
    """

    # ── Titres localisés affichés dans l'interface ─────────────
    TITLE_BY_LANG: ClassVar[Dict[str, str]] = {"fr": "Le Goat", "en": "The Goat", "es": "El Goat"}
    DEFAULT_TITLE = "Le Goat"

    # ── Version affichée dans les paramètres ───────────────────
    VERSION = "Goatesque 1.0.1"

    # ── Serveur HTTP local ─────────────────────────────────────
    HOST = "127.0.0.1"   # Ne pas exposer sur le réseau — local uniquement
    PORT = 8765           # Port par défaut ; modifiable via --port

    # ── Paramètres UI par défaut ───────────────────────────────
    DEFAULT_LANG        = "fr"      # Langue : "fr" | "en" | "es"
    DEFAULT_THEME       = "light"   # Thème  : "light" | "dark"
    DEFAULT_EFFECTS     = "on"      # Effets visuels (transitions, ombres)
    DEFAULT_TEXT_SIZE   = "default" # Taille texte : "default" | "large"
    DEFAULT_OPT_RESPONSES = "off"   # Optimisation réponses (désactive modes lourds)
    DEFAULT_UI_OPT      = "off"     # Optimisation UI (désactive sons + effets)
    DEFAULT_KB_SOUND    = "on"      # Son clavier
    DEFAULT_KB_STYLE    = "bulle"   # Style son clavier : "bulle" | "aurela" | "verdrock" | "feryn"
    DEFAULT_CLICK_SOUND = "on"      # Son des boutons
    DEFAULT_CLICK_STYLE = "bulle"   # Style son boutons : "bulle" | "nebrise"
    DEFAULT_AI_SOUND    = "on"      # Son réponse IA
    DEFAULT_CALC_TARGET = "default" # Ciblage des calcules : "cpu" | "gpu" | "default"
    # ── Style d'interface (Paramètres → Apparence) ─────────────
    # "default" : style classique (sans Lumen Mirror).
    # "glass"   : style Lumen Mirror — verre dépoli, animations et finitions soignées.
    DEFAULT_UI_STYLE          = "default"
    # Transparence du Lumen Mirror : 0 = très compact / opaque, 100 = très transparent.
    DEFAULT_GLASS_TRANSPARENCY = 55
    # Si "on", le verre dépoli est teinté par la couleur d'accent choisie.
    DEFAULT_GLASS_TINT        = "off"
    # Boutons pixelisés (clip-path 8 bits) : "on" garde le style pixel, "off" arrondit les boutons.
    DEFAULT_PIXEL_BUTTONS     = "on"
    # Effet d'écriture caractère par caractère pour les réponses IA.
    DEFAULT_AI_TYPING_EFFECT  = "on"

    # ── Préfixe localStorage (évite les collisions entre apps) ─
    STORAGE_PREFIX = "goat"
    # ── Modes disponibles ────────────────────────────────────────
    # Pour ajouter un mode :
    #   1. Ajoutez une entrée {"id": "mon_mode", "icon": "⚡"} ici.
    #   2. Ajoutez les clés de traduction "mode_mon_mode" dans TranslationManager.STRINGS (fr/en/es).
    #   3. Ajoutez "tooltip_mode_mon_mode" dans les traductions.
    #   4. Optionnel : ajoutez l'id dans DISABLED_MODES_OPTIMIZED pour le bloquer en mode optimisé.
    MODE_OPTIONS: ClassVar[list] = [
        {"id": "reflection", "icon": "\u25cc"},   # ◌ Reflection — raisonnement approfondi
        {"id": "fast",       "icon": "\u26a1"},   # ⚡ Fast       — réponse rapide, faible coût
        {"id": "creativity", "icon": "\u2726"},   # ✦ Creativity — style créatif
        # Modes Research — désactivés temporairement (en développement)
        # {"id": "research_in_data",   "icon": "\u25a3"},  # ▣ Research In Data   — RAG sur documents
        # {"id": "research_in_memory", "icon": "\u25cd"},  # ◍ Research In Memory — RAG sur historique
        # {"id": "deep_research",      "icon": "\u2b23"},  # ⬣ Deep Research      — analyse avancée
    ]
    DEFAULT_MODE_ID = ""  # "" = aucun mode sélectionné au démarrage

    # Modes bloqués quand l'optimisation des réponses est activée (Settings)
    DISABLED_MODES_OPTIMIZED: ClassVar[set] = {"reflection"}

    # ── Modèles IA disponibles ───────────────────────────────────
    # Pour ajouter un modèle :
    #   1. Ajoutez une entrée {"id": "...", "label_key": "...", "desc_key": "..."}.
    #   2. Ajoutez les clés dans TranslationManager.STRINGS.
    #   3. Ajoutez sa limite de feuille dans SHEET_LIMITS.
    #   4. Gérez-le dans generate_reply() selon son id.
    MODELS: ClassVar[list] = [
        {"id": "sukoshi", "label_key": "model_sukoshi", "desc_key": "model_sukoshi_desc"},
        {"id": "goat",    "label_key": "model_goat",    "desc_key": "model_goat_desc"},
        {"id": "maestro", "label_key": "model_maestro", "desc_key": "model_maestro_desc"},
    ]
    DEFAULT_MODEL = "goat"  # Modèle sélectionné au premier lancement

    # ── Limites de contexte par modèle (feuilles d'écriture) ────
    # Ajustez ces valeurs selon la fenêtre de contexte réelle de chaque modèle.
    SHEET_LIMITS: ClassVar[Dict[str, int]] = {
        "sukoshi":   4   * 1024,   # ~4 Ko  — modèle compact
        "goat":      6   * 1024,   # ~6 Ko  — modèle léger
        "maestro":   350 * 1024,   # ~350 Ko — modèle lourd, large contexte
    }

    # ── Styles d'écriture ────────────────────────────────────────
    # Pour ajouter un style :
    #   1. Ajoutez une entrée {"id": "...", "icon": "..."} ici.
    #   2. Ajoutez "style_<id>" et "tooltip_style_<id>" dans les traductions.
    WRITING_STYLES: ClassVar[list] = [
        {"id": "explicatif", "icon": "\U0001f4d6"},   # 📖 Style explicatif
        {"id": "educatif",   "icon": "\U0001f393"},   # 🎓 Style éducatif
    ]
    DEFAULT_WRITING_STYLE = ""  # "" = aucun style sélectionné

    # ── Gadgets (fonctionnalités avancées, désactivés pour l'instant) ──
    GADGETS: ClassVar[list] = [
        # {"id": "schema", "icon": "\U0001f4ca"},  # 📊 Génération de schéma visuel
    ]
    DEFAULT_GADGET = ""

    # ── Modèles personnalisés (Settings → Personnalisation) ──────
    # Lorsque l'utilisateur active l'interrupteur "Autres modèles" dans
    # Personnalisation, un bouton "Modèles" apparaît à côté du sélecteur
    # de style d'écriture. Il permet d'ajouter, renommer, supprimer
    # des modèles personnalisés (libellés uniquement, sans backend dédié).
    DEFAULT_OTHER_MODELS_ENABLED = "off"   # "on" | "off"
    # Sentinel utilisé pour marquer que le modèle actif est un modèle custom.
    # Lorsqu'il est posé, l'étiquette du bandeau supérieur affiche "Custom"
    # et la sélection des modèles standards est verrouillée jusqu'au reset.
    CUSTOM_MODEL_SENTINEL = "__custom__"

    # ── Prompt de migration (export mémoire depuis une autre IA) ─
    MIGRATION_PROMPT = r"""Export all of my stored memories and any context you've learned about me from past conversations. Preserve my words verbatim where possible, especially for instructions and preferences.

## Categories (output in this order):

1. **Instructions**: Rules I've explicitly asked you to follow going forward — tone, format, style, "always do X", "never do Y", and corrections to your behavior. Only include rules from stored memories, not from conversations.

2. **Identity**: Name, age, location, education, family, relationships, languages, and personal interests.

3. **Career**: Current and past roles, companies, and general skill areas.

4. **Projects**: Projects I meaningfully built or committed to. Ideally ONE entry per project. Include what it does, current status, and any key decisions. Use the project name or a short descriptor as the first words of the entry.

5. **Preferences**: Opinions, tastes, and working-style preferences that apply broadly.

## Format:

Use section headers for each category. Within each category, list one entry per line, sorted by oldest date first. Format each line as:

[YYYY-MM-DD] - Entry content here.

If no date is known, use [unknown] instead.

## Output:
- Wrap the entire export in a single code block for easy copying.
- After the code block, state whether this is the complete set or if more remain."""

    # ── Chemins de recherche du logo (ordre de priorité) ────────
    LOGO_PATHS: ClassVar[list] = [Path("le_goat.png"), Path("logo_goat.png")]


