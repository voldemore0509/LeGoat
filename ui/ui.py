# -*- coding: utf-8 -*-
"""
Le Goat — Interface desktop native (Goatistique)
=================================================
Application desktop monopage basée sur pywebview + serveur HTTP local.
Toute l'UI (HTML/CSS/JS) est générée et servie en mémoire — aucun fichier
statique externe n'est nécessaire.

Architecture
------------
┌─────────────────────────────────────────────┐
│  main()                                     │
│    └─ GoatHTTPServer  (ThreadingHTTPServer) │
│         └─ GoatRequestHandler               │
│              └─ GoatWebApp                  │
│                   ├─ ChatSession            │
│                   └─ build_index_html()     │
└─────────────────────────────────────────────┘

Flux d'une requête
------------------
  Utilisateur → pywebview → localhost:8765 → GoatRequestHandler
  → GoatWebApp.submit_message() → ChatSession.submit()
  → generate_reply() [backend IA — à implémenter]
  → réponse JSON → JS frontend → rendu HTML

Pour les développeurs — points d'extension
-------------------------------------------
  • Ajouter un MODE       → AppConfig.MODE_OPTIONS + traductions
  • Ajouter un MODÈLE     → AppConfig.MODELS + traductions
  • Ajouter un STYLE      → AppConfig.WRITING_STYLES + traductions
  • Brancher l'IA         → implémenter generate_reply() (voir stub ci-dessous)
  • Changer le port       → AppConfig.PORT
  • Changer la langue par défaut → AppConfig.DEFAULT_LANG

Dépendances
-----------
  pip install pywebview          # fenêtre desktop native (optionnel, fallback navigateur)
  # Le reste n'utilise que la stdlib Python (http.server, threading, json…)

Usage
-----
  python ui.py                   # fenêtre native
  python ui.py --browser         # ouvrir dans le navigateur
  python ui.py --no-browser      # serveur pur (API uniquement)
  python ui.py --test            # lancer la suite de tests

Auteur  : Goatistique / Longan AI
Version : voir AppConfig.VERSION
"""

from __future__ import annotations

import argparse
import base64
import html
import io
import json
import os
import platform
import re
import threading
import time
import unittest
try:
    import webview
except ImportError:
    webview = None
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    from PIL import Image
except Exception:
    Image = None

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as pdf_canvas
except Exception:
    A4 = None
    ImageReader = None
    pdf_canvas = None


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


# ============================================================
# Traductions (i18n)
# ============================================================

class TranslationManager:
    """
    Gestion des traductions de l'interface.

    Pour ajouter une langue :
      1. Ajoutez une entrée dans STATUS, WELCOME et STRINGS avec la clé
         ISO 639-1 de la langue (ex. "de" pour l'allemand).
      2. Ajoutez la langue dans AppConfig.TITLE_BY_LANG.
      3. Dans le JS, ajoutez le bouton de langue dans le HTML des paramètres.

    Pour ajouter une clé de traduction :
      Ajoutez-la dans chaque bloc linguistique (fr / en / es) avec la même clé.
      Le JS accède aux chaînes via la fonction t('ma_cle').
    """
    STATUS: ClassVar[Dict[str, str]] = {
        "fr": "Le Goat peut commettre des erreurs , vérifier ses réponse avec d'autre ia en cas doute.",
        "en": "The Goat can make mistakes. Cross-check its answers with other AIs if you have any doubt.",
        "es": "El Goat puede cometer errores. Verifique sus respuestas con otras IA si tiene dudas.",
    }
    WELCOME: ClassVar[Dict[str, list]] = {
        "fr": ["Par quoi commençons-nous ?", "Que voulez-vous explorer aujourd'hui ?", "Prêt à lancer la prochaine étape ?", "Sur quoi voulez-vous que Le Goat travaille ?", "Que souhaitez-vous vérifier ou rechercher ?", "On commence par quelle mission ?", "Prêt à faire avancer le projet ?"],
        "en": ["Where should we start?", "What would you like to explore today?", "Ready to launch the next step?", "What should The Goat work on?", "What would you like to verify or search for?", "Which mission do we start with?", "Ready to move the project forward?"],
        "es": ["¿Por dónde empezamos?", "¿Qué quiere explorar hoy?", "¿Listo para lanzar la siguiente etapa?", "¿En qué quiere que trabaje El Goat?", "¿Qué quiere verificar o buscar?", "¿Con qué misión empezamos?", "¿Listo para hacer avanzar el proyecto?"],
    }
    STRINGS: ClassVar[Dict[str, dict]] = {
        "fr": {
            "placeholder": "Demandez à Le Goat...", "settings_label": "Paramètres", "settings_title": "Paramètres",
            "settings_subtitle": "Configuration locale de Le Goat",
            "tab_general": "Générale", "tab_personalization": "Personnalisation",
            "tab_data_security": "Gestion de donnée et sécurité", "tab_optimization": "Optimisation et Performances",
            "general_language": "Langue", "general_version": "Version", "general_theme": "Thème",
            "general_text_size": "Taille du texte", "general_app_scale": "Taille du logiciel", "general_app_scale_hint": "Agrandit ou réduit toute l'interface.", "tab_appearance": "Apparence", "appearance_color": "Couleur de l'interface", "appearance_wallpaper": "Fond d'écran", "appearance_wallpaper_normal": "Fond d'écran du mode normal", "appearance_wallpaper_coworking": "Fond d'écran de Goat Code", "appearance_change": "Changer", "appearance_remove": "Retirer", "appearance_modal_title": "Fond d'écran", "appearance_import_image": "Importer une image", "appearance_import_video": "Importer une vidéo", "appearance_video_volume": "Volume de la vidéo", "appearance_video_help": "Vidéo en boucle pour l’arrière-plan.", "appearance_video_import_warning": "Plus la vidéo est longue et de bonne qualité, plus l’import prendra du temps et risque de faire laguer le logiciel.", "appearance_preview": "Aperçu", "color_blue": "Bleu", "color_red": "Rouge", "color_green": "Vert", "color_yellow": "Jaune", "color_pink": "Rose", "color_purple": "Violet", "general_keyboard_sounds": "Son du clavier",
            "general_keyboard_sound_style": "Style du son clavier", "general_click_sounds": "Son des boutons",
            "general_click_sound_style": "Style du son boutons", "general_ai_reply_sounds": "Son réponse IA",
            "language_fr": "Français", "language_en": "Anglais", "language_es": "Espagnol",
            "theme_light": "Claire", "theme_dark": "Sombre",
            "theme_description": "Choisissez l'apparence globale de l'interface.",
            "text_size_default": "Par défaut", "text_size_large": "Grand",
            "sound_on": "Activer", "sound_off": "Désactiver",
            "sound_style_bulle": "Bulle", "sound_style_aurela": "Aurela",
            "sound_style_verdrock": "Verdrock", "sound_style_feryn": "Feryn", "sound_style_nebrise": "Nebrise",
            "personalization_name": "Prénom", "personalization_surname": "Nom",
            "personalization_tone": "Ton de l'IA", "personalization_info": "Informations sur vous",
            "personalization_placeholder": "Ex. préférences, contraintes, contexte utile…",
            "placeholder_firstname": "Entrez votre prénom", "placeholder_lastname": "Entrez votre nom",
            "placeholder_tone": "Ex. professionnel, détendu, direct…",
            "perso_how_address": "Comment l'IA s'adresse à vous",
            "perso_how_address_help": "Prénom, surnom, ou titre que l'IA utilisera.",
            "perso_ai_tone": "Ton de l'IA",
            "perso_ai_tone_help": "Décrivez comment vous voulez que l'IA vous parle.",
            "data_security_memory": "Gérer la mémoire", "data_security_history": "Gérer l'historique des discussions",
            "optimization_effects": "Optimiser les effets visuels", "optimization_responses": "Optimiser les réponses",
            "optimization_ram": "Libération de la mémoire vive de l'IA",
            "optimization_ram_hint": "Libère la mémoire de la discussion en cours — l'IA ne se souviendra plus des échanges de cette session.",
            "optimization_calc_target": "Ciblage des calcules",
            "optimization_calc_target_hint": "Choisissez le canal de calcul privilégié pour les traitements lourds.",
            "calc_target_cpu": "CPU (Ram)",
            "calc_target_gpu": "GPU (Vram)",
            "calc_target_default": "Par défaut (Utiliser les 2 espaces)",
            "calc_target_notify_cpu": "Mode CPU activé — L'IA se concentrera uniquement sur le CPU (RAM). Cela bridera les performances et pourra désactiver certains modèles comme Maestro.",
            "calc_target_notify_gpu": "Mode GPU activé — L'IA se concentrera uniquement sur le GPU (VRAM). Cela bridera les performances et pourra désactiver certains modèles comme Maestro.",
            "calc_target_notify_default": "Mode par défaut activé — L'intégralité de la puissance du PC sera utilisée sans brider aucun modèle.",
            "state_on": "Activé", "state_off": "Désactivé",
            "mode_active_prefix": "Mode actif :", "no_mode": "Aucun mode",
            "close": "Fermer", "settings_hint": "Astuce : vous pouvez déplacer cette fenêtre avec la souris.",
            "new_chat": "Nouvelle discussion",
            "new_chat_confirm": "La discussion actuelle sera supprimée et irrécupérable. Continuer ?",
            "tab_switch_confirm": "Changer d'espace va réinitialiser la discussion en cours. Continuer ?",
            "regenerate": "Relancer", "soon": "Bientôt disponible.",
            "specificity": "Spécificité",
            "tooltip_specificity": "Voir le détail de la requête (mode, style, modèle, pièces jointes, horodatage…).",
            "specificity_title": "Spécificités de la réponse",
            "specificity_mode": "Mode utilisé",
            "specificity_style": "Style d'écriture",
            "specificity_model": "Modèle utilisé",
            "specificity_attachments": "Documents et images",
            "specificity_request_time": "Envoi de la requête",
            "specificity_response_time": "Réception de la réponse",
            "specificity_duration": "Temps de réponse",
            "specificity_none": "Aucun",
            "specificity_no_attachments": "Aucun document ou image joint",
            "specificity_unavailable": "Aucune information disponible.",
            "specificity_seconds_short": "s",
            "specificity_milliseconds_short": "ms",
            "specificity_custom_model": "Modèle personnalisé",
            "sidebar_search_placeholder": "Rechercher une discussion…",
            "sidebar_pinned": "Épinglés",
            "sidebar_pinned_empty": "Glissez pour épingler",
            "sidebar_tab_files": "Fichiers",
            "sidebar_tab_history": "Historique",
            "sidebar_create_file": "Créer un fichier",
            "sidebar_history_empty": "Aucune discussion pour l'instant.",
            "attach_image": "Image",
            "attach_image_hint": "Joindre une image (PNG, JPG, GIF…)",
            "attach_file": "Fichier",
            "attach_file_hint": "Joindre n'importe quel fichier",
            "mode_reflection": "Reflection", "mode_fast": "Fast",
            "mode_research_in_data": "Research In Data", "mode_research_in_memory": "Research In Memory",
            "mode_creativity": "Creativity", "mode_deep_research": "Deep Research",
            "model_sukoshi": "Sukoshi", "model_goat": "Traditionnel", "model_maestro": "Maestro", "model_goat_code": "Goat Code",
            "model_sukoshi_desc": "Modèle compact et rapide.",
            "model_goat_desc": "Modèle traditionnel, équilibré et polyvalent.",
            "model_maestro_desc": "IA plus lourde, apte à traiter des tâches complexes et de grande envergure.",
            "model_goat_code_desc": "Modèle fait pour la génération de code, correction de code et analyse de code.",
            "model_label": "Modèle", "model_recent": "Le plus récent",
            "tooltip_send": "Envoyer le message (Entrée).", "tooltip_settings": "Ouvrir les paramètres.",
            "tooltip_new_chat": "Démarrer une nouvelle discussion (supprime l'actuelle).",
            "tooltip_sidebar": "Ouvrir / fermer le panneau latéral.",
            "tooltip_regenerate": "Relancer la réponse de l'IA.",
            "tooltip_mode_fast": "Réponse rapide, faible coût.",
            "tooltip_mode_reflection": "Réflexion plus profonde (plus lent).",
            "tooltip_mode_research_in_data": "Recherche dans vos documents (RAG).",
            "tooltip_mode_research_in_memory": "Recherche dans la mémoire/historique (plus coûteux).",
            "tooltip_mode_creativity": "Style plus créatif, plus de variabilité.",
            "tooltip_mode_deep_research": "Deep research (analyse avancée, plus lent).",
            "tooltip_mode_trigger": "Sélectionner un mode (re-cliquez pour désélectionner).",
            "review_code": "Relire le code",
            "execute_code": "Exécuter le code",
            "tooltip_execute_code": "Exécute en simulation avec une logique algorithmique pour voir si le code devrait bien fonctionner.",
            "add_sheet": "Ajouter des données écrites",
            "tooltip_plus_btn": "Ajouter des données extérieures à l'IA.",
            "sheet_title": "Feuille d'écriture",
            "sheet_add": "Ajouter", "sheet_cancel": "Annuler",
            "sheets_max": "Maximum 10 feuilles atteint.",
            "sheet_too_large": "Cette feuille dépasse la limite de {limit} pour le modèle actuel.",
            "private_chat": "Chat Privé",
            "private_chat_desc": "Cette discussion ne sera pas sauvegardée dans l'historique.",
            "private_chat_welcome": "Chat Privé Activé",
            "private_chat_welcome_desc": "Les informations entrées ne seront et ne pourront pas être sauvegardées dans l'historique ou la mémoire.",
            "writing_style_label": "Style d'écriture", "no_style": "Aucun style",
            "style_explicatif": "Explicatif", "style_educatif": "Éducatif",
            "tooltip_style_explicatif": "Permet d'être dans un style plus explicatif, bien pour l'école ou l'explication d'un dossier.",
            "tooltip_style_educatif": "Idéal pour apprendre une notion ou quelque chose de nouveau.",
            "tooltip_style_trigger": "Sélectionner un style d'écriture (re-cliquez pour désélectionner).",
            # ── Modèles personnalisés ───────────────────────────
            "perso_other_models": "Autres modèles",
            "perso_other_models_help": "Active la possibilité d'ajouter et de gérer vos propres modèles.",
            "tooltip_other_models_toggle": "Active la possibilité d'ajouter d'autres modèles que ceux d'origine.",
            "models_btn_label": "Modèles",
            "tooltip_models_trigger": "Gérer et activer vos modèles personnalisés.",
            "models_add": "Ajouter un modèle",
            "models_modal_title": "NAME Models",
            "models_modal_placeholder": "Nom du modèle",
            "models_modal_enter": "Entrer",
            "models_modal_cancel": "Annuler",
            "models_no_custom": "Aucun modèle personnalisé pour l'instant.",
            "models_custom_label": "Custom",
            "models_rename": "Renommer",
            "models_delete": "Supprimer",
            "models_set_default": "Remettre le modèle par défaut",
            "models_default_required": "Pour repasser sur Sukoshi, Traditionnel ou Maestro, remettez d'abord le modèle sur « Par défaut ».",
            "models_delete_confirm": "Supprimer ce modèle personnalisé ?",
            "models_invalid_name": "Le nom du modèle ne peut pas être vide.",
            "models_duplicate_name": "Un modèle porte déjà ce nom.",
            "analyze_code": "Analyser le code",
            "update_info": "Voir les informations de mise à jour",
            "dev_notes": "Voir les notes de développement",
            "migrate_data": "Migrer les données",
            "migrate_title": "Migrer les données vers Le Goat",
            "migrate_step1": "1. Copiez ce prompt dans une conversation avec votre autre IA.",
            "migrate_step2": "2. Collez les résultats ci-dessous pour les ajouter à la mémoire de Le Goat.",
            "migrate_paste_placeholder": "Collez les détails de votre mémoire ici.",
            "migrate_add": "Ajouter les données à l'IA",
            "migrate_cancel": "Annuler",
            "migrate_copy": "Copier",
            "migrate_success": "Les données ont bien été importées.",
            "gadget_label": "Gadget", "no_gadget": "Aucun gadget",
            "gadget_schema": "Schéma",
            "tooltip_gadget_schema": "Génère un schéma visuel à partir de votre demande.",
            "tooltip_gadget_trigger": "Sélectionner un gadget (re-cliquez pour désélectionner).",
            "tab_goat_dev": "Goat Developer",
            "goat_dev_news": "Information sur les nouveautés de développement",
            "goat_dev_news_desc": "Découvrez les dernières fonctionnalités et améliorations.",
            "goat_dev_about": "En savoir plus sur Goat Developer",
            "goat_dev_about_desc": "L'équipe et la vision derrière Le Goat.",
            "thanks_message": "Designed and coded in France",
            "char_limit_tooltip": "Limite de caractères que l'IA peut analyser en une seule requête.",
            "char_limit_overclock_tooltip": "Overclocking activé — Attention en dépassant la limite, les réponses peuvent être dégradées.",
            "sheets_max_one": "Maximum 1 feuille atteint. Activez l'overclocking pour en ajouter jusqu'à 10.",
            "sheet_char_limit": "Limite : 14 000 caractères",
            "contraction_label": "Contraction Of Chat",
            "contraction_tooltip": "Mode Contraction Of Chat activé : le total de caractères dépasse 10 000. Les réponses seront compressées.",
            "overclock_label": "Overclocking IA",
            "overclock_subtitle": "Débride la limite de caractères pour des requêtes plus volumineuses.",
            "overclock_warning": "En activant l'overclocking, vous allez débrider la limite de caractères et pousser l'IA au-delà de ses limites nominales. Cela peut être bénéfique pour des requêtes plus volumineuses mais peut également rendre les réponses beaucoup plus longues, et dans certains cas de surcharge, rendre les réponses non générables ou fragmentées. Prendre le risque de débrider cette limite peut engendrer des réponses incomplètes, de moindre qualité, voire pas du tout générées, et peut solliciter fortement votre équipement. En acceptant cet overclocking, vous acceptez que l'IA pourra, une fois la limite dépassée, être moins professionnelle, moins performante, et pourra même affecter les performances de votre ordinateur — mais vous aurez une possibilité d'écriture beaucoup plus large. Voir notre site web pour savoir comment correctement overclocker.",
            "overclock_confirm": "Oui, activer",
            "overclock_cancel": "Annuler",
            "stop_generation": "Arrêter la génération",
            "font_label": "Police de réponse de l'IA",
            "font_user_label": "Police d'écriture de l'utilisateur",
            "font_default": "Par défaut (Noto Serif)",
            "font_arial": "Arial",
            "font_opendyslexic": "Open Dyslexic",
            "tab_profile": "Profil",
            "profile_share_hint": "Carte de profil partageable et modifiable localement.",
            "profile_chats_sent": "Chats envoyés à l'IA",
            "profile_goat_score": "Goat Score",
            "profile_description": "Description",
            "profile_social_links": "Réseaux sociaux",
            "profile_instagram": "Instagram",
            "profile_tiktok": "TikTok",
            "profile_youtube": "YouTube",
            "profile_github": "GitHub",
            "profile_bluesky": "Bluesky",
            "profile_edit": "Modifier",
            "profile_close_edit": "Fermer l'édition",
            "profile_share_pro": "Envoyer le profil professionnel",
            "profile_share_full": "Envoyer le profil complet",
            "profile_avatar": "Photo de profil",
            "profile_banner": "Bannière",
            "profile_change_avatar": "Importer la photo",
            "profile_change_banner": "Importer la bannière",
            "profile_remove_avatar": "Retirer",
            "profile_remove_banner": "Retirer",
            "profile_firstname": "Prénom",
            "profile_lastname": "Nom",
            "profile_bio": "Bio",
            "profile_bio_help": "Votre bio aide l'IA à mieux vous comprendre.",
            "profile_auto_save": "Sauvegarde automatique locale.",
            "profile_no_name": "Profil sans nom",
            "profile_no_description": "Ajoutez une description pour présenter ce profil.",
            "profile_copied": "Profil copié dans le presse-papiers.",
            "profile_share_error": "Impossible de partager le profil pour le moment.",
            "profile_share_dev": "Fonction d\u2019envoi du profil en cours de développement.",
            "regenerate_command": "Régénère la réponse précédente.",
            "profile_preview_title": "Aperçu du profil",
            "profile_choose_avatar": "Choisir une image",
            "profile_choose_banner": "Choisir une bannière",
            "profile_picker_title": "Choisir une image",
            "profile_picker_title_banner": "Choisir une bannière",
            "profile_picker_category_goat": "Goat",
            "profile_picker_import_avatar": "Importer une image",
            "profile_picker_import_banner": "Importer une bannière",
            "tab_aide": "Aide",
            "aide_contact_title": "Contacter le développeur",
            "aide_contact_desc": "Une question, un bug, une idée ? Écrivez-nous.",
            "aide_contact_btn": "Contacter",
            "aide_contact_modal_title": "Nous contacter",
            "aide_contact_modal_desc": "Choisissez votre moyen de contact préféré.",
            "aide_close": "Fermer",
            "aide_beta_label": "BÊTA",
            # ── Onglet Connecteurs ─────────────────────────────────
            "tab_connectors": "Connecteurs",
            "connectors_title": "Connecteurs",
            "connectors_subtitle": "Liez Le Goat à vos services et outils externes.",
            "connectors_add": "Ajouter un connecteur",
            "connectors_modal_title": "Connecteurs disponibles",
            "connectors_empty": "Aucun connecteur",
            "connectors_empty_hint": "Aucun connecteur n'est disponible pour le moment.",
            "connectors_add_custom": "Ajouter un connecteur personnalisé",
            "connectors_custom_modal_title": "Connecteur personnalisé",
            "connectors_custom_modal_desc": "Cette fonction est en cours de développement.",
            # ── Toggle "Version de prévisualisation" ──────────────
            "preview_toggle_label": "Accéder à la version de prévisualisation",
            "preview_toggle_hint": "Active les fonctions expérimentales — modes, styles, connecteurs, chat privé, sidebar, ciblage des calculs, overclocking, pièces jointes.",
            "preview_warning_title": "Activer les fonctions de prévisualisation",
            "preview_warning_text": "Plusieurs fonctions seront affichées, mais elles risquent d'être inutilisables ou en cours de test. Souhaitez-vous continuer ?",
            "preview_warning_confirm": "Activer",
            "preview_warning_cancel": "Annuler",
            # ── Barre de menu (style logiciel) ─────────────────────
            "menu_file": "Fichier",
            "menu_edit": "Édition",
            "menu_help": "Aide",
            "menu_open_location": "Emplacement du/des programmes",
            "menu_settings": "Paramètres",
            "menu_new_chat": "Nouvelle conversation",
            "menu_contact_dev": "Contacter le développeur",
            "menu_doc": "Documentation du projet",
            # Raccourcis clavier (édition)
            "shortcut_undo": "Annuler",
            "shortcut_redo": "Rétablir",
            "shortcut_cut": "Couper",
            "shortcut_copy": "Copier",
            "shortcut_paste": "Coller",
            "shortcut_select_all": "Tout sélectionner",
            "shortcut_find": "Rechercher",
        },
        "en": {
            "placeholder": "Ask The Goat...", "settings_label": "Settings", "settings_title": "Settings",
            "settings_subtitle": "Local configuration for The Goat",
            "tab_general": "General", "tab_personalization": "Personalization",
            "tab_data_security": "Data & Security", "tab_optimization": "Optimization & Performance",
            "general_language": "Language", "general_version": "Version", "general_theme": "Theme",
            "general_text_size": "Text size", "general_app_scale": "Software size", "general_app_scale_hint": "Enlarge or reduce the whole interface.", "tab_appearance": "Appearance", "appearance_color": "Interface color", "appearance_wallpaper": "Wallpaper", "appearance_wallpaper_normal": "Wallpaper for normal mode", "appearance_wallpaper_coworking": "Wallpaper for Goat Code", "appearance_change": "Change", "appearance_remove": "Remove", "appearance_modal_title": "Wallpaper", "appearance_import_image": "Import an image", "appearance_import_video": "Import a video", "appearance_video_volume": "Video volume", "appearance_video_help": "Looping video for the background.", "appearance_video_import_warning": "The longer and higher-quality the video is, the longer the import will take and it may cause the software to lag.", "appearance_preview": "Preview", "color_blue": "Blue", "color_red": "Red", "color_green": "Green", "color_yellow": "Yellow", "color_pink": "Pink", "color_purple": "Purple", "general_keyboard_sounds": "Keyboard sound",
            "general_keyboard_sound_style": "Keyboard sound style", "general_click_sounds": "Button sounds",
            "general_click_sound_style": "Button sound style", "general_ai_reply_sounds": "AI reply sound",
            "language_fr": "French", "language_en": "English", "language_es": "Spanish",
            "theme_light": "Light", "theme_dark": "Dark",
            "theme_description": "Choose the global interface appearance.",
            "text_size_default": "Default", "text_size_large": "Large",
            "sound_on": "Enable", "sound_off": "Disable",
            "sound_style_bulle": "Bubble", "sound_style_aurela": "Aurela",
            "sound_style_verdrock": "Verdrock", "sound_style_feryn": "Feryn", "sound_style_nebrise": "Nebrise",
            "personalization_name": "First name", "personalization_surname": "Last name",
            "personalization_tone": "AI tone", "personalization_info": "About you",
            "personalization_placeholder": "e.g., preferences, constraints, useful context…",
            "placeholder_firstname": "Enter your first name", "placeholder_lastname": "Enter your last name",
            "placeholder_tone": "e.g., professional, casual, direct…",
            "perso_how_address": "How the AI addresses you",
            "perso_how_address_help": "First name, nickname, or title the AI will use.",
            "perso_ai_tone": "AI tone",
            "perso_ai_tone_help": "Describe how you want the AI to talk to you.",
            "data_security_memory": "Manage memory", "data_security_history": "Manage chat history",
            "optimization_effects": "Optimize visual effects", "optimization_responses": "Optimize responses",
            "optimization_ram": "Free AI working memory",
            "optimization_ram_hint": "Clears the current conversation memory — the AI will no longer remember previous exchanges in this session.",
            "optimization_calc_target": "Compute targeting",
            "optimization_calc_target_hint": "Choose the preferred compute path for heavy workloads.",
            "calc_target_cpu": "CPU (Ram)",
            "calc_target_gpu": "GPU (Vram)",
            "calc_target_default": "Default (Use both spaces)",
            "calc_target_notify_cpu": "CPU mode enabled — The AI will focus solely on CPU (RAM). This may limit performance and disable some models like Maestro.",
            "calc_target_notify_gpu": "GPU mode enabled — The AI will focus solely on GPU (VRAM). This may limit performance and disable some models like Maestro.",
            "calc_target_notify_default": "Default mode enabled — Full PC power will be used without limiting any model.",
            "state_on": "On", "state_off": "Off",
            "mode_active_prefix": "Active mode:", "no_mode": "No mode",
            "close": "Close", "settings_hint": "Tip: you can move this window with your mouse.",
            "new_chat": "New chat",
            "new_chat_confirm": "The current chat will be deleted and cannot be recovered. Continue?",
            "tab_switch_confirm": "Switching workspace will reset the current conversation. Continue?",
            "regenerate": "Regenerate", "soon": "Coming soon.",
            "specificity": "Details",
            "tooltip_specificity": "See request details (mode, style, model, attachments, timestamps…).",
            "specificity_title": "Response details",
            "specificity_mode": "Mode used",
            "specificity_style": "Writing style",
            "specificity_model": "Model used",
            "specificity_attachments": "Documents and images",
            "specificity_request_time": "Request sent",
            "specificity_response_time": "Response received",
            "specificity_duration": "Response time",
            "specificity_none": "None",
            "specificity_no_attachments": "No document or image attached",
            "specificity_unavailable": "No information available.",
            "specificity_seconds_short": "s",
            "specificity_milliseconds_short": "ms",
            "specificity_custom_model": "Custom model",
            "sidebar_search_placeholder": "Search a conversation…",
            "sidebar_pinned": "Pinned",
            "sidebar_pinned_empty": "Drag to pin",
            "sidebar_tab_files": "Files",
            "sidebar_tab_history": "History",
            "sidebar_create_file": "Create a file",
            "sidebar_history_empty": "No conversation yet.",
            "attach_image": "Image",
            "attach_image_hint": "Attach an image (PNG, JPG, GIF…)",
            "attach_file": "File",
            "attach_file_hint": "Attach any file type",
            "mode_reflection": "Reflection", "mode_fast": "Fast",
            "mode_research_in_data": "Research In Data", "mode_research_in_memory": "Research In Memory",
            "mode_creativity": "Creativity", "mode_deep_research": "Deep Research",
            "model_sukoshi": "Sukoshi", "model_goat": "Traditional", "model_maestro": "Maestro", "model_goat_code": "Goat Code",
            "model_sukoshi_desc": "Compact and fast model.",
            "model_goat_desc": "Traditional model, balanced and versatile.",
            "model_maestro_desc": "Heavier AI, capable of handling complex and large-scale tasks.",
            "model_goat_code_desc": "Model built for code generation, code correction and code analysis.",
            "model_label": "Model", "model_recent": "Most recent",
            "tooltip_send": "Send message (Enter).", "tooltip_settings": "Open settings.",
            "tooltip_new_chat": "Start a new chat (deletes current).",
            "tooltip_sidebar": "Open / close the sidebar panel.",
            "tooltip_regenerate": "Regenerate the AI answer.",
            "tooltip_mode_fast": "Fast answer, low cost.",
            "tooltip_mode_reflection": "Deeper thinking (slower).",
            "tooltip_mode_research_in_data": "Search your documents (RAG).",
            "tooltip_mode_research_in_memory": "Search memory/history (more costly).",
            "tooltip_mode_creativity": "More creative style, higher variability.",
            "tooltip_mode_deep_research": "Deep research (advanced analysis, slower).",
            "tooltip_mode_trigger": "Select a mode (re-click to deselect).",
            "review_code": "Review code",
            "execute_code": "Execute code",
            "tooltip_execute_code": "Runs a simulation using algorithmic logic to check if the code should work correctly.",
            "add_sheet": "Add written data",
            "tooltip_plus_btn": "Add external data to the AI.",
            "sheet_title": "Writing sheet",
            "sheet_add": "Add", "sheet_cancel": "Cancel",
            "sheets_max": "Maximum 10 sheets reached.",
            "sheet_too_large": "This sheet exceeds the {limit} limit for the current model.",
            "private_chat": "Private Chat",
            "private_chat_desc": "This conversation will not be saved in history.",
            "private_chat_welcome": "Private Chat Activated",
            "private_chat_welcome_desc": "The information entered will not and cannot be saved in history or memory.",
            "writing_style_label": "Writing Style", "no_style": "No style",
            "style_explicatif": "Explanatory", "style_educatif": "Educational",
            "tooltip_style_explicatif": "A more explanatory style, great for school or explaining a topic.",
            "tooltip_style_educatif": "Ideal for learning a concept or something new.",
            "tooltip_style_trigger": "Select a writing style (re-click to deselect).",
            # ── Custom models ───────────────────────────────────
            "perso_other_models": "Other models",
            "perso_other_models_help": "Enable the ability to add and manage your own models.",
            "tooltip_other_models_toggle": "Enables the option to add models other than the original ones.",
            "models_btn_label": "Models",
            "tooltip_models_trigger": "Manage and activate your custom models.",
            "models_add": "Add a model",
            "models_modal_title": "NAME Models",
            "models_modal_placeholder": "Model name",
            "models_modal_enter": "Enter",
            "models_modal_cancel": "Cancel",
            "models_no_custom": "No custom model yet.",
            "models_custom_label": "Custom",
            "models_rename": "Rename",
            "models_delete": "Delete",
            "models_set_default": "Reset model to default",
            "models_default_required": "To switch back to Sukoshi, Traditional or Maestro, first reset the model to \"Default\".",
            "models_delete_confirm": "Delete this custom model?",
            "models_invalid_name": "Model name cannot be empty.",
            "models_duplicate_name": "A model with this name already exists.",
            "analyze_code": "Analyze code",
            "update_info": "View update information",
            "dev_notes": "View development notes",
            "migrate_data": "Migrate data",
            "migrate_title": "Migrate data to The Goat",
            "migrate_step1": "1. Copy this prompt into a conversation with your other AI.",
            "migrate_step2": "2. Paste the results below to add them to The Goat's memory.",
            "migrate_paste_placeholder": "Paste your memory details here.",
            "migrate_add": "Add data to the AI",
            "migrate_cancel": "Cancel",
            "migrate_copy": "Copy",
            "migrate_success": "Data has been imported successfully.",
            "gadget_label": "Gadget", "no_gadget": "No gadget",
            "gadget_schema": "Diagram",
            "tooltip_gadget_schema": "Generates a visual diagram from your request.",
            "tooltip_gadget_trigger": "Select a gadget (re-click to deselect).",
            "tab_goat_dev": "Goat Developer",
            "goat_dev_news": "Development news",
            "goat_dev_news_desc": "Discover the latest features and improvements.",
            "goat_dev_about": "Learn more about Goat Developer",
            "goat_dev_about_desc": "The team and vision behind The Goat.",
            "thanks_message": "Designed and coded in France",
            "char_limit_tooltip": "Character limit the AI can analyze in a single request.",
            "char_limit_overclock_tooltip": "Overclocking enabled — Be careful exceeding the limit, responses may be degraded.",
            "sheets_max_one": "Maximum 1 sheet reached. Enable overclocking to add up to 10.",
            "sheet_char_limit": "Limit: 14,000 characters",
            "contraction_label": "Contraction Of Chat",
            "contraction_tooltip": "Contraction Of Chat mode active: total characters exceed 10,000. Responses will be compressed.",
            "overclock_label": "AI Overclocking",
            "overclock_subtitle": "Unlocks the character limit for larger requests.",
            "overclock_warning": "By enabling overclocking, you will unlock the character limit and push the AI beyond its nominal limits. This can be beneficial for larger requests but may also make responses much longer, and in some overload cases, make responses non-generable or fragmented. Taking the risk of unlocking this limit may result in incomplete, lower quality, or entirely failed responses, and may heavily stress your equipment. By accepting this overclocking, you accept that the AI may, once the limit is exceeded, be less professional, less performant, and may even affect your computer's performance — but you will have a much wider writing capacity. See our website to learn how to properly overclock.",
            "overclock_confirm": "Yes, enable",
            "overclock_cancel": "Cancel",
            "stop_generation": "Stop generation",
            "font_label": "AI response font",
            "font_user_label": "User writing font",
            "font_default": "Default (Noto Serif)",
            "font_arial": "Arial",
            "font_opendyslexic": "Open Dyslexic",
            "tab_profile": "Profile",
            "profile_share_hint": "Shareable profile card stored locally.",
            "profile_chats_sent": "Chats sent to the AI",
            "profile_goat_score": "Goat Score",
            "profile_description": "Description",
            "profile_social_links": "Social links",
            "profile_instagram": "Instagram",
            "profile_tiktok": "TikTok",
            "profile_youtube": "YouTube",
            "profile_github": "GitHub",
            "profile_bluesky": "Bluesky",
            "profile_edit": "Edit",
            "profile_close_edit": "Close editor",
            "profile_share_pro": "Share professional profile",
            "profile_share_full": "Share full profile",
            "profile_avatar": "Profile photo",
            "profile_banner": "Banner",
            "profile_change_avatar": "Import photo",
            "profile_change_banner": "Import banner",
            "profile_remove_avatar": "Remove",
            "profile_remove_banner": "Remove",
            "profile_firstname": "First name",
            "profile_lastname": "Last name",
            "profile_bio": "Bio",
            "profile_bio_help": "Your bio helps the AI understand you better.",
            "profile_auto_save": "Saved locally automatically.",
            "profile_no_name": "Unnamed profile",
            "profile_no_description": "Add a description to present this profile.",
            "profile_copied": "Profile copied to clipboard.",
            "profile_share_error": "Unable to share the profile right now.",
            "profile_share_dev": "Profile sharing is still in development.",
            "regenerate_command": "Regenerate the previous answer.",
            "profile_preview_title": "Profile preview",
            "profile_choose_avatar": "Choose an image",
            "profile_choose_banner": "Choose a banner",
            "profile_picker_title": "Choose an image",
            "profile_picker_title_banner": "Choose a banner",
            "profile_picker_category_goat": "Goat",
            "profile_picker_import_avatar": "Import an image",
            "profile_picker_import_banner": "Import a banner",
            "tab_aide": "Help",
            "aide_contact_title": "Contact the developer",
            "aide_contact_desc": "A question, a bug, an idea? Write to us.",
            "aide_contact_btn": "Contact",
            "aide_contact_modal_title": "Contact us",
            "aide_contact_modal_desc": "Choose your preferred way to reach us.",
            "aide_close": "Close",
            "aide_beta_label": "BETA",
            # ── Connectors tab ───────────────────────────────────
            "tab_connectors": "Connectors",
            "connectors_title": "Connectors",
            "connectors_subtitle": "Link The Goat to your external services and tools.",
            "connectors_add": "Add a connector",
            "connectors_modal_title": "Available connectors",
            "connectors_empty": "No connector",
            "connectors_empty_hint": "No connector is available at the moment.",
            "connectors_add_custom": "Add a custom connector",
            "connectors_custom_modal_title": "Custom connector",
            "connectors_custom_modal_desc": "This feature is currently being developed.",
            # ── Preview toggle ───────────────────────────────────
            "preview_toggle_label": "Access the preview version",
            "preview_toggle_hint": "Enables experimental features — modes, styles, connectors, private chat, sidebar, compute targeting, overclocking, attachments.",
            "preview_warning_title": "Enable preview features",
            "preview_warning_text": "Several features will be displayed but may be unusable or under testing. Do you want to continue?",
            "preview_warning_confirm": "Enable",
            "preview_warning_cancel": "Cancel",
            # ── Top menubar ──────────────────────────────────────
            "menu_file": "File",
            "menu_edit": "Edit",
            "menu_help": "Help",
            "menu_open_location": "Program location",
            "menu_settings": "Settings",
            "menu_new_chat": "New conversation",
            "menu_contact_dev": "Contact the developer",
            "menu_doc": "Project documentation",
            "shortcut_undo": "Undo",
            "shortcut_redo": "Redo",
            "shortcut_cut": "Cut",
            "shortcut_copy": "Copy",
            "shortcut_paste": "Paste",
            "shortcut_select_all": "Select all",
            "shortcut_find": "Find",
        },
        "es": {
            "placeholder": "Pregunte a El Goat...", "settings_label": "Ajustes", "settings_title": "Ajustes",
            "settings_subtitle": "Configuración local de El Goat",
            "tab_general": "General", "tab_personalization": "Personalización",
            "tab_data_security": "Datos y seguridad", "tab_optimization": "Optimización y rendimiento",
            "general_language": "Idioma", "general_version": "Versión", "general_theme": "Tema",
            "general_text_size": "Tamaño del texto", "general_app_scale": "Tamaño del software", "general_app_scale_hint": "Amplía o reduce toda la interfaz.", "tab_appearance": "Apariencia", "appearance_color": "Color de la interfaz", "appearance_wallpaper": "Fondo de pantalla", "appearance_wallpaper_normal": "Fondo del modo normal", "appearance_wallpaper_coworking": "Fondo de Goat Code", "appearance_change": "Cambiar", "appearance_remove": "Quitar", "appearance_modal_title": "Fondo de pantalla", "appearance_import_image": "Importar una imagen", "appearance_import_video": "Importar un vídeo", "appearance_video_volume": "Volumen del vídeo", "appearance_video_help": "Vídeo en bucle para el fondo.", "appearance_video_import_warning": "Cuanto más largo y de mayor calidad sea el vídeo, más tardará la importación y podría hacer que el software vaya lento.", "appearance_preview": "Vista previa", "color_blue": "Azul", "color_red": "Rojo", "color_green": "Verde", "color_yellow": "Amarillo", "color_pink": "Rosa", "color_purple": "Violeta", "general_keyboard_sounds": "Sonido del teclado",
            "general_keyboard_sound_style": "Estilo de sonido del teclado", "general_click_sounds": "Sonido de botones",
            "general_click_sound_style": "Estilo de sonido de botones", "general_ai_reply_sounds": "Sonido de respuesta IA",
            "language_fr": "Francés", "language_en": "Inglés", "language_es": "Español",
            "theme_light": "Claro", "theme_dark": "Oscuro",
            "theme_description": "Elija la apariencia global de la interfaz.",
            "text_size_default": "Por defecto", "text_size_large": "Grande",
            "sound_on": "Activar", "sound_off": "Desactivar",
            "sound_style_bulle": "Burbuja", "sound_style_aurela": "Aurela",
            "sound_style_verdrock": "Verdrock", "sound_style_feryn": "Feryn", "sound_style_nebrise": "Nebrise",
            "personalization_name": "Nombre", "personalization_surname": "Apellido",
            "personalization_tone": "Tono de la IA", "personalization_info": "Información sobre usted",
            "personalization_placeholder": "p. ej., preferencias, restricciones, contexto útil…",
            "placeholder_firstname": "Ingrese su nombre", "placeholder_lastname": "Ingrese su apellido",
            "placeholder_tone": "p. ej., profesional, relajado, directo…",
            "perso_how_address": "Cómo se dirige la IA a usted",
            "perso_how_address_help": "Nombre, apodo o título que usará la IA.",
            "perso_ai_tone": "Tono de la IA",
            "perso_ai_tone_help": "Describa cómo quiere que la IA le hable.",
            "data_security_memory": "Gestionar memoria", "data_security_history": "Gestionar historial de chats",
            "optimization_effects": "Optimizar efectos visuales", "optimization_responses": "Optimizar respuestas",
            "optimization_ram": "Liberar memoria de trabajo de la IA",
            "optimization_ram_hint": "Borra la memoria de la conversación actual — la IA ya no recordará los intercambios anteriores de esta sesión.",
            "optimization_calc_target": "Objetivo de cálculo",
            "optimization_calc_target_hint": "Elija la ruta de cálculo preferida para las cargas pesadas.",
            "calc_target_cpu": "CPU (Ram)",
            "calc_target_gpu": "GPU (Vram)",
            "calc_target_default": "Por defecto (Usar ambos espacios)",
            "calc_target_notify_cpu": "Modo CPU activado — La IA se concentrará únicamente en la CPU (RAM). Esto puede limitar el rendimiento y desactivar algunos modelos como Maestro.",
            "calc_target_notify_gpu": "Modo GPU activado — La IA se concentrará únicamente en la GPU (VRAM). Esto puede limitar el rendimiento y desactivar algunos modelos como Maestro.",
            "calc_target_notify_default": "Modo por defecto activado — Se usará toda la potencia del PC sin limitar ningún modelo.",
            "state_on": "Activado", "state_off": "Desactivado",
            "mode_active_prefix": "Modo activo:", "no_mode": "Sin modo",
            "close": "Cerrar", "settings_hint": "Consejo: puede mover esta ventana con el ratón.",
            "new_chat": "Nuevo chat",
            "new_chat_confirm": "El chat actual se eliminará y no se podrá recuperar. ¿Continuar?",
            "tab_switch_confirm": "Cambiar de espacio reiniciará la conversación actual. ¿Continuar?",
            "regenerate": "Regenerar", "soon": "Próximamente.",
            "specificity": "Detalles",
            "tooltip_specificity": "Ver los detalles de la solicitud (modo, estilo, modelo, adjuntos, marca de tiempo…).",
            "specificity_title": "Detalles de la respuesta",
            "specificity_mode": "Modo utilizado",
            "specificity_style": "Estilo de escritura",
            "specificity_model": "Modelo utilizado",
            "specificity_attachments": "Documentos e imágenes",
            "specificity_request_time": "Solicitud enviada",
            "specificity_response_time": "Respuesta recibida",
            "specificity_duration": "Tiempo de respuesta",
            "specificity_none": "Ninguno",
            "specificity_no_attachments": "Ningún documento o imagen adjunto",
            "specificity_unavailable": "No hay información disponible.",
            "specificity_seconds_short": "s",
            "specificity_milliseconds_short": "ms",
            "specificity_custom_model": "Modelo personalizado",
            "sidebar_search_placeholder": "Buscar una conversación…",
            "sidebar_pinned": "Anclados",
            "sidebar_pinned_empty": "Arrastra para anclar",
            "sidebar_tab_files": "Archivos",
            "sidebar_tab_history": "Historial",
            "sidebar_create_file": "Crear un archivo",
            "sidebar_history_empty": "Aún no hay conversaciones.",
            "attach_image": "Imagen",
            "attach_image_hint": "Adjuntar una imagen (PNG, JPG, GIF…)",
            "attach_file": "Archivo",
            "attach_file_hint": "Adjuntar cualquier tipo de archivo",
            "mode_reflection": "Reflection", "mode_fast": "Fast",
            "mode_research_in_data": "Research In Data", "mode_research_in_memory": "Research In Memory",
            "mode_creativity": "Creativity", "mode_deep_research": "Deep Research",
            "model_sukoshi": "Sukoshi", "model_goat": "Tradicional", "model_maestro": "Maestro", "model_goat_code": "Goat Code",
            "model_sukoshi_desc": "Modelo compacto y rápido.",
            "model_goat_desc": "Modelo tradicional, equilibrado y versátil.",
            "model_maestro_desc": "IA más pesada, capaz de manejar tareas complejas y de gran envergadura.",
            "model_goat_code_desc": "Modelo hecho para generación de código, corrección de código y análisis de código.",
            "model_label": "Modelo", "model_recent": "Más reciente",
            "tooltip_send": "Enviar mensaje (Enter).", "tooltip_settings": "Abrir ajustes.",
            "tooltip_new_chat": "Iniciar un nuevo chat (borra el actual).",
            "tooltip_sidebar": "Abrir / cerrar el panel lateral.",
            "tooltip_regenerate": "Regenerar la respuesta de la IA.",
            "tooltip_mode_fast": "Respuesta rápida, bajo coste.",
            "tooltip_mode_reflection": "Reflexión más profunda (más lento).",
            "tooltip_mode_research_in_data": "Buscar en sus documentos (RAG).",
            "tooltip_mode_research_in_memory": "Buscar en memoria/historial (más costoso).",
            "tooltip_mode_creativity": "Estilo más creativo, más variabilidad.",
            "tooltip_mode_deep_research": "Deep research (análisis avanzado, más lento).",
            "tooltip_mode_trigger": "Seleccionar un modo (haga clic de nuevo para deseleccionar).",
            "review_code": "Revisar código",
            "execute_code": "Ejecutar código",
            "tooltip_execute_code": "Ejecuta una simulación con lógica algorítmica para verificar si el código debería funcionar correctamente.",
            "add_sheet": "Agregar datos escritos",
            "tooltip_plus_btn": "Agregar datos externos a la IA.",
            "sheet_title": "Hoja de escritura",
            "sheet_add": "Agregar", "sheet_cancel": "Cancelar",
            "sheets_max": "Máximo 10 hojas alcanzado.",
            "sheet_too_large": "Esta hoja supera el límite de {limit} para el modelo actual.",
            "private_chat": "Chat Privado",
            "private_chat_desc": "Esta conversación no se guardará en el historial.",
            "private_chat_welcome": "Chat Privado Activado",
            "private_chat_welcome_desc": "La información ingresada no será ni podrá ser guardada en el historial o la memoria.",
            "writing_style_label": "Estilo de escritura", "no_style": "Sin estilo",
            "style_explicatif": "Explicativo", "style_educatif": "Educativo",
            "tooltip_style_explicatif": "Un estilo más explicativo, ideal para la escuela o explicar un tema.",
            "tooltip_style_educatif": "Ideal para aprender un concepto o algo nuevo.",
            "tooltip_style_trigger": "Seleccionar un estilo de escritura (haga clic de nuevo para deseleccionar).",
            # ── Modelos personalizados ─────────────────────────
            "perso_other_models": "Otros modelos",
            "perso_other_models_help": "Activa la posibilidad de añadir y gestionar tus propios modelos.",
            "tooltip_other_models_toggle": "Permite añadir modelos distintos a los originales.",
            "models_btn_label": "Modelos",
            "tooltip_models_trigger": "Gestiona y activa tus modelos personalizados.",
            "models_add": "Añadir un modelo",
            "models_modal_title": "NAME Models",
            "models_modal_placeholder": "Nombre del modelo",
            "models_modal_enter": "Entrar",
            "models_modal_cancel": "Cancelar",
            "models_no_custom": "Aún no hay modelos personalizados.",
            "models_custom_label": "Custom",
            "models_rename": "Renombrar",
            "models_delete": "Eliminar",
            "models_set_default": "Restablecer al modelo por defecto",
            "models_default_required": "Para volver a Sukoshi, Tradicional o Maestro, restablece primero el modelo a «Por defecto».",
            "models_delete_confirm": "¿Eliminar este modelo personalizado?",
            "models_invalid_name": "El nombre del modelo no puede estar vacío.",
            "models_duplicate_name": "Ya existe un modelo con ese nombre.",
            "analyze_code": "Analizar código",
            "update_info": "Ver información de actualizaciones",
            "dev_notes": "Ver notas de desarrollo",
            "migrate_data": "Migrar datos",
            "migrate_title": "Migrar datos a El Goat",
            "migrate_step1": "1. Copie este prompt en una conversación con su otra IA.",
            "migrate_step2": "2. Pegue los resultados a continuación para agregarlos a la memoria de El Goat.",
            "migrate_paste_placeholder": "Pegue los detalles de su memoria aquí.",
            "migrate_add": "Agregar datos a la IA",
            "migrate_cancel": "Cancelar",
            "migrate_copy": "Copiar",
            "migrate_success": "Los datos se han importado correctamente.",
            "gadget_label": "Gadget", "no_gadget": "Sin gadget",
            "gadget_schema": "Esquema",
            "tooltip_gadget_schema": "Genera un esquema visual a partir de su solicitud.",
            "tooltip_gadget_trigger": "Seleccionar un gadget (haga clic de nuevo para deseleccionar).",
            "tab_goat_dev": "Goat Developer",
            "goat_dev_news": "Novedades de desarrollo",
            "goat_dev_news_desc": "Descubra las últimas funcionalidades y mejoras.",
            "goat_dev_about": "Más información sobre Goat Developer",
            "goat_dev_about_desc": "El equipo y la visión detrás de El Goat.",
            "thanks_message": "Designed and coded in France",
            "char_limit_tooltip": "Límite de caracteres que la IA puede analizar en una sola solicitud.",
            "char_limit_overclock_tooltip": "Overclocking activado — Cuidado al superar el límite, las respuestas pueden degradarse.",
            "sheets_max_one": "Máximo 1 hoja alcanzado. Active el overclocking para agregar hasta 10.",
            "sheet_char_limit": "Límite: 14.000 caracteres",
            "contraction_label": "Contraction Of Chat",
            "contraction_tooltip": "Modo Contraction Of Chat activo: el total de caracteres supera 10.000. Las respuestas se comprimirán.",
            "overclock_label": "Overclocking IA",
            "overclock_subtitle": "Desbloquea el límite de caracteres para solicitudes más grandes.",
            "overclock_warning": "Al activar el overclocking, desbloqueará el límite de caracteres y empujará la IA más allá de sus límites nominales. Esto puede ser beneficioso para solicitudes más grandes pero también puede hacer que las respuestas sean mucho más largas, y en algunos casos de sobrecarga, hacer que las respuestas no se generen o sean fragmentadas. Tomar el riesgo de desbloquear este límite puede resultar en respuestas incompletas, de menor calidad o totalmente fallidas, y puede estresar fuertemente su equipo. Al aceptar este overclocking, acepta que la IA podrá, una vez superado el límite, ser menos profesional, menos eficiente, y puede incluso afectar el rendimiento de su computadora — pero tendrá una capacidad de escritura mucho más amplia. Vea nuestro sitio web para aprender cómo overclocar correctamente.",
            "overclock_confirm": "Sí, activar",
            "overclock_cancel": "Cancelar",
            "stop_generation": "Detener generación",
            "font_label": "Fuente de respuesta de la IA",
            "font_user_label": "Fuente de escritura del usuario",
            "font_default": "Por defecto (Noto Serif)",
            "font_arial": "Arial",
            "font_opendyslexic": "Open Dyslexic",
            "tab_profile": "Perfil",
            "profile_share_hint": "Tarjeta de perfil compartible guardada localmente.",
            "profile_chats_sent": "Chats enviados a la IA",
            "profile_goat_score": "Goat Score",
            "profile_description": "Descripción",
            "profile_social_links": "Redes sociales",
            "profile_instagram": "Instagram",
            "profile_tiktok": "TikTok",
            "profile_youtube": "YouTube",
            "profile_github": "GitHub",
            "profile_bluesky": "Bluesky",
            "profile_edit": "Editar",
            "profile_close_edit": "Cerrar edición",
            "profile_share_pro": "Compartir perfil profesional",
            "profile_share_full": "Compartir perfil completo",
            "profile_avatar": "Foto de perfil",
            "profile_banner": "Banner",
            "profile_change_avatar": "Importar foto",
            "profile_change_banner": "Importar banner",
            "profile_remove_avatar": "Quitar",
            "profile_remove_banner": "Quitar",
            "profile_firstname": "Nombre",
            "profile_lastname": "Apellido",
            "profile_bio": "Bio",
            "profile_bio_help": "Tu bio ayuda a la IA a entenderte mejor.",
            "profile_auto_save": "Guardado local automático.",
            "profile_no_name": "Perfil sin nombre",
            "profile_no_description": "Agregue una descripción para presentar este perfil.",
            "profile_copied": "Perfil copiado al portapapeles.",
            "profile_share_error": "No se puede compartir el perfil en este momento.",
            "profile_share_dev": "La función de compartir el perfil sigue en desarrollo.",
            "regenerate_command": "Regenera la respuesta anterior.",
            "profile_preview_title": "Vista previa del perfil",
            "profile_choose_avatar": "Elegir una imagen",
            "profile_choose_banner": "Elegir un banner",
            "profile_picker_title": "Elegir una imagen",
            "profile_picker_title_banner": "Elegir un banner",
            "profile_picker_category_goat": "Goat",
            "profile_picker_import_avatar": "Importar una imagen",
            "profile_picker_import_banner": "Importar un banner",
            "tab_aide": "Ayuda",
            "aide_contact_title": "Contactar al desarrollador",
            "aide_contact_desc": "¿Una pregunta, un error, una idea? Escríbanos.",
            "aide_contact_btn": "Contactar",
            "aide_contact_modal_title": "Contáctenos",
            "aide_contact_modal_desc": "Elija su forma de contacto preferida.",
            "aide_close": "Cerrar",
            "aide_beta_label": "BETA",
            # ── Pestaña Conectores ───────────────────────────────
            "tab_connectors": "Conectores",
            "connectors_title": "Conectores",
            "connectors_subtitle": "Vincule El Goat con sus servicios y herramientas externas.",
            "connectors_add": "Añadir un conector",
            "connectors_modal_title": "Conectores disponibles",
            "connectors_empty": "Ningún conector",
            "connectors_empty_hint": "No hay ningún conector disponible por el momento.",
            "connectors_add_custom": "Añadir un conector personalizado",
            "connectors_custom_modal_title": "Conector personalizado",
            "connectors_custom_modal_desc": "Esta función está en desarrollo.",
            # ── Toggle de vista previa ───────────────────────────
            "preview_toggle_label": "Acceder a la versión de vista previa",
            "preview_toggle_hint": "Activa las funciones experimentales — modos, estilos, conectores, chat privado, barra lateral, objetivo de cálculo, overclocking, adjuntos.",
            "preview_warning_title": "Activar funciones de vista previa",
            "preview_warning_text": "Se mostrarán varias funciones, pero pueden ser inutilizables o estar en pruebas. ¿Desea continuar?",
            "preview_warning_confirm": "Activar",
            "preview_warning_cancel": "Cancelar",
            # ── Barra de menú ─────────────────────────────────────
            "menu_file": "Archivo",
            "menu_edit": "Edición",
            "menu_help": "Ayuda",
            "menu_open_location": "Ubicación del/los programas",
            "menu_settings": "Ajustes",
            "menu_new_chat": "Nueva conversación",
            "menu_contact_dev": "Contactar al desarrollador",
            "menu_doc": "Documentación del proyecto",
            "shortcut_undo": "Deshacer",
            "shortcut_redo": "Rehacer",
            "shortcut_cut": "Cortar",
            "shortcut_copy": "Copiar",
            "shortcut_paste": "Pegar",
            "shortcut_select_all": "Seleccionar todo",
            "shortcut_find": "Buscar",
        },
    }



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
        base = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
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
        base = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
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
        base = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
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
        base = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
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


# ============================================================
# Template HTML / CSS / JS
# ============================================================

def _load_html_template() -> str:
    """
    Retourne le template HTML complet de l'interface.

    Ce template est une chaîne brute (raw string) contenant des marqueurs
    %%NOM%% qui seront remplacés par build_index_html() avant envoi au client.

    Structure du template
    ---------------------
    <head>
      Polices (Google Fonts) + CSS inline complet
    </head>
    <body>
      Top Tab Bar  — onglets Chat / Goat Code + modèles
      Private Chat Button
      <main>
        .brand-stack    — logo + message de bienvenue
        .messages       — historique de conversation
        .composer-wrap  — zone de saisie + boutons de contrôle
      </main>
      Modales — paramètres, migration, feuilles, overclock
      <script> — logique UI complète (vanilla JS)
    </body>

    Marqueurs disponibles
    ---------------------
    %%APP_TITLE%%         Titre de l'application
    %%APP_VERSION%%       Version (AppConfig.VERSION)
    %%TRANSLATIONS_JSON%% Objet JSON des traductions
    %%MODES_JSON%%        Tableau JSON des modes actifs
    %%MODELS_JSON%%       Tableau JSON des modèles
    %%MESSAGES_JSON%%     Historique de la session courante
    ... (voir build_index_html pour la liste complète)
    """
    return r'''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%%APP_TITLE%%</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
<link href="https://fonts.cdnfonts.com/css/open-dyslexic" rel="stylesheet">
<style>
@font-face{font-family:"OpenDyslexicCustom";src:local("OpenDyslexic-Regular"),local("OpenDyslexic Regular"),local("OpenDyslexic"),local("Open Dyslexic"),local("Open-Dyslexic");font-weight:400;font-style:normal;}
@font-face{font-family:"OpenDyslexicCustom";src:local("OpenDyslexic-Italic"),local("OpenDyslexic Italic"),local("Open Dyslexic Italic"),local("OpenDyslexic");font-weight:400;font-style:italic;}
@font-face{font-family:"OpenDyslexicCustom";src:local("OpenDyslexic-Bold"),local("OpenDyslexic Bold"),local("Open Dyslexic Bold"),local("OpenDyslexic");font-weight:700;font-style:normal;}
@font-face{font-family:"OpenDyslexicCustom";src:local("OpenDyslexic-BoldItalic"),local("OpenDyslexic Bold Italic"),local("Open Dyslexic Bold Italic"),local("OpenDyslexic");font-weight:700;font-style:italic;}
</style>
<style>
:root{--text-scale:1;--ui-scale-factor:1;--accent:#3b82f6;--accent-rgb:59,130,246;--accent-soft:rgba(var(--accent-rgb),.12);--accent-soft-2:rgba(var(--accent-rgb),.08);--accent-border:rgba(var(--accent-rgb),.26);--bg:#fff;--text-primary:#1f2937;--text-secondary:#6b7280;--text-muted:#b8b8b8;--line:rgba(148,163,184,.22);--bubble-user:#f3f4f6;--bubble-assistant:#fafafa;--input-bg:#f3f4f6;--input-placeholder:#9d9d9d;--surface-soft:#f3f4f6;--surface-softer:#fcfcfd;--surface-border:#cfd6df;--surface-border-soft:#eef2f7;--shadow-soft:0 18px 46px rgba(15,23,42,.10);--send-bg:#1f2937;--send-color:#fff;--send-shadow:0 0 0 2px #374151,4px 4px 0 0 rgba(15,23,42,.7),0 8px 18px rgba(0,0,0,.12);--settings-backdrop:rgba(15,23,42,.34);--settings-panel:rgba(255,255,255,.98);--settings-panel-border:rgba(148,163,184,.16);--settings-sidebar:rgba(243,244,246,.88);--settings-tab-hover:rgba(var(--accent-rgb),.08);--settings-tab-active:rgba(var(--accent-rgb),.14);--settings-row-border:rgba(148,163,184,.18);--menu-bg:rgba(41,41,41,.98);--menu-border:rgba(255,255,255,.08);--menu-text:#f5f5f5;--menu-hover:rgba(255,255,255,.08);--menu-selected:rgba(121,166,255,.18);--status-color:#b8b8b8;--action-bg:rgba(255,255,255,.65);--action-border:rgba(148,163,184,.18);--action-text:#4b5563;--tooltip-bg:rgba(17,24,39,.95);--tooltip-text:#f8fafc;--tooltip-border:rgba(255,255,255,.08)}
body[data-theme="dark"]{--bg:#161616;--text-primary:#f5f5f5;--text-secondary:#c3c7ce;--text-muted:#9ca3af;--line:rgba(255,255,255,.10);--bubble-user:#262626;--bubble-assistant:#202020;--input-bg:#252525;--input-placeholder:#8a8f98;--surface-soft:#2a2a2a;--surface-softer:#343434;--surface-border:#525867;--surface-border-soft:#2f3440;--shadow-soft:0 20px 48px rgba(0,0,0,.32);--send-bg:#f5f5f5;--send-color:#161616;--send-shadow:0 0 0 2px #d1d5db,4px 4px 0 0 rgba(255,255,255,.3),0 8px 18px rgba(255,255,255,.08);--settings-backdrop:rgba(0,0,0,.52);--settings-panel:rgba(28,28,28,.98);--settings-panel-border:rgba(255,255,255,.06);--settings-sidebar:rgba(38,38,38,.96);--settings-tab-hover:rgba(var(--accent-rgb),.08);--settings-tab-active:rgba(var(--accent-rgb),.18);--settings-row-border:rgba(255,255,255,.08);--status-color:#9ca3af;--action-bg:rgba(0,0,0,.32);--action-border:rgba(255,255,255,.08);--action-text:rgba(255,255,255,.84)}
body[data-textsize="large"]{--text-scale:1.15}
body[data-effects="off"] *{transition:none!important;animation:none!important}
body[data-effects="off"] .bubble,body[data-effects="off"] .composer,body[data-effects="off"] .settings-modal,body[data-effects="off"] .settings-ghost-button,body[data-effects="off"] .settings-choice,body[data-effects="off"] .bubble-action{box-shadow:none!important;filter:none!important}
body[data-effects="off"] .composer,body[data-effects="off"] .settings-backdrop{backdrop-filter:none!important}
*{box-sizing:border-box}body{margin:0;min-height:100vh;font-family:"JetBrains Mono","Segoe UI",Arial,sans-serif;font-size:calc(16px * var(--text-scale));background:transparent;color:var(--text-primary)}
button,input,textarea,select{font:inherit}

/* ── Goat Coworking visual mode ── */
body[data-active-tab="coworking"][data-cw-wallpaper="off"] .wallpaper-layer{background-image:linear-gradient(rgba(var(--accent-rgb),.08) 1px,transparent 1px),linear-gradient(90deg,rgba(var(--accent-rgb),.08) 1px,transparent 1px);background-size:32px 32px;background-position:center center}
body[data-theme="dark"][data-active-tab="coworking"][data-cw-wallpaper="off"] .wallpaper-layer{background-image:linear-gradient(rgba(var(--accent-rgb),.11) 1px,transparent 1px),linear-gradient(90deg,rgba(var(--accent-rgb),.11) 1px,transparent 1px)}
body[data-active-tab="chat"] .wallpaper-layer,body[data-active-tab="coworking"][data-cw-wallpaper="on"] .wallpaper-layer{background-image:none}

/* ── Top Tab Bar (Chat / Goat Coworking) ── */
.top-tab-bar{position:fixed;top:0;left:0;right:0;height:52px;display:flex;align-items:center;justify-content:center;z-index:55;background:var(--bg);border-bottom:1px solid var(--line);padding:0 16px}
.top-tab-bar-inner{display:flex;align-items:center;background:var(--surface-soft);border-radius:12px;padding:3px;gap:2px}
.top-tab-btn{padding:8px 20px;border:none;border-radius:10px;background:transparent;color:var(--text-secondary);cursor:pointer;font-size:.875rem;font-weight:600;font-family:"JetBrains Mono","Segoe UI",sans-serif;transition:background .16s,color .16s;display:flex;align-items:center;gap:6px}
.top-tab-btn:hover{color:var(--text-primary)}
.top-tab-btn.active{background:var(--bubble-user);color:var(--text-primary);box-shadow:0 1px 3px rgba(0,0,0,.1)}
.top-tab-btn .chevron{font-size:.65rem;opacity:.5;transition:transform .2s}
.top-tab-btn[aria-expanded="true"] .chevron{transform:rotate(180deg)}
.tab-chat-wrap{position:relative}

/* ── Model dropdown (intégré dans onglet Chat) ── */
.model-dropdown{display:none}
.model-trigger-btn{display:none}
.model-trigger-btn{display:flex;align-items:center;gap:6px;border:none;background:transparent;color:var(--text-primary);cursor:pointer;font-size:1rem;font-weight:700;padding:8px 12px;border-radius:12px;transition:background .14s}
.model-trigger-btn:hover{background:var(--surface-soft)}
.model-trigger-btn .chevron{font-size:.7rem;opacity:.6;transition:transform .2s}
.model-trigger-btn[aria-expanded="true"] .chevron{transform:rotate(180deg)}
.model-dd-menu{position:absolute;top:calc(100% + 8px);left:50%;transform:translateX(-50%);min-width:280px;padding:10px;border-radius:16px;background:var(--menu-bg);border:1px solid var(--menu-border);box-shadow:0 20px 50px rgba(0,0,0,.32);display:flex;flex-direction:column;gap:2px;z-index:60;opacity:0;pointer-events:none;transition:opacity .16s,transform .16s;transform:translateX(-50%) translateY(-4px)}
.model-dd-menu.open{opacity:1;pointer-events:auto;transform:translateX(-50%) translateY(0)}
.model-dd-header{padding:8px 12px;font-size:.75rem;color:var(--text-muted);font-weight:500}
.model-dd-item{width:100%;border:none;border-radius:12px;background:transparent;color:var(--menu-text);display:flex;align-items:center;justify-content:space-between;padding:12px;cursor:pointer;text-align:left;transition:background .14s}
.model-dd-item:hover{background:var(--menu-hover)}
.model-dd-item .m-info{display:flex;flex-direction:column;gap:2px}
.model-dd-item .m-name{font-weight:600;font-size:.875rem}
.model-dd-item .m-desc{font-size:.75rem;opacity:.6}
.model-dd-item .m-check{color:#9ec1ff;opacity:0;font-size:1rem}.model-dd-item.selected .m-check{opacity:1}
.model-dd-sep{height:1px;background:var(--menu-border);margin:4px 12px}
.model-dd-action{width:100%;border:none;border-radius:12px;background:transparent;color:var(--menu-text);padding:12px;cursor:pointer;text-align:left;font-size:.875rem;opacity:.7;transition:background .14s}
.model-dd-action:hover{background:var(--menu-hover)}

/* ── Private chat button ── */
.private-chat-btn{position:fixed;top:73px;right:18px;z-index:56;height:34px;padding:0 14px;border-radius:10px;border:1px solid var(--line);background:var(--bubble-user);color:var(--text-primary);display:inline-flex;align-items:center;gap:7px;cursor:pointer;font-size:.8rem;font-weight:600;font-family:"JetBrains Mono","Segoe UI",sans-serif;box-shadow:var(--shadow-soft);transition:transform .14s,background .16s,color .16s}
.private-chat-btn:hover{transform:translateY(-1px)}
.private-chat-btn .pc-tooltip{display:none;position:fixed;top:116px;right:18px;background:var(--tooltip-bg);color:var(--tooltip-text);padding:10px 14px;border-radius:12px;font-size:.8rem;white-space:nowrap;box-shadow:0 12px 30px rgba(0,0,0,.3);z-index:100}
.private-chat-btn .pc-tooltip .pc-title{font-weight:700;margin-bottom:3px}
.private-chat-btn .pc-tooltip .pc-desc{opacity:.7;font-size:.75rem}
.private-chat-btn:hover .pc-tooltip{display:block}
.private-chat-btn.active{background:var(--accent-soft);border-color:var(--accent-border);color:var(--accent)}
.top-tab-btn:disabled{opacity:.35;cursor:not-allowed;pointer-events:none}

.shell{min-height:calc(100vh - 52px);width:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:22px;padding:96px 16px 96px}
.shell.has-messages{justify-content:flex-start;padding-top:96px;padding-bottom:48px}
.brand-stack{display:flex;flex-direction:column;align-items:center;gap:12px;opacity:1;transform:translateY(0) scale(1);max-height:260px;overflow:hidden;transition:opacity .26s,transform .26s,max-height .32s,margin .26s}
.shell.has-messages .brand-stack{opacity:0;transform:translateY(-14px) scale(.92);max-height:0;margin:0;pointer-events:none}
.logo-card{width:auto;height:auto;background:none;display:grid;place-items:center;box-shadow:none;border:none;overflow:visible}
.logo-card img{width:110px;height:110px;object-fit:contain;display:block;filter:none}
body[data-active-tab="coworking"] .logo-card{display:none}
.goatistique-badge{position:fixed;bottom:18px;right:20px;z-index:50;pointer-events:none;opacity:.65;transition:opacity .3s}
.goatistique-badge img{height:80px;width:auto;object-fit:contain;display:block}
.brand-text{display:none}
.welcome-copy{margin-top:10px;max-width:min(920px,calc(100vw - 48px));text-align:center;font-size:clamp(28px,5vw,58px);font-weight:500;line-height:1.08;letter-spacing:-.03em;color:var(--text-primary);user-select:none}
.welcome-desc{max-width:min(600px,calc(100vw - 48px));text-align:center;font-size:.9rem;color:var(--text-secondary);line-height:1.5;margin-top:12px}
.typing-dots{display:inline-flex;gap:6px;align-items:end;padding:6px 0;height:28px}
.typing-dots span{width:9px;height:9px;border-radius:50%;background:var(--text-secondary);animation:dotPulse 1.2s ease-in-out infinite}
.typing-dots span:nth-child(2){animation-delay:.2s}
.typing-dots span:nth-child(3){animation-delay:.4s}
@keyframes dotPulse{0%,100%{transform:translateY(0);opacity:.35}25%{transform:translateY(-12px);opacity:1}50%{transform:translateY(4px);opacity:.6}75%{transform:translateY(-4px);opacity:.8}}
.messages{width:min(760px,calc(100vw - 32px));display:none;flex-direction:column;gap:14px;margin-top:4px;margin-bottom:6px}
.shell.has-messages .messages{display:flex}
.message-row{display:flex;width:100%}.message-row.user{justify-content:flex-end;align-items:flex-end;gap:8px}
.message-row.assistant{justify-content:flex-start;flex-direction:column;align-items:flex-start;gap:6px}
.message-user-avatar{width:34px;height:34px;border-radius:12px;overflow:hidden;border:1px solid var(--line);background:var(--surface-soft);box-shadow:var(--shadow-soft);flex:0 0 34px;align-self:flex-end}
.message-user-avatar img{width:100%;height:100%;object-fit:cover;object-position:center center;display:block}
.bubble{max-width:min(84%,640px);padding:14px 16px;border-radius:22px;line-height:1.5;white-space:pre-wrap;word-break:break-word;box-shadow:var(--shadow-soft);border:1px solid var(--line)}
.message-row.user .bubble{background:var(--bubble-user);color:var(--text-primary);border-top-right-radius:8px}
.message-row.assistant .bubble{background:var(--bubble-assistant);color:var(--text-primary);border-top-left-radius:8px;font-family:"Noto Serif",Georgia,serif}
.bubble-actions{display:inline-flex;gap:10px;padding-left:6px}
.bubble-action{border:1px solid var(--action-border);background:var(--action-bg);color:var(--action-text);border-radius:999px;padding:8px 12px;cursor:pointer;font-size:.75rem;box-shadow:0 10px 24px rgba(15,23,42,.06);transition:transform .14s,box-shadow .14s}
.bubble-action:hover{transform:translateY(-1px)}
.bubble-action.is-active{background:var(--accent-soft);border-color:var(--accent-border);color:var(--accent)}
.bubble-action[data-action="specificity"]{display:inline-flex;align-items:center;gap:6px}
.bubble-action[data-action="specificity"]::before{content:"";display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 2px rgba(var(--accent-rgb),.18)}

/* ── Panneau dépliant « Spécificité » ── */
.specificity-panel{display:none;width:min(84%,640px);margin-top:6px;padding:14px 16px;border-radius:18px;border:1px solid var(--line);background:var(--surface-softer);color:var(--text-primary);box-shadow:var(--shadow-soft);font-size:.82rem;line-height:1.5;animation:specificityFade .18s ease-out}
.specificity-panel.open{display:block}
.specificity-panel-title{font-size:.78rem;font-weight:600;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.08em;margin:0 0 10px 0}
.specificity-grid{display:grid;grid-template-columns:minmax(140px,auto) 1fr;column-gap:14px;row-gap:8px}
.specificity-label{font-weight:600;color:var(--text-secondary);white-space:nowrap}
.specificity-value{color:var(--text-primary);word-break:break-word}
.specificity-value.is-muted{color:var(--text-muted);font-style:italic}
.specificity-attachments{display:flex;flex-direction:column;gap:6px}
.specificity-attachment{display:inline-flex;align-items:center;gap:8px;padding:6px 10px;border-radius:10px;background:var(--surface-soft);border:1px solid var(--line);font-size:.78rem}
.specificity-attachment-kind{font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;color:var(--text-secondary);background:var(--bg);padding:2px 6px;border-radius:6px;border:1px solid var(--line)}
.specificity-attachment-name{font-weight:500;color:var(--text-primary);max-width:320px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.specificity-attachment-size{color:var(--text-muted);font-size:.72rem;margin-left:auto}
@keyframes specificityFade{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:translateY(0)}}
@media (max-width:560px){.specificity-grid{grid-template-columns:1fr;row-gap:4px}.specificity-label{margin-top:4px}}
.composer-wrap{width:min(760px,calc(100vw - 32px));position:relative;margin:0 auto;display:flex;flex-direction:column}
.composer{width:100%;background:var(--input-bg);border:1px solid var(--line);border-radius:26px;box-shadow:var(--shadow-soft);padding:16px 18px;display:flex;align-items:flex-end;gap:12px;backdrop-filter:blur(14px)}
.composer textarea{flex:1;resize:none;border:none;outline:none;background:transparent;color:var(--text-primary);font-size:1rem;line-height:1.5;min-height:28px;max-height:180px;padding:2px 2px 4px 2px;overflow-y:auto}
.composer textarea::placeholder{color:var(--input-placeholder)}

/* ── Plus button (attach sheets) ── */
.composer-plus{width:38px;height:38px;border:none;border-radius:0;background:var(--send-bg);color:var(--send-color);display:inline-flex;align-items:center;justify-content:center;cursor:pointer;font-size:1.1rem;font-weight:700;font-family:"JetBrains Mono","Courier New",monospace;flex:0 0 auto;box-shadow:0 0 0 2px var(--text-secondary),3px 3px 0 0 rgba(0,0,0,.3);transition:transform .12s;clip-path:polygon(18% 0%,82% 0%,82% 9%,91% 9%,91% 18%,100% 18%,100% 82%,91% 82%,91% 91%,82% 91%,82% 100%,18% 100%,18% 91%,9% 91%,9% 82%,0% 82%,0% 18%,9% 18%,9% 9%,18% 9%)}
.composer-plus:hover{transform:translateY(-1px)}
.plus-menu{position:absolute;bottom:calc(100% + 8px);left:0;min-width:200px;padding:8px;border-radius:14px;background:var(--menu-bg);border:1px solid var(--menu-border);box-shadow:0 20px 50px rgba(0,0,0,.3);z-index:30;opacity:0;pointer-events:none;transition:opacity .16s}
.plus-menu.open{opacity:1;pointer-events:auto}
.plus-menu-item{width:100%;border:none;border-radius:10px;background:transparent;color:var(--menu-text);padding:10px 12px;cursor:pointer;text-align:left;font-size:.85rem;transition:background .14s}
.plus-menu-item:hover{background:var(--menu-hover)}
.sheets-row{display:flex;gap:8px;flex-wrap:wrap;padding:8px 0}

/* ──────────────────────────────────────────────────────────────
   Bouton + dans le composer : pièces jointes Image / Fichier
   ────────────────────────────────────────────────────────────── */
.attach-btn{width:36px;height:36px;border-radius:50%;border:1px solid var(--line);background:var(--input-bg);color:var(--text-secondary);display:inline-flex;align-items:center;justify-content:center;cursor:pointer;flex:0 0 36px;align-self:center;transition:background .14s,color .14s,border-color .14s,transform .12s}
.attach-btn:hover{background:var(--settings-tab-hover);color:var(--text-primary);border-color:var(--text-secondary);transform:translateY(-1px)}
.attach-btn:active{transform:translateY(0)}
.attach-btn svg{width:16px;height:16px;transition:transform .18s}
.attach-btn[aria-expanded="true"] svg{transform:rotate(45deg);color:var(--accent)}
.attach-menu{position:absolute;bottom:calc(100% + 12px);left:0;min-width:240px;padding:6px;border-radius:14px;background:var(--menu-bg);border:1px solid var(--menu-border);box-shadow:0 24px 48px rgba(0,0,0,.28);z-index:30;opacity:0;transform:translateY(6px) scale(.98);pointer-events:none;transition:opacity .16s,transform .16s}
.attach-menu.open{opacity:1;transform:translateY(0) scale(1);pointer-events:auto}
.attach-menu-item{width:100%;display:flex;align-items:center;gap:12px;border:none;border-radius:10px;background:transparent;color:var(--menu-text);padding:10px 12px;cursor:pointer;text-align:left;font-family:inherit;transition:background .14s}
.attach-menu-item:hover{background:var(--menu-hover)}
.attach-menu-item .attach-menu-icon{width:32px;height:32px;border-radius:9px;background:var(--surface-soft);display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;color:var(--text-primary)}
.attach-menu-item .attach-menu-icon svg{width:16px;height:16px}
.attach-menu-item .attach-menu-text{display:flex;flex-direction:column;gap:1px;flex:1;min-width:0}
.attach-menu-item .attach-menu-title{font-size:.86rem;font-weight:600;color:var(--text-primary)}
.attach-menu-item .attach-menu-hint{font-size:.72rem;color:var(--text-muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.attachments-row{display:flex;gap:8px;flex-wrap:wrap;padding:6px 4px 0}
.attachment-chip{position:relative;display:flex;align-items:center;gap:8px;padding:6px 28px 6px 8px;border-radius:12px;border:1px solid var(--line);background:var(--surface-soft);max-width:220px;transition:border-color .14s,transform .14s}
.attachment-chip:hover{border-color:var(--text-secondary);transform:translateY(-1px)}
.attachment-thumb{width:38px;height:38px;border-radius:9px;background:var(--menu-bg);display:inline-flex;align-items:center;justify-content:center;overflow:hidden;flex-shrink:0;color:var(--text-secondary)}
.attachment-thumb img{width:100%;height:100%;object-fit:cover}
.attachment-thumb svg{width:18px;height:18px}
.attachment-meta{display:flex;flex-direction:column;gap:1px;min-width:0}
.attachment-name{font-size:.78rem;font-weight:600;color:var(--text-primary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:140px}
.attachment-size{font-size:.68rem;color:var(--text-muted);font-family:"JetBrains Mono",monospace}
.attachment-remove{position:absolute;top:4px;right:4px;width:20px;height:20px;border-radius:50%;border:none;background:rgba(0,0,0,.55);color:#fff;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;font-size:.7rem;line-height:1;transition:background .14s}
.attachment-remove:hover{background:rgba(0,0,0,.8)}
.sheet-thumb{width:100px;height:80px;border-radius:10px;border:1px solid var(--line);background:var(--surface-soft);position:relative;overflow:hidden;display:flex;align-items:center;justify-content:center;font-size:.65rem;color:var(--text-secondary);padding:6px;word-break:break-all;line-height:1.2}
.sheet-thumb .sheet-remove{position:absolute;top:3px;right:3px;width:20px;height:20px;border-radius:50%;border:none;background:rgba(0,0,0,.6);color:#fff;font-size:.7rem;cursor:pointer;display:flex;align-items:center;justify-content:center}
.sheet-modal-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.5);backdrop-filter:blur(4px);z-index:80;display:none;align-items:center;justify-content:center}
.sheet-modal-backdrop.open{display:flex}
/* ── Modèles personnalisés (Settings → Personnalisation → Autres modèles) ── */
.custom-models-menu{min-width:240px;max-width:320px;max-height:380px;overflow-y:auto;padding:6px}
.custom-model-row{display:flex;align-items:center;gap:8px;width:100%;padding:8px 10px;border-radius:10px;border:none;background:transparent;color:var(--text-primary);cursor:pointer;text-align:left;transition:background .14s}
.custom-model-row:hover{background:var(--menu-hover)}
.custom-model-row.selected{background:rgba(var(--accent-rgb),.14);color:var(--accent)}
.custom-model-row .cmr-name{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-weight:600;font-size:.875rem}
.custom-model-row .cmr-actions{display:flex;gap:4px;flex-shrink:0;opacity:0;transition:opacity .14s}
.custom-model-row:hover .cmr-actions,.custom-model-row.selected .cmr-actions{opacity:1}
.custom-model-row .cmr-act-btn{border:none;background:transparent;color:var(--text-secondary);width:24px;height:24px;border-radius:6px;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;font-size:.85rem;transition:background .14s,color .14s}
.custom-model-row .cmr-act-btn:hover{background:var(--menu-hover);color:var(--text-primary)}
.custom-models-empty{padding:14px 12px;font-size:.8rem;color:var(--text-muted);text-align:center}
.custom-models-add-btn{width:100%;border:1px dashed var(--line);background:transparent;color:var(--text-primary);border-radius:10px;padding:10px;cursor:pointer;font-weight:600;font-size:.85rem;margin-top:6px;transition:background .14s,border-color .14s}
.custom-models-add-btn:hover{background:var(--menu-hover);border-color:var(--text-secondary)}
.custom-models-default-btn{width:100%;border:none;background:rgba(var(--accent-rgb),.1);color:var(--accent);border-radius:10px;padding:9px;cursor:pointer;font-weight:600;font-size:.8rem;margin-bottom:6px;transition:background .14s}
.custom-models-default-btn:hover{background:rgba(var(--accent-rgb),.18)}
.custom-models-sep{height:1px;background:var(--menu-border);margin:6px 4px}
.custom-model-error{color:#ef4444;font-size:.78rem;font-weight:600;min-height:1em}
.custom-model-error[hidden]{display:none}
/* Item de modèle standard désactivé (verrouillé tant qu'un modèle custom est actif) */
.model-dd-item.locked{opacity:.45;cursor:not-allowed}
.model-dd-item.locked:hover{background:transparent}
.sheet-modal{width:min(700px,calc(100vw - 40px));max-height:80vh;background:var(--settings-panel);border:1px solid var(--settings-panel-border);border-radius:20px;box-shadow:0 30px 70px rgba(0,0,0,.3);padding:24px;display:flex;flex-direction:column;gap:16px}
.sheet-modal h3{margin:0;font-size:1.1rem;color:var(--text-primary)}
.sheet-modal textarea{flex:1;min-height:300px;resize:vertical;border:1px solid var(--line);border-radius:14px;background:var(--bubble-assistant);color:var(--text-primary);padding:14px;font-size:.9rem;outline:none;font-family:inherit}
.sheet-modal-actions{display:flex;gap:10px;justify-content:flex-end}
.sheet-modal-actions button{padding:10px 20px;border-radius:0;border:none;cursor:pointer;font-size:.875rem;font-weight:700;font-family:"JetBrains Mono","Courier New",monospace;clip-path:polygon(8% 0%,92% 0%,92% 12%,100% 12%,100% 88%,92% 88%,92% 100%,8% 100%,8% 88%,0% 88%,0% 12%,8% 12%)}
.sheet-modal-actions .sheet-btn-add{background:var(--send-bg);color:var(--send-color);box-shadow:0 0 0 2px var(--text-secondary),3px 3px 0 0 rgba(0,0,0,.3)}
.sheet-modal-actions .sheet-btn-cancel{background:var(--surface-soft);color:var(--text-primary);box-shadow:0 0 0 2px var(--text-secondary),3px 3px 0 0 rgba(0,0,0,.2)}

/* ── Migration modal ── */
.migrate-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.5);backdrop-filter:blur(4px);z-index:80;display:none;align-items:center;justify-content:center}
.migrate-backdrop.open{display:flex}
.migrate-modal{width:min(700px,calc(100vw - 40px));max-height:85vh;overflow-y:auto;background:var(--settings-panel);border:1px solid var(--settings-panel-border);border-radius:20px;box-shadow:0 30px 70px rgba(0,0,0,.3);padding:24px;display:flex;flex-direction:column;gap:18px}
.migrate-modal h3{margin:0;font-size:1.15rem;color:var(--text-primary);display:flex;align-items:center;justify-content:space-between}
.migrate-modal h3 button{border:none;background:transparent;color:var(--text-secondary);font-size:1.3rem;cursor:pointer}
.migrate-step{font-size:.875rem;color:var(--text-secondary);font-weight:600}
.migrate-prompt-box{position:relative;background:var(--surface-soft);border:1px solid var(--line);border-radius:14px;padding:14px;font-size:.8rem;line-height:1.5;color:var(--text-primary);max-height:160px;overflow-y:auto;white-space:pre-wrap;font-family:"JetBrains Mono",monospace}
.migrate-copy-btn{display:block;margin:8px 0 0 auto;padding:6px 14px;border-radius:0;border:none;background:var(--send-bg);color:var(--send-color);font-size:.75rem;font-weight:700;cursor:pointer;font-family:"JetBrains Mono",monospace;clip-path:polygon(10% 0%,90% 0%,90% 15%,100% 15%,100% 85%,90% 85%,90% 100%,10% 100%,10% 85%,0% 85%,0% 15%,10% 15%)}
.migrate-textarea{min-height:150px;resize:vertical;border:1px solid var(--line);border-radius:14px;background:var(--bubble-assistant);color:var(--text-primary);padding:14px;font-size:.875rem;outline:none;font-family:inherit}
.migrate-actions{display:flex;gap:10px;justify-content:flex-end}
.migrate-actions button{padding:10px 20px;border-radius:0;border:none;cursor:pointer;font-size:.875rem;font-weight:700;font-family:"JetBrains Mono","Courier New",monospace;clip-path:polygon(8% 0%,92% 0%,92% 12%,100% 12%,100% 88%,92% 88%,92% 100%,8% 100%,8% 88%,0% 88%,0% 12%,8% 12%)}
.migrate-btn-add{background:var(--send-bg);color:var(--send-color);box-shadow:0 0 0 2px var(--text-secondary),3px 3px 0 0 rgba(0,0,0,.3);transition:opacity .14s}
.migrate-btn-add:disabled{opacity:.4;cursor:not-allowed}
.migrate-btn-cancel{background:var(--surface-soft);color:var(--text-primary);box-shadow:0 0 0 2px var(--text-secondary),3px 3px 0 0 rgba(0,0,0,.2)}

/* ── Send button pixel style ── */
.send-button,.voice-input-button{width:42px;height:42px;border:none;border-radius:0;background:var(--send-bg);color:var(--send-color);display:inline-flex;align-items:center;justify-content:center;cursor:pointer;flex:0 0 auto;box-shadow:var(--send-shadow);transition:transform .12s,opacity .12s,filter .12s;font-size:.95rem;font-weight:700;font-family:"JetBrains Mono","Courier New",monospace;clip-path:polygon(18% 0%,82% 0%,82% 9%,91% 9%,91% 18%,100% 18%,100% 82%,91% 82%,91% 91%,82% 91%,82% 100%,18% 100%,18% 91%,9% 91%,9% 82%,0% 82%,0% 18%,9% 18%,9% 9%,18% 9%)}
.voice-input-button{background:rgba(var(--accent-rgb),.08);color:var(--accent);box-shadow:0 0 0 2px rgba(var(--accent-rgb),.30),3px 3px 0 0 rgba(var(--accent-rgb),.15),0 8px 18px rgba(var(--accent-rgb),.10)}
.voice-input-button svg{width:18px;height:18px;stroke-width:2.25;display:block}
body[data-theme="dark"] .voice-input-button{background:rgba(var(--accent-rgb),.18);color:rgba(var(--accent-rgb),1);box-shadow:0 0 0 2px rgba(var(--accent-rgb),.32),3px 3px 0 0 rgba(var(--accent-rgb),.18),0 8px 18px rgba(0,0,0,.28)}
.send-button:hover,.voice-input-button:hover{transform:translateY(-1px);filter:brightness(1.04)}.send-button:disabled,.voice-input-button:disabled{cursor:default;opacity:.55;transform:none;filter:none}

/* ── Mode + Style rows ── */
.controls-row{display:flex;align-items:center;gap:10px;margin-top:12px;flex-wrap:wrap}
.mode-panel,.style-panel{position:relative;display:flex;flex-direction:column;align-items:flex-start;gap:8px}
.mode-trigger,.style-trigger{min-height:42px;padding:0 14px;border-radius:12px;border:1px solid var(--line);background:var(--surface-soft);color:var(--accent);box-shadow:var(--shadow-soft);display:inline-flex;align-items:center;gap:8px;cursor:pointer;font-size:.8125rem;font-weight:600;transition:transform .14s,box-shadow .14s,background .14s}
.mode-trigger:hover,.style-trigger:hover{transform:translateY(-1px)}
.mode-trigger[aria-expanded="true"],.style-trigger[aria-expanded="true"]{background:rgba(var(--accent-rgb),.12);border-color:rgba(var(--accent-rgb),.26)}
.trigger-icon{font-size:1rem;color:var(--accent)}.trigger-chevron{color:var(--text-secondary);font-size:.875rem}
.dropdown-menu{position:absolute;top:calc(100% + 10px);left:0;min-width:280px;padding:10px;border-radius:20px;background:var(--menu-bg);border:1px solid var(--menu-border);box-shadow:0 28px 60px rgba(0,0,0,.28);display:flex;flex-direction:column;gap:4px;z-index:20;opacity:0;transform:translateY(-6px) scale(.98);pointer-events:none;transition:opacity .16s,transform .16s}
.dropdown-menu.open{opacity:1;transform:translateY(0) scale(1);pointer-events:auto}
.dropdown-menu-item{width:100%;border:none;border-radius:14px;background:transparent;color:var(--menu-text);display:flex;align-items:center;gap:12px;padding:12px;cursor:pointer;text-align:left;transition:background .14s,transform .12s}
.dropdown-menu-item:hover{background:var(--menu-hover);transform:translateX(1px)}
.dropdown-menu-item.selected{background:var(--menu-selected)}
.dropdown-menu-item.disabled{opacity:.45;cursor:not-allowed}.dropdown-menu-item.disabled:hover{background:transparent;transform:none}
.dm-icon{width:22px;text-align:center;font-size:1rem;opacity:.95;flex:0 0 22px}
.dm-label{flex:1}.dm-check{color:#9ec1ff;opacity:0;transition:opacity .12s}.dropdown-menu-item.selected .dm-check{opacity:1}
.mode-announcement{font-size:.8125rem;color:var(--text-secondary);padding-left:8px;min-height:18px}
.status{width:min(760px,calc(100vw - 32px));min-height:18px;text-align:center;font-size:.8125rem;color:var(--status-color);line-height:1.35}
.settings-anchor,.newchat-anchor{position:fixed;left:18px;z-index:40;display:flex;align-items:center;gap:10px}
.settings-anchor{bottom:18px}.newchat-anchor{top:64px}
.settings-button,.newchat-button{width:52px;height:52px;border-radius:16px;border:1px solid var(--line);background:var(--bubble-user);color:var(--text-primary);box-shadow:var(--shadow-soft);display:inline-flex;align-items:center;justify-content:center;cursor:pointer;font-size:1.375rem;transition:transform .14s}
.settings-button:hover,.newchat-button:hover{transform:translateY(-1px)}
.settings-button-label,.newchat-button-label{padding:0 12px;height:36px;border-radius:999px;border:1px solid var(--line);background:var(--bubble-assistant);color:var(--text-secondary);display:inline-flex;align-items:center;font-size:.8125rem;box-shadow:var(--shadow-soft);opacity:0;transform:translateX(-4px);pointer-events:none;transition:opacity .14s,transform .14s}
.settings-anchor:hover .settings-button-label,.newchat-anchor:hover .newchat-button-label{opacity:1;transform:translateX(0)}
.settings-backdrop{position:fixed;inset:0;background:var(--settings-backdrop);backdrop-filter:blur(6px);z-index:60;opacity:0;transition:opacity .18s}.settings-backdrop.open{opacity:1}
.settings-modal{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);width:min(1080px,calc(100vw - 32px));height:min(760px,calc(100vh - 36px));min-height:560px;max-height:calc(100vh - 36px);border-radius:26px;overflow:hidden;background:var(--settings-panel);border:1px solid var(--settings-panel-border);box-shadow:0 32px 80px rgba(0,0,0,.32);z-index:70;display:grid;grid-template-columns:250px 1fr;opacity:0;transition:opacity .18s,transform .18s}
.settings-modal.open{opacity:1;transform:translate(-50%,-50%) scale(1)}
.settings-sidebar{background:var(--settings-sidebar);border-right:1px solid var(--settings-panel-border);border-radius:26px 0 0 26px;padding:18px;display:flex;flex-direction:column;gap:8px;overflow:hidden;position:relative}
.settings-close-row{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}.settings-close-row strong{color:var(--text-primary);font-size:.9375rem}
.settings-close{width:38px;height:38px;border-radius:12px;border:1px solid var(--line);background:transparent;color:var(--text-primary);cursor:pointer;display:inline-flex;align-items:center;justify-content:center;font-size:1.25rem}
.settings-tab{width:100%;min-height:46px;border:none;border-radius:14px;background:transparent;color:var(--text-primary);cursor:pointer;display:flex;align-items:center;gap:12px;padding:0 14px;text-align:left;transition:background .14s}
.settings-tab:hover{background:var(--settings-tab-hover)}.settings-tab.active{background:var(--settings-tab-active);color:var(--accent)}
.settings-tab-icon{width:18px;text-align:center;opacity:.9;flex:0 0 18px}
.settings-main{display:flex;flex-direction:column;min-width:0;min-height:0;overflow:hidden;max-height:100%}
.settings-header{padding:20px 24px 12px;border-bottom:1px solid var(--settings-row-border);cursor:grab;user-select:none;display:flex;align-items:center;justify-content:space-between;gap:16px}
.settings-header:active{cursor:grabbing}
.settings-header h2{margin:0;font-size:1.5rem;font-weight:600;color:var(--text-primary)}
.settings-header p{margin:6px 0 0;font-size:.8125rem;color:var(--text-secondary)}
.settings-hint{font-size:.75rem;color:var(--text-secondary);text-align:right;max-width:260px}
.settings-content{padding:12px 24px 24px;overflow-y:scroll;overflow-x:hidden;flex:1;min-height:0;scroll-behavior:smooth;overscroll-behavior:contain;scrollbar-gutter:stable}
.settings-section{display:none;flex-direction:column;gap:18px;min-height:0}.settings-section.active{display:flex;min-height:100%}
.settings-block{border-bottom:1px solid var(--settings-row-border);padding-bottom:18px}.settings-block:last-child{border-bottom:none;padding-bottom:0}
.settings-row{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:12px 0}
.settings-row-stack{display:flex;flex-direction:column;gap:6px}
.settings-row-title{font-size:1rem;color:var(--text-primary);font-weight:500}
.settings-row-subtitle{font-size:.8125rem;color:var(--text-secondary);line-height:1.4}
.settings-version-value{font-size:.9375rem;color:var(--text-primary);font-weight:600}
.settings-ghost-button{min-height:40px;padding:0 16px;border-radius:999px;border:1px solid var(--line);background:var(--bubble-user);color:var(--text-primary);cursor:pointer;box-shadow:var(--shadow-soft)}
.settings-choice-group{display:inline-flex;flex-wrap:wrap;gap:10px;justify-content:flex-end}
.settings-choice{min-height:38px;padding:0 14px;border-radius:999px;border:1px solid var(--line);background:var(--bubble-assistant);color:var(--text-primary);cursor:pointer}
.settings-choice.active{background:var(--accent-soft);border-color:var(--accent-border);color:var(--accent)}
.settings-input,.settings-textarea{width:min(420px,100%);border-radius:16px;border:1px solid var(--line);background:var(--bubble-assistant);color:var(--text-primary);padding:12px 14px;box-shadow:var(--shadow-soft);outline:none}
.settings-textarea{min-height:110px;resize:vertical}
.settings-state{display:inline-flex;align-items:center;justify-content:center;padding:6px 10px;border-radius:999px;font-size:.75rem;border:1px solid var(--line);background:var(--bubble-assistant);color:var(--text-secondary);min-width:92px;text-align:center}

/* ── Profile tab ── */
.profile-shell{display:flex;justify-content:center;padding:4px 0 16px;min-height:0}
.profile-stack{width:min(760px,100%);display:flex;flex-direction:column;gap:18px}
.profile-card{border:1px solid var(--settings-row-border);border-radius:24px;overflow:hidden;background:var(--bubble-assistant);box-shadow:var(--shadow-soft)}
.profile-banner{height:180px;background:linear-gradient(135deg,#1f2937 0%,var(--accent) 55%,#8b5cf6 100%);background-size:cover;background-position:center;position:relative}
.profile-banner::after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(15,23,42,.08),rgba(15,23,42,.34))}
.profile-card-body{padding:0 26px 26px;display:flex;flex-direction:column;gap:18px}
.profile-avatar-wrap{margin-top:-54px;position:relative;z-index:1}
.profile-avatar{width:108px;height:108px;border-radius:28px;object-fit:cover;border:4px solid var(--settings-panel);background:var(--surface-soft);box-shadow:var(--shadow-soft)}
.profile-headline{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;flex-wrap:wrap}
.profile-name-block{display:flex;flex-direction:column;gap:6px}
.profile-name{margin:0;font-size:1.45rem;font-weight:700;color:var(--text-primary)}
.profile-subline{font-size:.86rem;color:var(--text-secondary)}
.profile-description{margin:0;font-size:.95rem;line-height:1.65;color:var(--text-secondary)}
.profile-description.empty{color:var(--text-muted);font-style:italic}
.profile-metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.profile-metric{border:1px solid var(--settings-row-border);border-radius:18px;padding:14px 16px;background:var(--surface-soft);display:flex;flex-direction:column;gap:6px}
.profile-metric span{font-size:.8rem;color:var(--text-secondary)}
.profile-metric strong{font-size:1.1rem;color:var(--text-primary)}
.profile-section-title{font-size:.86rem;font-weight:700;color:var(--text-primary);text-transform:uppercase;letter-spacing:.04em}
.profile-socials{display:flex;flex-wrap:wrap;gap:10px}
.profile-social-link{display:inline-flex;align-items:center;justify-content:center;min-height:38px;padding:0 14px;border-radius:999px;border:1px solid var(--line);background:var(--surface-soft);color:var(--text-primary);text-decoration:none;transition:transform .14s,background .14s}
.profile-social-link:hover{transform:translateY(-1px);background:var(--settings-tab-hover)}
.profile-social-empty{font-size:.86rem;color:var(--text-muted)}
.profile-share-actions{display:flex;flex-wrap:wrap;gap:12px}
.profile-share-actions .settings-ghost-button{border-radius:14px}
.profile-share-actions .settings-ghost-button.primary{background:var(--send-bg);color:var(--send-color)}
.profile-editor{border:1px solid var(--settings-row-border);border-radius:24px;padding:18px;background:var(--surface-softer);display:flex;flex-direction:column;gap:16px;max-height:min(560px,calc(100vh - 280px));overflow-y:scroll;scrollbar-gutter:stable}
.profile-editor-header{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}
.profile-editor-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.profile-editor-grid .profile-span-2{grid-column:1 / -1}
.profile-upload-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.profile-upload-card{border:1px dashed var(--settings-row-border);border-radius:18px;padding:14px;background:var(--bubble-assistant);display:flex;flex-direction:column;gap:12px}
.profile-upload-title{font-size:.92rem;font-weight:600;color:var(--text-primary)}
.profile-upload-preview{height:92px;border-radius:14px;background:var(--surface-soft);border:1px solid var(--line);display:flex;align-items:center;justify-content:center;overflow:hidden;color:var(--text-muted);font-size:.82rem}
.profile-upload-preview img{width:100%;height:100%;object-fit:cover;object-position:center center;display:block}
.profile-upload-actions{display:flex;flex-wrap:wrap;gap:10px}
.profile-upload-actions .settings-ghost-button{border-radius:12px;min-height:38px}
.profile-helper{font-size:.8rem;color:var(--text-secondary)}
.profile-hidden-input{display:none}

.settings-tab-profile-footer{min-height:46px;padding:0 14px;border:none;border-radius:14px;background:transparent;display:flex;justify-content:flex-start;align-items:center;gap:12px;position:static;left:auto;right:auto;bottom:auto;z-index:auto;backdrop-filter:none;margin-top:auto}
.settings-tab-profile-footer.active{background:var(--settings-tab-active)}
.settings-profile-tab-avatar{width:42px;height:42px;border-radius:14px;object-fit:cover;object-position:center center;border:1px solid var(--line);background:var(--surface-soft);flex:0 0 42px}
.settings-profile-tab-copy{display:flex;flex-direction:column;min-width:0}
.settings-profile-tab-label{font-size:.92rem;font-weight:600;color:inherit}
.settings-profile-tab-name{font-size:.78rem;color:var(--text-secondary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:160px}
.settings-content::-webkit-scrollbar,.profile-editor::-webkit-scrollbar{width:12px}.settings-content::-webkit-scrollbar-thumb,.profile-editor::-webkit-scrollbar-thumb{background:color-mix(in srgb,var(--text-secondary) 34%,transparent);border-radius:999px;border:3px solid transparent;background-clip:padding-box}.settings-content::-webkit-scrollbar-track,.profile-editor::-webkit-scrollbar-track{background:transparent}
.brand-actions{display:none}.brand-add-button{width:auto;height:44px;padding:0 18px;gap:10px;border-radius:14px;clip-path:none;font-size:.9rem;font-weight:700}.brand-add-button .brand-add-icon{font-size:1rem;line-height:1}.brand-add-button .brand-add-label{line-height:1}.brand-plus-menu{top:calc(100% + 10px);bottom:auto;left:50%;transform:translateX(-50%)}.brand-plus-menu.open{transform:translateX(-50%)}
.settings-stepper{display:inline-flex;align-items:center;gap:10px;justify-content:flex-end}
.settings-stepper-value{min-width:82px;height:40px;padding:0 14px;border-radius:999px;border:1px solid var(--line);background:var(--bubble-assistant);color:var(--text-primary);display:inline-flex;align-items:center;justify-content:center;font-weight:600}
.profile-inline-toggle{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:14px 16px;border:1px solid var(--settings-row-border);border-radius:18px;background:var(--bubble-assistant)}
.profile-inline-toggle-text{display:flex;flex-direction:column;gap:4px}
.profile-inline-toggle-text strong{font-size:.95rem;color:var(--text-primary)}
.profile-inline-toggle-text span{font-size:.82rem;color:var(--text-secondary);line-height:1.4}
.profile-switch{position:relative;display:inline-flex;width:54px;height:30px;flex:0 0 54px}
.profile-switch input{position:absolute;inset:0;opacity:0;cursor:pointer}
.profile-switch-track{width:54px;height:30px;border-radius:999px;background:var(--surface-soft);border:1px solid var(--line);transition:background .14s,border-color .14s;display:block}
.profile-switch-track::after{content:"";position:absolute;top:3px;left:3px;width:22px;height:22px;border-radius:50%;background:#fff;box-shadow:0 2px 10px rgba(0,0,0,.22);transition:transform .14s}
.profile-switch input:checked + .profile-switch-track{background:var(--accent);border-color:var(--accent)}
.profile-switch input:checked + .profile-switch-track::after{transform:translateX(24px)}
.profile-security-note{font-size:.78rem;color:var(--text-secondary)}
.profile-avatar.is-logo,.settings-profile-tab-avatar.is-logo,.message-user-avatar img.is-logo,#profile-avatar-hover-image.is-logo,.profile-upload-preview img.is-logo{object-fit:contain;padding:6px;background:var(--surface-softer);box-sizing:border-box}
.profile-picker-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.62);backdrop-filter:blur(8px);z-index:96;display:none;align-items:center;justify-content:center;padding:20px}
.profile-picker-backdrop.open{display:flex}
.profile-picker-modal{width:min(880px,calc(100vw - 32px));max-height:calc(100vh - 32px);overflow:hidden;border-radius:28px;background:var(--settings-panel);border:1px solid var(--settings-panel-border);box-shadow:0 32px 80px rgba(0,0,0,.35);display:flex;flex-direction:column}
.profile-picker-header{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:18px 20px;border-bottom:1px solid var(--settings-row-border)}
.profile-picker-header strong{font-size:1.15rem;color:var(--text-primary)}
.profile-picker-header button{width:42px;height:42px;border-radius:14px;border:1px solid var(--line);background:transparent;color:var(--text-primary);cursor:pointer;font-size:1.2rem}
.profile-picker-body{padding:20px;display:flex;flex-direction:column;gap:18px;overflow:auto}
.profile-picker-section-title{font-size:2rem;font-weight:700;color:var(--text-primary);letter-spacing:-.03em}
.profile-picker-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}
.profile-picker-grid.banner-mode{grid-template-columns:repeat(3,minmax(0,1fr))}
.profile-picker-card{border:none;background:transparent;padding:0;display:flex;flex-direction:column;gap:10px;cursor:pointer;text-align:left}
.profile-picker-card-label{font-size:.86rem;font-weight:600;color:var(--text-primary)}
.profile-picker-thumb{height:170px;border-radius:22px;overflow:hidden;border:1px solid var(--line);background:var(--surface-soft);display:flex;align-items:center;justify-content:center;box-shadow:var(--shadow-soft);transition:transform .14s,border-color .14s}
.profile-picker-thumb.banner{height:132px}
.profile-picker-thumb img{width:100%;height:100%;object-fit:cover;object-position:center center;display:block}
.profile-picker-thumb img.is-logo{object-fit:contain;padding:14px;background:var(--surface-softer);box-sizing:border-box}
.profile-picker-card.import .profile-picker-thumb{border:1px dashed var(--settings-row-border);background:color-mix(in srgb,var(--surface-soft) 86%,transparent);color:var(--text-secondary);font-size:2rem;font-weight:700;flex-direction:column;gap:8px}
.profile-picker-card.import .profile-picker-thumb span{font-size:.9rem;font-weight:600;color:var(--text-primary)}
.profile-picker-card:hover .profile-picker-thumb{transform:translateY(-2px)}
@media(max-width:760px){.profile-picker-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.profile-picker-section-title{font-size:1.65rem}}
.profile-avatar-hover-card{position:fixed;z-index:125;display:flex;flex-direction:column;gap:0;border-radius:22px;overflow:hidden;background:var(--settings-panel);border:1px solid var(--settings-row-border);box-shadow:0 24px 64px rgba(0,0,0,.28);width:min(288px,calc(100vw - 24px));opacity:0;pointer-events:none;transform:translateY(8px) scale(.98);transition:opacity .16s,transform .16s}
.profile-avatar-hover-card.show{opacity:1;transform:translateY(0) scale(1)}
.profile-avatar-hover-banner{height:86px;background:linear-gradient(135deg,#1f2937 0%,var(--accent) 55%,#8b5cf6 100%);background-size:cover;background-position:center;position:relative}
.profile-avatar-hover-banner::after{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(15,23,42,.06),rgba(15,23,42,.28))}
.profile-avatar-hover-body{padding:0 14px 14px;display:flex;flex-direction:column;gap:10px}
.profile-avatar-hover-head{display:flex;align-items:flex-end;gap:10px;margin-top:-28px;position:relative;z-index:1}
.profile-avatar-hover-card img{width:72px;height:72px;object-fit:cover;border-radius:20px;border:3px solid var(--settings-panel);background:var(--surface-soft);box-shadow:var(--shadow-soft)}
.profile-avatar-hover-copy{display:flex;flex-direction:column;gap:4px;min-width:0;padding-bottom:6px}
.profile-avatar-hover-copy strong{font-size:.92rem;color:var(--text-primary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:170px}
.profile-avatar-hover-copy span{font-size:.78rem;color:var(--text-secondary);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;line-height:1.35}
.profile-crop-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.62);backdrop-filter:blur(8px);z-index:95;display:none;align-items:center;justify-content:center;padding:20px}
.profile-crop-backdrop.open{display:flex}
.profile-crop-modal{width:min(920px,calc(100vw - 32px));max-height:calc(100vh - 32px);overflow:hidden;border-radius:24px;background:var(--settings-panel);border:1px solid var(--settings-panel-border);box-shadow:0 32px 80px rgba(0,0,0,.35);display:flex;flex-direction:column}
.profile-crop-header{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:18px 20px;border-bottom:1px solid var(--settings-row-border)}
.profile-crop-header strong{font-size:1rem;color:var(--text-primary)}
.profile-crop-header button{width:38px;height:38px;border-radius:12px;border:1px solid var(--line);background:transparent;color:var(--text-primary);cursor:pointer}
.profile-crop-body{padding:18px 20px 10px;display:flex;flex-direction:column;gap:14px;min-height:0}
.profile-crop-canvas-wrap{position:relative;border-radius:20px;overflow:hidden;border:1px solid var(--line);background:#0b1020;min-height:300px;height:min(56vh,520px)}
#profile-crop-canvas{width:100%;height:100%;display:block;touch-action:none;cursor:grab}
#profile-crop-canvas.dragging{cursor:grabbing}
.profile-crop-controls{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.profile-crop-controls input[type="range"]{flex:1;min-width:180px}
.profile-crop-actions{display:flex;justify-content:flex-end;gap:12px;padding:0 20px 20px}
.profile-crop-actions .settings-ghost-button.primary{background:var(--send-bg);color:var(--send-color)}
@media(max-width:640px){.settings-tab-profile-footer{margin-top:0;position:static}.profile-crop-body{padding:14px}.profile-crop-canvas-wrap{height:46vh}.profile-crop-actions{padding:0 14px 14px}.profile-picker-body{padding:16px}.profile-picker-grid{grid-template-columns:1fr 1fr}.profile-picker-thumb{height:132px}.profile-picker-thumb.banner{height:108px}}

.tooltip{position:fixed;z-index:999;max-width:360px;padding:10px 12px;border-radius:12px;background:var(--tooltip-bg);color:var(--tooltip-text);border:1px solid var(--tooltip-border);box-shadow:0 24px 60px rgba(0,0,0,.28);font-size:.8125rem;line-height:1.35;pointer-events:none;opacity:0;transform:translateY(4px);transition:opacity .12s,transform .12s}
.tooltip.show{opacity:1;transform:translateY(0)}
[hidden]{display:none!important}
.calc-target-panel{position:relative;display:flex;flex-direction:column;align-items:flex-start;gap:8px}
#calc-target-menu{position:fixed;top:auto;left:auto;z-index:90}
.calc-target-notification{margin-top:-8px;padding:14px 16px;border-radius:14px;border:1px solid rgba(var(--accent-rgb),.22);background:rgba(var(--accent-rgb),.06);color:var(--text-primary);font-size:.86rem;line-height:1.5;animation:fadeSlideIn .3s ease}
@keyframes fadeSlideIn{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:translateY(0)}}
.thanks-text{text-align:center;font-size:1rem;font-weight:600;padding:18px 0 6px;color:var(--text-secondary)}
@media(max-width:900px){.settings-modal{width:min(1080px,calc(100vw - 18px));grid-template-columns:1fr}.settings-sidebar{border-right:none;border-bottom:1px solid var(--settings-panel-border)}.settings-header{cursor:default}.settings-hint{display:none}}
@media(max-width:640px){.composer{padding:14px;border-radius:22px}.bubble{max-width:92%}.controls-row{flex-wrap:wrap}.mode-announcement{padding-left:0}.dropdown-menu{min-width:min(280px,calc(100vw - 32px))}.settings-anchor{left:12px;bottom:12px}.newchat-anchor{left:12px;top:58px}.settings-modal{min-height:auto;max-height:calc(100vh - 24px)}.settings-header h2{font-size:1.25rem}.settings-row{flex-direction:column;align-items:flex-start}.settings-choice-group{justify-content:flex-start}.profile-metrics,.profile-editor-grid,.profile-upload-grid{grid-template-columns:1fr}.profile-card-body{padding:0 18px 18px}.voice-input-button{order:1}}

/* ── Character counter ── */
.char-counter{display:flex;align-items:center;justify-content:center;font-size:.7rem;color:var(--text-secondary);font-family:"JetBrains Mono",monospace;cursor:default;padding:2px 0;margin-top:2px;user-select:none;transition:color .2s}
.char-counter.warning{color:#f59e0b}
.char-counter.danger{color:#ef4444;font-weight:700}
.char-counter-tip{position:absolute;bottom:calc(100% + 6px);right:0;background:var(--tooltip-bg);color:var(--tooltip-text);padding:8px 12px;border-radius:10px;font-size:.75rem;white-space:nowrap;box-shadow:0 10px 24px rgba(0,0,0,.3);opacity:0;pointer-events:none;transition:opacity .16s;z-index:40}
.char-counter:hover .char-counter-tip{opacity:1;pointer-events:auto}

/* ── Stop button ── */
.stop-button{width:42px;height:42px;border:none;border-radius:0;background:#ef4444;color:#fff;display:inline-flex;align-items:center;justify-content:center;cursor:pointer;flex:0 0 auto;box-shadow:0 0 0 2px #b91c1c,3px 3px 0 0 rgba(0,0,0,.3);transition:transform .12s;font-size:.85rem;font-weight:700;font-family:"JetBrains Mono","Courier New",monospace;clip-path:polygon(18% 0%,82% 0%,82% 9%,91% 9%,91% 18%,100% 18%,100% 82%,91% 82%,91% 91%,82% 91%,82% 100%,18% 100%,18% 91%,9% 91%,9% 82%,0% 82%,0% 18%,9% 18%,9% 9%,18% 9%)}
.stop-button:hover{transform:translateY(-1px)}

/* ── Contraction Of Chat tag ── */
.contraction-tag{min-height:42px;padding:0 14px;border-radius:12px;border:1px solid rgba(239,68,68,.3);background:rgba(239,68,68,.08);color:#ef4444;display:inline-flex;align-items:center;gap:8px;font-size:.8125rem;font-weight:600;cursor:default;user-select:none;position:relative}
.contraction-tag .contraction-tip{position:absolute;bottom:calc(100% + 8px);left:0;background:var(--tooltip-bg);color:var(--tooltip-text);padding:8px 12px;border-radius:10px;font-size:.75rem;white-space:nowrap;box-shadow:0 10px 24px rgba(0,0,0,.3);opacity:0;pointer-events:none;transition:opacity .16s;z-index:40}
.contraction-tag:hover .contraction-tip{opacity:1;pointer-events:auto}
.contraction-tag[hidden]{display:none!important}

/* ── Overclock modal ── */
.overclock-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.6);backdrop-filter:blur(6px);z-index:90;display:none;align-items:center;justify-content:center}
.overclock-backdrop.open{display:flex}
.overclock-modal{width:min(600px,calc(100vw - 40px));max-height:80vh;overflow-y:auto;background:var(--settings-panel);border:1px solid var(--settings-panel-border);border-radius:20px;box-shadow:0 30px 70px rgba(0,0,0,.4);padding:28px;display:flex;flex-direction:column;gap:16px}
.overclock-modal h3{margin:0;font-size:1.15rem;color:#ef4444;font-weight:700;display:flex;align-items:center;gap:8px}
.overclock-modal .oc-warning-text{font-size:.85rem;color:var(--text-secondary);line-height:1.6}
.overclock-modal .oc-actions{display:flex;gap:10px;justify-content:flex-end;margin-top:8px}
.overclock-modal .oc-actions button{padding:10px 20px;border-radius:0;border:none;cursor:pointer;font-size:.875rem;font-weight:700;font-family:"JetBrains Mono","Courier New",monospace;clip-path:polygon(8% 0%,92% 0%,92% 12%,100% 12%,100% 88%,92% 88%,92% 100%,8% 100%,8% 88%,0% 88%,0% 12%,8% 12%)}
.oc-btn-confirm{background:#ef4444;color:#fff;box-shadow:0 0 0 2px #b91c1c,3px 3px 0 0 rgba(0,0,0,.3)}
.oc-btn-cancel{background:var(--surface-soft);color:var(--text-primary);box-shadow:0 0 0 2px var(--text-secondary),3px 3px 0 0 rgba(0,0,0,.2)}

/* ── Overclock toggle in settings ── */
.overclock-toggle{position:relative;width:52px;height:28px;border-radius:14px;border:2px solid var(--line);background:var(--surface-soft);cursor:pointer;transition:background .2s,border-color .2s;flex:0 0 52px}
.overclock-toggle::after{content:'';position:absolute;top:2px;left:2px;width:20px;height:20px;border-radius:50%;background:var(--text-secondary);transition:transform .2s,background .2s}
.overclock-toggle.active{background:rgba(239,68,68,.15);border-color:rgba(239,68,68,.4)}
.overclock-toggle.active::after{transform:translateX(24px);background:#ef4444}

/* ── Sheet char counter in modal ── */
.sheet-modal-header{display:flex;align-items:center;justify-content:space-between;gap:12px}
.sheet-char-counter{font-size:.75rem;color:var(--text-secondary);font-family:"JetBrains Mono",monospace}
.sheet-char-counter.danger{color:#ef4444;font-weight:700}

/* ── Font classes for AI responses ── */
body[data-aifont="arial"] .message-row.assistant .bubble{font-family:Arial,Helvetica,sans-serif}
body[data-aifont="opendyslexic"] .message-row.assistant .bubble{font-family:"OpenDyslexicCustom","OpenDyslexic-Regular","OpenDyslexic","Open Dyslexic",sans-serif;font-style:normal;font-weight:400;letter-spacing:.01em}
body[data-userfont="arial"] .message-row.user .bubble{font-family:Arial,Helvetica,sans-serif}
body[data-userfont="opendyslexic"] .message-row.user .bubble,body[data-userfont="opendyslexic"] textarea{font-family:"OpenDyslexicCustom","OpenDyslexic-Regular","OpenDyslexic","Open Dyslexic",sans-serif;font-style:normal;font-weight:400;letter-spacing:.01em}

.wallpaper-layer{position:fixed;inset:0;z-index:-2;overflow:hidden;background:var(--bg)}
.wallpaper-media{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:none}
.wallpaper-media.show{display:block}
.wallpaper-tint{position:absolute;inset:0;background:transparent;pointer-events:none}
body[data-wallpaper-active="on"] .wallpaper-tint{background:rgba(255,255,255,.68)}
body[data-theme="dark"][data-wallpaper-active="on"] .wallpaper-tint{background:rgba(22,22,22,.58)}
body[data-accent="blue"]{--accent:#3b82f6;--accent-rgb:59,130,246}
body[data-accent="red"]{--accent:#ef4444;--accent-rgb:239,68,68}
body[data-accent="green"]{--accent:#22c55e;--accent-rgb:34,197,94}
body[data-accent="yellow"]{--accent:#eab308;--accent-rgb:234,179,8}
body[data-accent="pink"]{--accent:#ec4899;--accent-rgb:236,72,153}
body[data-accent="purple"]{--accent:#8b5cf6;--accent-rgb:139,92,246}
.settings-tab-active-fallback,.settings-tab:hover{background:rgba(var(--accent-rgb),.08)}
.settings-tab.active{background:rgba(var(--accent-rgb),.14)}
.profile-social-link:hover{background:rgba(var(--accent-rgb),.08)}
.appearance-swatch-group{display:inline-flex;flex-wrap:wrap;gap:10px;justify-content:flex-end}
.appearance-swatch{width:42px;height:42px;border-radius:999px;border:2px solid transparent;cursor:pointer;position:relative;box-shadow:var(--shadow-soft)}
.appearance-swatch.active{border-color:var(--text-primary);transform:scale(1.04)}
.appearance-swatch::after{content:"";position:absolute;inset:7px;border-radius:999px;background:var(--swatch,#3b82f6)}
.wallpaper-preview-card{border:1px solid var(--settings-row-border);border-radius:18px;background:var(--bubble-assistant);padding:16px;display:flex;flex-direction:column;gap:14px}
.wallpaper-preview-box{height:124px;border-radius:16px;border:1px solid var(--line);background:var(--surface-soft);overflow:hidden;position:relative;display:flex;align-items:center;justify-content:center;color:var(--text-secondary);font-size:.82rem}
.wallpaper-preview-box img,.wallpaper-preview-box video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.wallpaper-preview-box .label{position:relative;z-index:1;padding:8px 12px;border-radius:999px;background:rgba(255,255,255,.7);color:#111827}

/* ── Badge BÊTA ── */
.beta-badge{display:inline-flex;align-items:center;padding:2px 8px;border-radius:999px;background:rgba(234,179,8,.15);border:1px solid rgba(234,179,8,.35);color:#ca8a04;font-size:.65rem;font-weight:700;letter-spacing:.06em;margin-left:8px;vertical-align:middle;user-select:none}
body[data-theme="dark"] .beta-badge{background:rgba(234,179,8,.18);border-color:rgba(234,179,8,.32);color:#fbbf24}

/* ── Modal contact développeur ── */
.aide-contact-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.55);backdrop-filter:blur(6px);z-index:95;display:none;align-items:center;justify-content:center;padding:20px}
.aide-contact-backdrop.open{display:flex}
.aide-contact-modal{width:min(480px,calc(100vw - 40px));background:var(--settings-panel);border:1px solid var(--settings-panel-border);border-radius:24px;box-shadow:0 32px 80px rgba(0,0,0,.34);padding:32px;display:flex;flex-direction:column;gap:24px;align-items:center}
.aide-contact-modal h3{margin:0;font-size:1.25rem;font-weight:700;color:var(--text-primary);text-align:center}
.aide-contact-modal p{margin:0;font-size:.9rem;color:var(--text-secondary);text-align:center;line-height:1.5}
.aide-contact-cards{display:flex;gap:16px;flex-wrap:wrap;justify-content:center;width:100%}
.aide-contact-card{flex:1;min-width:140px;max-width:180px;border:1px solid var(--settings-row-border);border-radius:20px;background:var(--bubble-assistant);padding:24px 16px;display:flex;flex-direction:column;align-items:center;gap:12px;cursor:pointer;transition:transform .14s,box-shadow .14s,background .14s;text-decoration:none;color:var(--text-primary)}
.aide-contact-card:hover{transform:translateY(-3px);box-shadow:0 16px 40px rgba(0,0,0,.14);background:var(--settings-tab-hover)}
.aide-contact-card.disabled{opacity:.45;cursor:not-allowed;pointer-events:none}
.aide-contact-card svg{width:44px;height:44px;flex:0 0 44px}
.aide-contact-card-label{font-size:.9rem;font-weight:600;color:var(--text-primary)}
.aide-contact-card-sub{font-size:.75rem;color:var(--text-secondary);text-align:center}
.aide-contact-close{min-height:42px;padding:0 24px;border-radius:14px;border:1px solid var(--line);background:var(--surface-soft);color:var(--text-primary);cursor:pointer;font-size:.9rem;font-weight:600;font-family:inherit;transition:transform .14s}
.aide-contact-close:hover{transform:translateY(-1px)}
body[data-theme="dark"] .wallpaper-preview-box .label{background:rgba(17,24,39,.72);color:#f8fafc}
.wallpaper-actions{display:flex;flex-wrap:wrap;gap:10px}
.wallpaper-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.55);backdrop-filter:blur(8px);z-index:97;display:none;align-items:center;justify-content:center;padding:20px}
.wallpaper-backdrop.open{display:flex}
.wallpaper-modal{width:min(760px,calc(100vw - 32px));max-height:calc(100vh - 32px);overflow:auto;border-radius:26px;background:var(--settings-panel);border:1px solid var(--settings-panel-border);box-shadow:0 32px 80px rgba(0,0,0,.35);display:flex;flex-direction:column}
.wallpaper-modal-header{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:18px 20px;border-bottom:1px solid var(--settings-row-border)}
.wallpaper-modal-header strong{font-size:1.15rem;color:var(--text-primary)}
.wallpaper-modal-header button{width:42px;height:42px;border-radius:14px;border:1px solid var(--line);background:transparent;color:var(--text-primary);cursor:pointer;font-size:1.2rem}
.wallpaper-modal-body{padding:20px;display:flex;flex-direction:column;gap:16px}
.wallpaper-modal-target{font-size:.88rem;color:var(--text-secondary)}
.wallpaper-url-row{display:flex;gap:10px;flex-wrap:wrap}
.wallpaper-url-row .settings-input{flex:1;min-width:260px;width:auto}

/* ──────────────────────────────────────────────────────────────
   Barre latérale (sidebar) — design refondu
   Structure : topbar │ primary CTA │ search │ pinned │ tabs │
               content │ footer (profil + paramètres)
   ────────────────────────────────────────────────────────────── */
.sidebar-overlay{position:fixed;inset:0;background:rgba(0,0,0,.28);backdrop-filter:blur(4px);-webkit-backdrop-filter:blur(4px);z-index:100;opacity:0;pointer-events:none;transition:opacity .26s cubic-bezier(.4,0,.2,1)}
.sidebar-overlay.open{opacity:1;pointer-events:auto}
.sidebar-panel{position:fixed;top:0;left:0;height:100vh;width:312px;max-width:calc(100vw - 36px);background:var(--settings-panel);border-right:1px solid var(--settings-panel-border);box-shadow:8px 0 36px rgba(0,0,0,.16);z-index:101;display:flex;flex-direction:column;transform:translateX(-100%);transition:transform .28s cubic-bezier(.4,0,.2,1);overflow:hidden}
.sidebar-panel.open{transform:translateX(0)}

/* Topbar : brand + bouton fermer */
.sidebar-topbar{display:flex;align-items:center;justify-content:space-between;padding:16px 14px 8px;gap:8px}
.sidebar-brand-wrap{display:flex;align-items:center;gap:10px;flex:1;min-width:0}
.sidebar-brand-mark{width:28px;height:28px;border-radius:8px;background:linear-gradient(135deg,var(--accent),rgba(var(--accent-rgb),.55));display:inline-flex;align-items:center;justify-content:center;color:#fff;font-size:.78rem;font-weight:800;flex-shrink:0;letter-spacing:-.02em;overflow:hidden}
.sidebar-brand-mark img{width:100%;height:100%;object-fit:cover;display:block}
.sidebar-brand-mark img[src=""],.sidebar-brand-mark img:not([src]){display:none}
/* Quand un vrai logo est présent, on retire le dégradé bleu derrière */
.sidebar-brand-mark.has-logo{background:transparent}
.sidebar-brand{font-size:.92rem;font-weight:700;color:var(--text-primary);letter-spacing:-.01em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sidebar-icon-btn{width:30px;height:30px;border-radius:9px;border:none;background:transparent;color:var(--text-secondary);cursor:pointer;display:inline-flex;align-items:center;justify-content:center;flex:0 0 30px;transition:background .14s,color .14s}
.sidebar-icon-btn:hover{background:var(--settings-tab-hover);color:var(--text-primary)}
.sidebar-icon-btn svg{width:16px;height:16px}

/* Bouton primaire : Nouvelle discussion */
.sidebar-section{padding:4px 10px}
.sidebar-primary-btn{width:100%;height:42px;border-radius:12px;border:1px solid var(--accent-border);background:var(--accent-soft);color:var(--accent);cursor:pointer;font-size:.86rem;font-weight:600;font-family:inherit;display:flex;align-items:center;gap:10px;padding:0 14px;transition:background .16s,transform .13s,box-shadow .16s;box-shadow:0 1px 4px rgba(var(--accent-rgb),.08)}
.sidebar-primary-btn:hover{background:rgba(var(--accent-rgb),.18);transform:translateY(-1px);box-shadow:0 6px 16px rgba(var(--accent-rgb),.18)}
.sidebar-primary-btn:active{transform:translateY(0);box-shadow:none}
.sidebar-primary-btn svg{width:16px;height:16px;flex-shrink:0}

/* Recherche */
.sidebar-search-inner{position:relative;display:flex;align-items:center}
.sidebar-search-icon{position:absolute;left:12px;color:var(--text-muted);pointer-events:none;display:inline-flex}
.sidebar-search-icon svg{width:14px;height:14px}
.sidebar-search{width:100%;height:38px;border-radius:11px;border:1px solid var(--line);background:var(--input-bg);color:var(--text-primary);padding:0 14px 0 36px;font-size:.84rem;outline:none;font-family:inherit;transition:border-color .14s,box-shadow .14s}
.sidebar-search:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(var(--accent-rgb),.12)}
.sidebar-search::placeholder{color:var(--input-placeholder)}

/* Section "Épinglés" — état vide façon Cowork */
.sidebar-pinned-wrap{padding:14px 14px 6px}
.sidebar-section-title{font-size:.72rem;font-weight:700;color:var(--text-muted);letter-spacing:.06em;text-transform:uppercase;user-select:none;margin-bottom:6px}
.sidebar-pinned-empty{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:10px;color:var(--text-muted);font-size:.8rem;border:1px dashed var(--line);background:transparent}
.sidebar-pinned-empty svg{width:14px;height:14px;flex-shrink:0;opacity:.7}

/* Onglets */
.sidebar-tabs{display:flex;padding:0 14px;gap:4px;border-bottom:1px solid var(--line);margin-top:8px}
.sidebar-tab{flex:1;height:36px;border:none;background:transparent;color:var(--text-secondary);cursor:pointer;font-size:.81rem;font-weight:600;font-family:inherit;border-bottom:2px solid transparent;margin-bottom:-1px;transition:color .14s,border-color .14s}
.sidebar-tab.active{color:var(--accent);border-bottom-color:var(--accent)}
.sidebar-tab:hover:not(.active){color:var(--text-primary)}

/* Contenu scrollable */
.sidebar-content{flex:1;overflow-y:auto;padding:8px 8px 6px;scrollbar-width:thin;scrollbar-color:var(--line) transparent}
.sidebar-content::-webkit-scrollbar{width:6px}
.sidebar-content::-webkit-scrollbar-thumb{background:var(--line);border-radius:6px}
.sidebar-action-item{width:100%;border:none;background:transparent;color:var(--text-primary);text-align:left;padding:9px 12px;border-radius:10px;cursor:pointer;font-size:.84rem;font-family:inherit;display:flex;align-items:center;gap:11px;transition:background .14s;line-height:1.4}
.sidebar-action-item:hover{background:var(--settings-tab-hover)}
.sidebar-action-item svg{width:16px;height:16px;flex-shrink:0;color:var(--text-secondary);transition:color .14s}
.sidebar-action-item:hover svg{color:var(--text-primary)}
.sidebar-empty{padding:28px 14px;color:var(--text-muted);font-size:.82rem;text-align:center;line-height:1.6}

/* Footer : profil utilisateur + bouton paramètres */
.sidebar-footer{padding:10px 10px 14px;border-top:1px solid var(--line);display:flex;align-items:center;gap:8px}
.sidebar-profile{flex:1;display:flex;align-items:center;gap:10px;padding:6px 8px;border-radius:11px;cursor:pointer;transition:background .14s;min-width:0}
.sidebar-profile:hover{background:var(--settings-tab-hover)}
.sidebar-profile-avatar{width:30px;height:30px;border-radius:50%;background:linear-gradient(135deg,var(--accent),rgba(var(--accent-rgb),.55));display:inline-flex;align-items:center;justify-content:center;color:#fff;font-size:.74rem;font-weight:700;flex-shrink:0;letter-spacing:-.02em;overflow:hidden}
.sidebar-profile-avatar img{width:100%;height:100%;object-fit:cover}
.sidebar-profile-name{font-size:.84rem;font-weight:600;color:var(--text-primary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex:1;min-width:0}
.sidebar-settings-icon-btn{width:34px;height:34px;border-radius:10px;border:1px solid transparent;background:transparent;color:var(--text-secondary);cursor:pointer;display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;transition:background .14s,color .14s,border-color .14s}
.sidebar-settings-icon-btn:hover{background:var(--settings-tab-hover);color:var(--text-primary);border-color:var(--line)}
.sidebar-settings-icon-btn svg{width:16px;height:16px}

/* ── Système "Créer un fichier" : modale + items + popover d'actions ── */
.sf-modal-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.5);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px);z-index:140;display:none;align-items:center;justify-content:center;padding:20px;opacity:0;transition:opacity .18s}
.sf-modal-backdrop.open{display:flex;opacity:1}
.sf-modal{width:min(420px,100%);background:var(--settings-panel);border:1px solid var(--settings-panel-border);border-radius:18px;box-shadow:0 28px 70px rgba(0,0,0,.32);padding:22px 22px 18px;display:flex;flex-direction:column;gap:14px;transform:translateY(8px);transition:transform .18s}
.sf-modal-backdrop.open .sf-modal{transform:translateY(0)}
.sf-modal-title{font-size:1.05rem;font-weight:700;color:var(--text-primary)}
.sf-modal-input{height:42px;border-radius:11px;border:1px solid var(--line);background:var(--input-bg);color:var(--text-primary);padding:0 14px;font-size:.9rem;outline:none;font-family:inherit;transition:border-color .14s,box-shadow .14s}
.sf-modal-input:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(var(--accent-rgb),.12)}
.sf-modal-actions{display:flex;justify-content:flex-end;gap:8px;margin-top:4px}
.sf-modal-btn{height:38px;padding:0 16px;border-radius:11px;font-size:.85rem;font-weight:600;font-family:inherit;cursor:pointer;border:1px solid var(--line);background:transparent;color:var(--text-primary);transition:background .14s,filter .14s}
.sf-modal-btn:hover{background:var(--settings-tab-hover)}
.sf-modal-btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}
.sf-modal-btn.primary:hover{filter:brightness(1.08);background:var(--accent)}
.sf-item{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:10px;cursor:pointer;color:var(--text-primary);font-size:.84rem;transition:background .14s;position:relative;line-height:1.4}
.sf-item:hover,.sf-item.menu-open{background:var(--settings-tab-hover)}
.sf-item-icon{width:16px;height:16px;flex-shrink:0;color:var(--text-secondary)}
.sf-item-name{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.sf-item-more{width:26px;height:26px;border-radius:8px;border:none;background:transparent;color:var(--text-secondary);cursor:pointer;display:inline-flex;align-items:center;justify-content:center;flex-shrink:0;opacity:0;transition:opacity .14s,background .14s,color .14s}
.sf-item:hover .sf-item-more,.sf-item.menu-open .sf-item-more{opacity:1}
.sf-item-more:hover{background:var(--line);color:var(--text-primary)}
.sf-item-more svg{width:14px;height:14px}
.sf-popover{position:fixed;min-width:170px;background:var(--menu-bg);border:1px solid var(--menu-border);border-radius:12px;box-shadow:0 18px 40px rgba(0,0,0,.28);padding:6px;display:none;flex-direction:column;gap:2px;z-index:142}
.sf-popover.open{display:flex}
.sf-popover-item{height:34px;padding:0 12px;border-radius:8px;border:none;background:transparent;color:var(--text-primary);text-align:left;cursor:pointer;font-size:.84rem;font-family:inherit;display:flex;align-items:center;gap:9px;transition:background .14s}
.sf-popover-item:hover{background:var(--settings-tab-hover)}
.sf-popover-item.danger{color:#dc2626}
.sf-popover-item.danger:hover{background:rgba(220,38,38,.10)}
.sf-popover-item svg{width:14px;height:14px;flex-shrink:0}

/* ── Boutons gauche Apple-style quasi-transparent ── */
.left-buttons-anchor{position:fixed;left:16px;top:62px;z-index:40;display:flex;flex-direction:column;align-items:center;gap:7px}
.sidebar-toggle-btn{width:40px;height:40px;border-radius:12px;border:1px solid var(--action-border);background:var(--action-bg);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);color:var(--text-primary);display:inline-flex;align-items:center;justify-content:center;cursor:pointer;font-size:1.05rem;box-shadow:0 2px 10px rgba(0,0,0,.07);transition:transform .14s,background .14s}
.sidebar-toggle-btn:hover{transform:translateY(-1px);background:var(--settings-tab-hover)}
/* Override newchat-button and settings-button to Apple style */
.newchat-button{width:40px!important;height:40px!important;border-radius:12px!important;border:1px solid var(--action-border)!important;background:var(--action-bg)!important;backdrop-filter:blur(14px)!important;-webkit-backdrop-filter:blur(14px)!important;box-shadow:0 2px 10px rgba(0,0,0,.07)!important;font-size:1.1rem!important}
.settings-button{width:40px!important;height:40px!important;border-radius:12px!important;border:1px solid var(--action-border)!important;background:var(--action-bg)!important;backdrop-filter:blur(14px)!important;-webkit-backdrop-filter:blur(14px)!important;box-shadow:0 2px 10px rgba(0,0,0,.07)!important;font-size:1.05rem!important}

/* ──────────────────────────────────────────────────────────────
   Barre de menu façon logiciel (Fichier / Édition / Aide)
   Ancrée tout en haut, pleine largeur, opaque pour masquer
   complètement le fond d'écran sous la zone d'en-tête.
   IMPORTANT : seul le label (.app-menubar-label) est visible ;
   les dropdowns sont en position absolue + display:none par défaut.
   ────────────────────────────────────────────────────────────── */
.app-menubar{position:fixed;top:0;left:0;right:0;z-index:90;display:flex;align-items:stretch;height:30px;padding:0 6px;background:var(--bg);user-select:none;overflow:visible}
body[data-theme="dark"] .app-menubar{background:var(--bg)}
/* Sécurité : on force la barre à rester opaque même quand un fond
   d'écran est actif (la barre doit toujours masquer l'image). */
body[data-wallpaper-active="on"] .app-menubar{background:var(--bg)!important}
body[data-theme="dark"][data-wallpaper-active="on"] .app-menubar{background:var(--bg)!important}
.app-menubar-item{position:relative;display:inline-flex;align-items:center;height:100%;padding:0;cursor:pointer;border:none;background:transparent;outline:none}
.app-menubar-label{display:inline-flex;align-items:center;height:100%;padding:0 12px;font-size:.82rem;color:var(--text-primary);border-radius:6px;transition:background .12s;white-space:nowrap}
.app-menubar-item:hover .app-menubar-label,.app-menubar-item.open .app-menubar-label{background:var(--settings-tab-hover)}
.app-menubar-dropdown{position:absolute;top:100%;left:0;min-width:260px;background:var(--settings-panel);border:1px solid var(--settings-panel-border);border-radius:10px;box-shadow:0 18px 46px rgba(15,23,42,.18);padding:6px;display:none;flex-direction:column;gap:2px;z-index:91;overflow:hidden;white-space:nowrap}
.app-menubar-item.open>.app-menubar-dropdown{display:flex}
.app-menubar-dd-item{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:7px 10px;border-radius:7px;font-size:.82rem;color:var(--text-primary);cursor:pointer;background:transparent;border:none;text-align:left;width:100%;white-space:nowrap}
.app-menubar-dd-item:hover{background:var(--settings-tab-hover)}
.app-menubar-dd-item.disabled{color:var(--text-muted);cursor:default}
.app-menubar-dd-item.disabled:hover{background:transparent}
.app-menubar-dd-shortcut{font-size:.74rem;color:var(--text-secondary);font-family:"JetBrains Mono",monospace;letter-spacing:.02em}
.app-menubar-dd-sep{height:1px;background:var(--settings-row-border);margin:4px 2px}

/* Décale les éléments fixes pour ne pas chevaucher la menubar (30px) */
.top-tab-bar{top:30px!important;background:var(--bg)!important}
/* Sécurité : la top-tab-bar reste opaque même avec fond d'écran. */
body[data-wallpaper-active="on"] .top-tab-bar{background:var(--bg)!important}
body[data-theme="dark"][data-wallpaper-active="on"] .top-tab-bar{background:var(--bg)!important}
.left-buttons-anchor{top:calc(62px + 30px)}
.private-chat-btn{top:calc(73px + 30px)!important}
.private-chat-btn .pc-tooltip{top:calc(116px + 30px)!important}
.settings-anchor{bottom:18px}

/* ──────────────────────────────────────────────────────────────
   Toggle "Version de prévisualisation" (interrupteur dans Général)
   ────────────────────────────────────────────────────────────── */
.preview-switch{position:relative;display:inline-block;width:44px;height:24px}
.preview-switch input{opacity:0;width:0;height:0}
.preview-switch-track{position:absolute;cursor:pointer;inset:0;background:rgba(148,163,184,.4);border-radius:999px;transition:background .18s}
.preview-switch-track::before{content:"";position:absolute;height:18px;width:18px;left:3px;top:3px;background:#fff;border-radius:50%;transition:transform .18s;box-shadow:0 1px 3px rgba(0,0,0,.2)}
.preview-switch input:checked+.preview-switch-track{background:var(--accent)}
.preview-switch input:checked+.preview-switch-track::before{transform:translateX(20px)}

/* Quand la prévisualisation est désactivée, on cache toutes les fonctions
   expérimentales sans toucher au DOM (réversible immédiat). */
body[data-preview="off"] .mode-panel,
body[data-preview="off"] .style-panel,
body[data-preview="off"] #attach-btn,
body[data-preview="off"] .attach-wrap,
body[data-preview="off"] #sidebar-toggle-btn,
body[data-preview="off"] #private-chat-btn,
body[data-preview="off"] [data-settings-tab="connectors"],
body[data-preview="off"] [data-settings-content="connectors"],
body[data-preview="off"] [data-preview-only="1"]{display:none!important}

/* ──────────────────────────────────────────────────────────────
   Modale d'avertissement (activation prévisualisation)
   ────────────────────────────────────────────────────────────── */
.preview-warning-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.55);backdrop-filter:blur(8px);z-index:130;display:none;align-items:center;justify-content:center;padding:20px}
.preview-warning-backdrop.open{display:flex}
.preview-warning-modal{width:min(460px,calc(100vw - 40px));background:var(--settings-panel);border:1px solid var(--settings-panel-border);border-radius:18px;box-shadow:0 32px 80px rgba(0,0,0,.34);padding:24px;display:flex;flex-direction:column;gap:14px}
.preview-warning-modal h3{margin:0;color:var(--text-primary);font-size:1.05rem}
.preview-warning-modal p{margin:0;color:var(--text-secondary);font-size:.9rem;line-height:1.5}
.preview-warning-actions{display:flex;justify-content:flex-end;gap:10px;margin-top:6px}

/* ──────────────────────────────────────────────────────────────
   Onglet Connecteurs : modale + liste vide + bouton custom
   ────────────────────────────────────────────────────────────── */
.connectors-modal-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.5);backdrop-filter:blur(6px);z-index:130;display:none;align-items:center;justify-content:center;padding:20px}
.connectors-modal-backdrop.open{display:flex}
.connectors-modal{width:min(560px,calc(100vw - 40px));max-height:calc(100vh - 60px);overflow:auto;background:var(--settings-panel);border:1px solid var(--settings-panel-border);border-radius:20px;box-shadow:0 32px 80px rgba(0,0,0,.32);padding:24px;display:flex;flex-direction:column;gap:18px}
.connectors-modal-header{display:flex;align-items:center;justify-content:space-between;gap:14px}
.connectors-modal-header h3{margin:0;color:var(--text-primary);font-size:1.1rem}
.connectors-modal-close{width:36px;height:36px;border-radius:10px;border:1px solid var(--line);background:transparent;color:var(--text-primary);cursor:pointer;font-size:1.05rem}
.connectors-empty-card{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:6px;padding:38px 18px;border:1px dashed var(--settings-row-border);border-radius:14px;background:var(--surface-soft);color:var(--text-secondary);text-align:center}
.connectors-empty-card strong{color:var(--text-primary);font-size:1rem}
.connectors-empty-card span{font-size:.85rem}
.connectors-modal-footer{display:flex;justify-content:flex-end;gap:10px}

</style>
</head>
<body data-theme="light" data-effects="on" data-textsize="default" data-active-tab="chat" data-accent="blue" data-wallpaper-active="off" data-cw-wallpaper="off" data-preview="on">
<div class="wallpaper-layer" id="wallpaper-layer" aria-hidden="true"><img class="wallpaper-media" id="wallpaper-image" alt=""><video class="wallpaper-media" id="wallpaper-video" autoplay muted loop playsinline></video><div class="wallpaper-tint"></div></div>

<!-- ──────────────────────────────────────────────────────────────
     Barre de menu façon logiciel (Fichier / Édition / Aide)
     IMPORTANT : on utilise <div> pour le déclencheur, car un <button>
     ne peut pas contenir d'autres <button> (le navigateur les déplie).
     ────────────────────────────────────────────────────────────── -->
<nav class="app-menubar" id="app-menubar" aria-label="Menu principal">
  <div class="app-menubar-item" id="menu-file-btn" tabindex="0" role="button" aria-haspopup="true" aria-expanded="false">
    <span class="app-menubar-label" data-i18n="menu_file">Fichier</span>
    <div class="app-menubar-dropdown" id="menu-file-dd" role="menu">
      <button type="button" class="app-menubar-dd-item" data-menu-action="open-location" role="menuitem"><span data-i18n="menu_open_location">Emplacement du/des programmes</span></button>
      <div class="app-menubar-dd-sep"></div>
      <button type="button" class="app-menubar-dd-item" data-menu-action="open-settings" role="menuitem"><span data-i18n="menu_settings">Paramètres</span></button>
      <button type="button" class="app-menubar-dd-item" data-menu-action="new-chat" role="menuitem"><span data-i18n="menu_new_chat">Nouvelle conversation</span></button>
    </div>
  </div>
  <div class="app-menubar-item" id="menu-edit-btn" tabindex="0" role="button" aria-haspopup="true" aria-expanded="false">
    <span class="app-menubar-label" data-i18n="menu_edit">Édition</span>
    <div class="app-menubar-dropdown" id="menu-edit-dd" role="menu">
      <button type="button" class="app-menubar-dd-item" data-menu-action="undo" role="menuitem"><span data-i18n="shortcut_undo">Annuler</span><span class="app-menubar-dd-shortcut">Ctrl+Z</span></button>
      <button type="button" class="app-menubar-dd-item" data-menu-action="redo" role="menuitem"><span data-i18n="shortcut_redo">Rétablir</span><span class="app-menubar-dd-shortcut">Ctrl+Maj+Z</span></button>
      <div class="app-menubar-dd-sep"></div>
      <button type="button" class="app-menubar-dd-item" data-menu-action="cut" role="menuitem"><span data-i18n="shortcut_cut">Couper</span><span class="app-menubar-dd-shortcut">Ctrl+X</span></button>
      <button type="button" class="app-menubar-dd-item" data-menu-action="copy" role="menuitem"><span data-i18n="shortcut_copy">Copier</span><span class="app-menubar-dd-shortcut">Ctrl+C</span></button>
      <button type="button" class="app-menubar-dd-item" data-menu-action="paste" role="menuitem"><span data-i18n="shortcut_paste">Coller</span><span class="app-menubar-dd-shortcut">Ctrl+V</span></button>
      <button type="button" class="app-menubar-dd-item" data-menu-action="select-all" role="menuitem"><span data-i18n="shortcut_select_all">Tout sélectionner</span><span class="app-menubar-dd-shortcut">Ctrl+A</span></button>
      <div class="app-menubar-dd-sep"></div>
      <button type="button" class="app-menubar-dd-item" data-menu-action="find" role="menuitem"><span data-i18n="shortcut_find">Rechercher</span><span class="app-menubar-dd-shortcut">Ctrl+F</span></button>
    </div>
  </div>
  <div class="app-menubar-item" id="menu-help-btn" tabindex="0" role="button" aria-haspopup="true" aria-expanded="false">
    <span class="app-menubar-label" data-i18n="menu_help">Aide</span>
    <div class="app-menubar-dropdown" id="menu-help-dd" role="menu">
      <button type="button" class="app-menubar-dd-item" data-menu-action="contact-dev" role="menuitem"><span data-i18n="menu_contact_dev">Contacter le développeur</span></button>
      <button type="button" class="app-menubar-dd-item" data-menu-action="open-doc" role="menuitem"><span data-i18n="menu_doc">Documentation du projet</span></button>
    </div>
  </div>
</nav>

<!-- Top Tab Bar -->
<div class="top-tab-bar">
  <div class="top-tab-bar-inner">
    <div class="tab-chat-wrap">
      <button type="button" class="top-tab-btn active" id="tab-chat" aria-expanded="false"><span id="model-current-label">Chat</span><span class="chevron">▾</span></button>
      <div class="model-dd-menu" id="model-dd-menu" role="menu"></div>
    </div>
    <button type="button" class="top-tab-btn" id="tab-coworking" data-tab="coworking">Goat Code</button>
  </div>
</div>

<!-- Model dropdown ancien (caché, dummy pour JS) -->
<div class="model-dropdown" id="model-dropdown" hidden>
  <button type="button" class="model-trigger-btn" id="model-trigger-btn" aria-expanded="false"></button>
</div>

<button type="button" class="private-chat-btn" id="private-chat-btn">🔒<span id="pc-label">Chat Privé</span><div class="pc-tooltip"><div class="pc-title" id="pc-title"></div><div class="pc-desc" id="pc-desc"></div></div></button>

<main class="shell" id="shell">
  <section class="brand-stack"><div class="logo-card"><img id="main-logo" src="%%LEGOAT_LIGHT_URI%%" data-light="%%LEGOAT_LIGHT_URI%%" data-dark="%%LEGOAT_DARK_URI%%" data-pixel-light="%%LEGOAT_PIXEL_LIGHT_URI%%" data-pixel-dark="%%LEGOAT_PIXEL_DARK_URI%%" alt="Logo"></div><div class="brand-text" id="brand-text">%%APP_TITLE%%</div><div class="welcome-copy" id="welcome-copy"></div><div class="welcome-desc" id="welcome-desc"></div><div class="brand-actions"><button type="button" class="composer-plus brand-add-button" id="composer-plus" data-tooltip-key="tooltip_plus_btn"><span class="brand-add-icon">＋</span><span class="brand-add-label" data-i18n="sheet_add">Ajouter</span></button><div class="plus-menu brand-plus-menu" id="plus-menu"><button type="button" class="plus-menu-item" id="plus-add-sheet"></button></div></div></section>
  <section class="messages" id="messages" aria-live="polite"></section>
  <section class="composer-wrap">
    <div class="sheets-row" id="sheets-row"></div>
    <div class="attachments-row" id="attachments-row" hidden></div>
    <form class="composer" id="chat-form">
      <!-- Bouton + : ouvre le menu Image / Fichier -->
      <div class="attach-wrap" style="position:relative;align-self:center">
        <button type="button" class="attach-btn" id="attach-btn" aria-haspopup="true" aria-expanded="false" aria-label="Joindre">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>
        </button>
        <div class="attach-menu" id="attach-menu" role="menu">
          <button type="button" class="attach-menu-item" id="attach-image-btn" role="menuitem">
            <span class="attach-menu-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2.5"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 16l-5-5L5 21"/></svg>
            </span>
            <span class="attach-menu-text">
              <span class="attach-menu-title" data-i18n="attach_image">Image</span>
              <span class="attach-menu-hint" data-i18n="attach_image_hint">Joindre une image</span>
            </span>
          </button>
          <button type="button" class="attach-menu-item" id="attach-file-btn" role="menuitem">
            <span class="attach-menu-icon">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>
            </span>
            <span class="attach-menu-text">
              <span class="attach-menu-title" data-i18n="attach_file">Fichier</span>
              <span class="attach-menu-hint" data-i18n="attach_file_hint">Joindre un fichier</span>
            </span>
          </button>
        </div>
        <input type="file" id="attach-image-input" accept="image/*" multiple hidden>
        <input type="file" id="attach-file-input" multiple hidden>
      </div>
      <textarea id="message-input" rows="1"></textarea>
      <button type="button" class="voice-input-button" id="voice-input-btn" aria-label="Voice input">
        <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square" stroke-linejoin="miter"><path d="M12 4a2 2 0 0 1 2 2v5a2 2 0 1 1-4 0V6a2 2 0 0 1 2-2Z"/><path d="M7 10v1a5 5 0 0 0 10 0v-1"/><path d="M12 16v4"/><path d="M9 20h6"/></svg>
      </button>
      <button type="submit" class="send-button" id="send-button" data-tooltip-key="tooltip_send">↑</button>
      <button type="button" class="stop-button" id="stop-button" hidden>■</button>

    </form>
    <div style="display:flex;justify-content:flex-end;width:100%;padding:0 4px;position:relative">
      <div class="char-counter" id="char-counter"><span id="char-counter-text">0 / 10 000</span><div class="char-counter-tip" id="char-counter-tip"></div></div>
    </div>
    <div class="controls-row" id="controls-row">
      <!-- Modes -->
      <div class="mode-panel" id="mode-panel"><button type="button" class="mode-trigger" id="mode-trigger" aria-haspopup="true" aria-expanded="false" data-tooltip-key="tooltip_mode_trigger"><span class="trigger-icon" id="mode-icon">○</span><span id="selected-mode-label"></span><span class="trigger-chevron">⌄</span></button><div class="dropdown-menu" id="mode-menu" role="menu"></div></div>
      <!-- Writing Styles -->
      <div class="style-panel"><button type="button" class="style-trigger" id="style-trigger" aria-haspopup="true" aria-expanded="false" data-tooltip-key="tooltip_style_trigger"><span class="trigger-icon" id="style-icon">✎</span><span id="selected-style-label"></span><span class="trigger-chevron">⌄</span></button><div class="dropdown-menu" id="style-menu" role="menu"></div></div>
      <!-- ── Modèles personnalisés (visible si interrupteur "Autres modèles" actif) ── -->
      <div class="style-panel custom-models-panel" id="custom-models-panel" hidden>
        <button type="button" class="style-trigger" id="custom-models-trigger" aria-haspopup="true" aria-expanded="false" data-tooltip-key="tooltip_models_trigger">
          <span class="trigger-icon" id="custom-models-icon">⚙</span>
          <span id="custom-models-label" data-i18n="models_btn_label">Modèles</span>
          <span class="trigger-chevron">⌄</span>
        </button>
        <div class="dropdown-menu custom-models-menu" id="custom-models-menu" role="menu"></div>
      </div>
      <!-- Gadgets (desactive pour le moment)
      <div class="style-panel"><button type="button" class="style-trigger" id="gadget-trigger" aria-haspopup="true" aria-expanded="false" data-tooltip-key="tooltip_gadget_trigger"><span class="trigger-icon" id="gadget-icon">⚙</span><span id="selected-gadget-label"></span><span class="trigger-chevron">⌄</span></button><div class="dropdown-menu" id="gadget-menu" role="menu"></div></div>
      -->
      <!-- Contraction Of Chat -->
      <div class="contraction-tag" id="contraction-tag" hidden>⚠ Contraction Of Chat<div class="contraction-tip" id="contraction-tip"></div></div>
    </div>
    <div class="mode-announcement" id="mode-announcement"></div>
  </section>
  <div class="status" id="status"></div>
</main>
<!-- Boutons gauche — style Apple quasi-transparent -->
<div class="left-buttons-anchor">
  <button type="button" class="sidebar-toggle-btn" id="sidebar-toggle-btn" aria-label="Ouvrir le panneau latéral" data-tooltip-key="tooltip_sidebar">☰</button>
  <button type="button" class="newchat-button" id="newchat-button" data-tooltip-key="tooltip_new_chat">＋</button>
</div>
<div id="newchat-button-label" hidden></div>
<div class="settings-anchor"><button type="button" class="settings-button" id="settings-button" data-tooltip-key="tooltip_settings">⚙</button><div class="settings-button-label" id="settings-button-label"></div></div>

<!-- ──────────────────────────────────────────────────────────────
     Barre latérale (sidebar)
     ────────────────────────────────────────────────────────────── -->
<div class="sidebar-overlay" id="sidebar-overlay" aria-hidden="true"></div>
<aside class="sidebar-panel" id="sidebar-panel" aria-hidden="true" role="complementary">

  <!-- Topbar : marque + bouton fermer -->
  <div class="sidebar-topbar">
    <div class="sidebar-brand-wrap">
      <span class="sidebar-brand-mark" id="sidebar-brand-mark" aria-hidden="true">
        <img id="sidebar-brand-mark-img" alt="">
      </span>
      <span class="sidebar-brand" id="sidebar-brand">Le Goat</span>
    </div>
    <button type="button" class="sidebar-icon-btn" id="sidebar-close-btn" aria-label="Fermer le panneau">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>
    </button>
  </div>

  <!-- Action principale : nouvelle discussion -->
  <div class="sidebar-section">
    <button type="button" class="sidebar-primary-btn" id="sidebar-new-chat-btn">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 5v14M5 12h14"/></svg>
      <span id="sidebar-new-chat-label">Nouvelle discussion</span>
    </button>
  </div>

  <!-- Recherche -->
  <div class="sidebar-section">
    <div class="sidebar-search-inner">
      <span class="sidebar-search-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4.3-4.3"/></svg>
      </span>
      <input type="search" class="sidebar-search" id="sidebar-search" placeholder="Rechercher une discussion…" data-placeholder-key="sidebar_search_placeholder">
    </div>
  </div>

  <!-- Section "Épinglés" -->
  <div class="sidebar-pinned-wrap">
    <div class="sidebar-section-title" data-i18n="sidebar_pinned">Épinglés</div>
    <div class="sidebar-pinned-empty" id="sidebar-pinned-empty">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2l2.39 4.84 5.34.78-3.86 3.77.91 5.32L12 14.27l-4.78 2.51.91-5.32-3.86-3.77 5.34-.78L12 2z" transform="scale(.85) translate(2.1 1.6)"/></svg>
      <span data-i18n="sidebar_pinned_empty">Glissez pour épingler</span>
    </div>
  </div>

  <!-- Onglets : Fichiers / Historique -->
  <div class="sidebar-tabs">
    <button type="button" class="sidebar-tab active" data-sidebar-tab="files" data-i18n="sidebar_tab_files">Fichiers</button>
    <button type="button" class="sidebar-tab" data-sidebar-tab="history" data-i18n="sidebar_tab_history">Historique</button>
  </div>

  <!-- Contenu : Fichiers -->
  <div class="sidebar-content" data-sidebar-content="files">
    <button type="button" class="sidebar-action-item" id="sidebar-create-file-btn">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/><path d="M12 18v-6M9 15h6"/></svg>
      <span data-i18n="sidebar_create_file">Créer un fichier</span>
    </button>
  </div>

  <!-- Contenu : Historique -->
  <div class="sidebar-content" data-sidebar-content="history" hidden>
    <div class="sidebar-empty" id="sidebar-history-empty" data-i18n="sidebar_history_empty">Aucune discussion pour l'instant.</div>
  </div>

  <!-- Footer : profil + paramètres -->
  <div class="sidebar-footer">
    <button type="button" class="sidebar-profile" id="sidebar-profile-btn" aria-label="Ouvrir le profil">
      <span class="sidebar-profile-avatar" id="sidebar-profile-avatar" aria-hidden="true">G</span>
      <span class="sidebar-profile-name" id="sidebar-profile-name">Le Goat</span>
    </button>
    <button type="button" class="sidebar-settings-icon-btn" id="sidebar-settings-btn" aria-label="Paramètres" data-tooltip-key="tooltip_settings">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.6 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.6a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09c0 .66.39 1.26 1 1.51a1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9c.25.61.85 1 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
    </button>
  </div>
</aside>
<!-- Modale "Créer / Renommer un fichier" -->
<div class="sf-modal-backdrop" id="sf-modal-backdrop" aria-hidden="true">
  <div class="sf-modal" role="dialog" aria-modal="true" aria-labelledby="sf-modal-title">
    <div class="sf-modal-title" id="sf-modal-title">Nouveau fichier</div>
    <input type="text" class="sf-modal-input" id="sf-modal-input" placeholder="Nom du fichier" autocomplete="off" spellcheck="false" maxlength="120">
    <div class="sf-modal-actions">
      <button type="button" class="sf-modal-btn" id="sf-modal-cancel">Annuler</button>
      <button type="button" class="sf-modal-btn primary" id="sf-modal-confirm">Créer</button>
    </div>
  </div>
</div>
<!-- Popover : actions sur un fichier (renommer / supprimer) -->
<div class="sf-popover" id="sf-popover" role="menu" aria-hidden="true">
  <button type="button" class="sf-popover-item" id="sf-popover-rename" role="menuitem">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
    <span id="sf-popover-rename-label">Renommer</span>
  </button>
  <button type="button" class="sf-popover-item danger" id="sf-popover-delete" role="menuitem">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
    <span id="sf-popover-delete-label">Supprimer</span>
  </button>
</div>
<div class="settings-backdrop" id="settings-backdrop" hidden></div>
<section class="settings-modal" id="settings-modal" hidden aria-modal="true" role="dialog">
  <aside class="settings-sidebar">
    <div class="settings-close-row"><strong data-i18n="settings_label">Paramètres</strong><button type="button" class="settings-close" id="settings-close">×</button></div>
    <button type="button" class="settings-tab active" data-settings-tab="general"><span class="settings-tab-icon">⚙</span><span data-i18n="tab_general">Générale</span></button>
    <button type="button" class="settings-tab" data-settings-tab="appearance"><span class="settings-tab-icon">🎨</span><span data-i18n="tab_appearance">Apparence</span></button>
    <button type="button" class="settings-tab" data-settings-tab="personalization"><span class="settings-tab-icon">✦</span><span data-i18n="tab_personalization">Personnalisation</span></button>
    <button type="button" class="settings-tab" data-settings-tab="data_security"><span class="settings-tab-icon">☑</span><span data-i18n="tab_data_security">Données</span></button>
    <button type="button" class="settings-tab" data-settings-tab="optimization"><span class="settings-tab-icon">⚡</span><span data-i18n="tab_optimization">Optimisation</span></button>
    <button type="button" class="settings-tab" data-settings-tab="connectors"><span class="settings-tab-icon">🔌</span><span data-i18n="tab_connectors">Connecteurs</span></button>
    <button type="button" class="settings-tab" data-settings-tab="goat_dev"><span class="settings-tab-icon">🐐</span><span data-i18n="tab_goat_dev">Goat Developer</span></button>
    <button type="button" class="settings-tab" data-settings-tab="aide"><span class="settings-tab-icon">💬</span><span data-i18n="tab_aide">Aide</span></button>
    <button type="button" class="settings-tab settings-tab-profile-footer" data-settings-tab="profile">
      <img class="settings-profile-tab-avatar" id="settings-profile-tab-avatar" alt="Avatar profil">
      <div class="settings-profile-tab-copy">
        <span class="settings-profile-tab-label" data-i18n="tab_profile">Profil</span>
        <span class="settings-profile-tab-name" id="settings-profile-tab-name">Profil local</span>
      </div>
    </button>
  </aside>
  <div class="settings-main">
    <div class="settings-header" id="settings-drag-handle"><div><h2 data-i18n="settings_title">Paramètres</h2><p data-i18n="settings_subtitle"></p></div><div class="settings-hint" data-i18n="settings_hint"></div></div>
    <div class="settings-content" id="settings-content">
      <section class="settings-section active" data-settings-content="general">
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="general_version">Version</div></div><div class="settings-version-value" id="settings-version-value">%%APP_VERSION%%</div></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="update_info">Mises à jour</div></div><button type="button" class="settings-ghost-button" id="update-info-button" data-i18n="update_info"></button></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="general_language">Langue</div></div><div class="settings-choice-group"><button type="button" class="settings-choice" data-language-value="fr" data-i18n="language_fr">Français</button><button type="button" class="settings-choice" data-language-value="en" data-i18n="language_en">Anglais</button><button type="button" class="settings-choice" data-language-value="es" data-i18n="language_es">Espagnol</button></div></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="general_theme">Thème</div><div class="settings-row-subtitle" data-i18n="theme_description"></div></div><div class="settings-choice-group"><button type="button" class="settings-choice" data-theme-value="light" data-i18n="theme_light">Claire</button><button type="button" class="settings-choice" data-theme-value="dark" data-i18n="theme_dark">Sombre</button></div></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="general_text_size">Taille</div></div><div class="settings-choice-group"><button type="button" class="settings-choice" data-textsize-value="default" data-i18n="text_size_default">Par défaut</button><button type="button" class="settings-choice" data-textsize-value="large" data-i18n="text_size_large">Grand</button></div></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="general_app_scale">Taille du logiciel</div><div class="settings-row-subtitle" data-i18n="general_app_scale_hint"></div></div><div class="settings-stepper"><button type="button" class="settings-ghost-button" id="scale-down-button">−</button><span class="settings-stepper-value" id="ui-scale-value">100%</span><button type="button" class="settings-ghost-button" id="scale-up-button">+</button></div></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="general_keyboard_sounds">Son clavier</div></div><div class="settings-choice-group" id="keyboard-sound-toggle"><button type="button" class="settings-choice" data-kb-sound="on" data-i18n="sound_on">Activer</button><button type="button" class="settings-choice" data-kb-sound="off" data-i18n="sound_off">Désactiver</button></div></div><div class="settings-row" id="keyboard-style-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="general_keyboard_sound_style">Style</div></div><div class="settings-choice-group"><button type="button" class="settings-choice" data-kb-style="bulle" data-i18n="sound_style_bulle">Bulle</button><button type="button" class="settings-choice" data-kb-style="aurela" data-i18n="sound_style_aurela">Aurela</button><button type="button" class="settings-choice" data-kb-style="verdrock" data-i18n="sound_style_verdrock">Verdrock</button><button type="button" class="settings-choice" data-kb-style="feryn" data-i18n="sound_style_feryn">Feryn</button></div></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="general_click_sounds">Son boutons</div></div><div class="settings-choice-group" id="click-sound-toggle"><button type="button" class="settings-choice" data-click-sound="on" data-i18n="sound_on">Activer</button><button type="button" class="settings-choice" data-click-sound="off" data-i18n="sound_off">Désactiver</button></div></div><div class="settings-row" id="click-style-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="general_click_sound_style">Style</div></div><div class="settings-choice-group"><button type="button" class="settings-choice" data-click-style="bulle" data-i18n="sound_style_bulle">Bulle</button><button type="button" class="settings-choice" data-click-style="nebrise" data-i18n="sound_style_nebrise">Nebrise</button></div></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="general_ai_reply_sounds">Son IA</div></div><div class="settings-choice-group" id="ai-sound-toggle"><button type="button" class="settings-choice" data-ai-sound="on" data-i18n="sound_on">Activer</button><button type="button" class="settings-choice" data-ai-sound="off" data-i18n="sound_off">Désactiver</button></div></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="font_label">Police IA</div></div><div class="settings-choice-group"><button type="button" class="settings-choice" data-aifont-value="default" data-i18n="font_default">Par défaut</button><button type="button" class="settings-choice" data-aifont-value="arial" data-i18n="font_arial">Arial</button><button type="button" class="settings-choice" data-aifont-value="opendyslexic" data-i18n="font_opendyslexic">Open Dyslexic</button></div></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="font_user_label">Police utilisateur</div></div><div class="settings-choice-group"><button type="button" class="settings-choice" data-userfont-value="default" data-i18n="font_default">Par défaut</button><button type="button" class="settings-choice" data-userfont-value="arial" data-i18n="font_arial">Arial</button><button type="button" class="settings-choice" data-userfont-value="opendyslexic" data-i18n="font_opendyslexic">Open Dyslexic</button></div></div></div>
        <!-- Toggle "Version de prévisualisation" — active/désactive les fonctions expérimentales -->
        <div class="settings-block">
          <div class="settings-row">
            <div class="settings-row-stack">
              <div class="settings-row-title" data-i18n="preview_toggle_label">Accéder à la version de prévisualisation</div>
              <div class="settings-row-subtitle" data-i18n="preview_toggle_hint"></div>
            </div>
            <label class="preview-switch" aria-label="Version de prévisualisation">
              <input type="checkbox" id="preview-toggle-input" checked>
              <span class="preview-switch-track"></span>
            </label>
          </div>
        </div>
        <div class="thanks-text" id="thanks-text" data-i18n="thanks_message">Designed and coded in France</div>
      </section>

      <section class="settings-section" data-settings-content="appearance">
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="appearance_color">Couleur de l'interface</div></div><div class="appearance-swatch-group"><button type="button" class="appearance-swatch" data-accent-value="blue" style="--swatch:#3b82f6" title="Bleu"></button><button type="button" class="appearance-swatch" data-accent-value="red" style="--swatch:#ef4444" title="Rouge"></button><button type="button" class="appearance-swatch" data-accent-value="green" style="--swatch:#22c55e" title="Vert"></button><button type="button" class="appearance-swatch" data-accent-value="yellow" style="--swatch:#eab308" title="Jaune"></button><button type="button" class="appearance-swatch" data-accent-value="pink" style="--swatch:#ec4899" title="Rose"></button><button type="button" class="appearance-swatch" data-accent-value="purple" style="--swatch:#8b5cf6" title="Violet"></button></div></div></div>
        <div class="wallpaper-preview-card">
          <div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="appearance_wallpaper_normal">Fond d'écran du mode normal</div></div><div class="wallpaper-actions"><button type="button" class="settings-ghost-button" id="change-normal-wallpaper" data-i18n="appearance_change">Changer</button><button type="button" class="settings-ghost-button" id="remove-normal-wallpaper" data-i18n="appearance_remove">Retirer</button></div></div>
          <div class="wallpaper-preview-box" id="normal-wallpaper-preview"><span class="label" data-i18n="appearance_preview">Aperçu</span></div>
        </div>
        <div class="wallpaper-preview-card">
          <div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="appearance_wallpaper_coworking">Fond d'écran de Goat Code</div></div><div class="wallpaper-actions"><button type="button" class="settings-ghost-button" id="change-coworking-wallpaper" data-i18n="appearance_change">Changer</button><button type="button" class="settings-ghost-button" id="remove-coworking-wallpaper" data-i18n="appearance_remove">Retirer</button></div></div>
          <div class="wallpaper-preview-box" id="coworking-wallpaper-preview"><span class="label" data-i18n="appearance_preview">Aperçu</span></div>
        </div>
      </section>
      <section class="settings-section" data-settings-content="personalization"><div class="settings-block">
        <div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title">Logo de l'IA</div><div class="settings-row-subtitle">Remplace le logo affiché dans l'interface. PNG ou JPG recommandé.</div></div><div style="display:flex;gap:8px;align-items:center"><img id="ai-logo-preview" alt="Logo aperçu" style="width:40px;height:40px;object-fit:contain;border-radius:8px;border:1px solid var(--line);background:var(--surface-soft)"><button type="button" class="settings-ghost-button" id="ai-logo-change-btn">Changer</button><button type="button" class="settings-ghost-button" id="ai-logo-reset-btn">Réinitialiser</button></div></div>
        <div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title">Nom de l'IA</div><div class="settings-row-subtitle">Par défaut : "Le Goat". Ce nom s'affiche partout dans l'interface.</div></div><div style="display:flex;gap:8px;align-items:center"><input class="settings-input" id="ai-name-input" placeholder="Le Goat" style="width:150px"><button type="button" class="settings-ghost-button" id="ai-name-reset-btn">Réinitialiser</button></div></div>
        <div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="perso_how_address">Comment l'IA s'adresse à vous</div><div class="settings-row-subtitle" data-i18n="perso_how_address_help">Prénom, surnom, ou titre que l'IA utilisera.</div></div><input class="settings-input" id="user-tone" data-placeholder-key="placeholder_tone"></div>
        <div class="settings-row" style="flex-direction:column;align-items:stretch"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="perso_ai_tone">Ton de l'IA</div><div class="settings-row-subtitle" data-i18n="perso_ai_tone_help">Décrivez comment vous voulez que l'IA vous parle.</div></div><textarea class="settings-textarea" id="user-info" data-placeholder-key="personalization_placeholder" style="width:100%;min-height:160px"></textarea></div>
        <!-- ── Interrupteur "Autres modèles" ───────────────────────────────
             Affiche/cache un bouton "Modèles" à côté du sélecteur de style
             d'écriture, qui permet de gérer ses propres modèles. -->
        <div class="settings-row" data-tooltip-key="tooltip_other_models_toggle">
          <div class="settings-row-stack">
            <div class="settings-row-title" data-i18n="perso_other_models">Autres modèles</div>
            <div class="settings-row-subtitle" data-i18n="perso_other_models_help">Active la possibilité d'ajouter et de gérer vos propres modèles.</div>
          </div>
          <label class="profile-switch" aria-label="Autres modèles">
            <input type="checkbox" id="other-models-toggle">
            <span class="profile-switch-track"></span>
          </label>
        </div>
        <input type="hidden" id="user-firstname"><input type="hidden" id="user-lastname">
      </div></section>
      <section class="settings-section" data-settings-content="data_security"><div class="settings-block">
        <div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="data_security_memory">Mémoire</div></div><button type="button" class="settings-ghost-button" id="manage-memory-button" data-i18n="data_security_memory"></button></div>
        <!-- Option masquée temporairement : historique des discussions
        <div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="data_security_history">Historique</div></div><button type="button" class="settings-ghost-button" id="manage-history-button" data-i18n="data_security_history"></button></div>
        -->
        <div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="migrate_data">Migration</div></div><button type="button" class="settings-ghost-button" id="migrate-data-button" data-i18n="migrate_data"></button></div>
      </div></section>
      <section class="settings-section" data-settings-content="optimization">
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="optimization_effects">Effets visuels</div><div class="settings-row-subtitle">Désactive transitions + ombres + blur.</div></div><div class="settings-choice-group"><span class="settings-state" id="effects-state"></span><button type="button" class="settings-ghost-button" id="toggle-effects-button" data-i18n="optimization_effects"></button></div></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="optimization_responses">Réponses</div><div class="settings-row-subtitle">Bloque Creativity / Reflection / Research In Memory.</div></div><div class="settings-choice-group"><span class="settings-state" id="responses-state"></span><button type="button" class="settings-ghost-button" id="toggle-responses-button" data-i18n="optimization_responses"></button></div></div></div>
        <div class="settings-block" data-preview-only="1"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="optimization_calc_target">Ciblage des calculs<span class="beta-badge" data-i18n="aide_beta_label">BÊTA</span></div><div class="settings-row-subtitle" data-i18n="optimization_calc_target_hint"></div></div><div class="calc-target-panel" id="calc-target-panel"><button type="button" class="mode-trigger" id="calc-target-trigger" aria-haspopup="true" aria-expanded="false"><span class="trigger-icon" id="calc-target-icon">⚙</span><span id="calc-target-label"></span><span class="trigger-chevron">⌄</span></button><div class="dropdown-menu" id="calc-target-menu" role="menu"></div></div></div></div>
        <div class="calc-target-notification" id="calc-target-notification" hidden></div>
        <!-- Option masquée temporairement : libération de la mémoire vive de l'IA
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="optimization_ram">Libération de la mémoire vive de l'IA</div><div class="settings-row-subtitle" data-i18n="optimization_ram_hint"></div></div><button type="button" class="settings-ghost-button" id="release-ram-button" data-i18n="optimization_ram"></button></div></div>
        -->
        <div class="settings-block" data-preview-only="1"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="overclock_label">Overclocking IA</div><div class="settings-row-subtitle" data-i18n="overclock_subtitle"></div></div><div class="overclock-toggle" id="overclock-toggle"></div></div></div>
      </section>
      <!-- ── Section Connecteurs ── -->
      <section class="settings-section" data-settings-content="connectors">
        <div class="settings-block">
          <div class="settings-row">
            <div class="settings-row-stack">
              <div class="settings-row-title" data-i18n="connectors_title">Connecteurs</div>
              <div class="settings-row-subtitle" data-i18n="connectors_subtitle">Liez Le Goat à vos services et outils externes.</div>
            </div>
            <button type="button" class="settings-ghost-button" id="connectors-add-btn" data-i18n="connectors_add">Ajouter un connecteur</button>
          </div>
        </div>
      </section>
      <!-- ── Section Aide ── -->
      <section class="settings-section" data-settings-content="aide"><div class="settings-block">
        <div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="aide_contact_title">Contacter le développeur</div><div class="settings-row-subtitle" data-i18n="aide_contact_desc">Une question, un bug, une idée ? Écrivez-nous.</div></div><button type="button" class="settings-ghost-button" id="aide-contact-btn" data-i18n="aide_contact_btn">Contacter</button></div>
      </div></section>

      <!-- ── Modal contact développeur ── -->
      <div class="aide-contact-backdrop" id="aide-contact-backdrop" role="dialog" aria-modal="true">
        <div class="aide-contact-modal">
          <h3 data-i18n="aide_contact_modal_title">Nous contacter</h3>
          <p data-i18n="aide_contact_modal_desc">Choisissez votre moyen de contact préféré.</p>
          <div class="aide-contact-cards">
            <!-- Mail — ouvre Gmail ou l'application Mail Windows -->
            <a class="aide-contact-card" id="aide-mail-card" href="mailto:contact@legoat.fr" title="Envoyer un e-mail">
              <svg viewBox="0 0 44 44" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="44" height="44" rx="12" fill="#EA4335"/>
                <path d="M8 14h28v18H8V14z" fill="white" opacity=".15"/>
                <path d="M8 14l14 11L36 14" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                <rect x="8" y="14" width="28" height="18" rx="2" stroke="white" stroke-width="2" fill="none"/>
              </svg>
              <span class="aide-contact-card-label">Mail</span>
              <span class="aide-contact-card-sub">contact@legoat.fr</span>
            </a>
            <!-- Instagram — désactivé pour l'instant -->
            <div class="aide-contact-card disabled" title="Instagram — bientôt disponible">
              <svg viewBox="0 0 44 44" fill="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                  <linearGradient id="ig-grad" x1="0" y1="44" x2="44" y2="0" gradientUnits="userSpaceOnUse">
                    <stop offset="0%" stop-color="#f09433"/>
                    <stop offset="25%" stop-color="#e6683c"/>
                    <stop offset="50%" stop-color="#dc2743"/>
                    <stop offset="75%" stop-color="#cc2366"/>
                    <stop offset="100%" stop-color="#bc1888"/>
                  </linearGradient>
                </defs>
                <rect width="44" height="44" rx="12" fill="url(#ig-grad)"/>
                <rect x="11" y="11" width="22" height="22" rx="6" stroke="white" stroke-width="2.2" fill="none"/>
                <circle cx="22" cy="22" r="5.5" stroke="white" stroke-width="2.2" fill="none"/>
                <circle cx="29" cy="15" r="1.5" fill="white"/>
              </svg>
              <span class="aide-contact-card-label">Instagram</span>
              <span class="aide-contact-card-sub">Bientôt disponible</span>
            </div>
          </div>
          <button type="button" class="aide-contact-close" id="aide-contact-close" data-i18n="aide_close">Fermer</button>
        </div>
      </div>

      <!-- ── Modale Connecteurs (liste vide + bouton custom) ── -->
      <div class="connectors-modal-backdrop" id="connectors-modal-backdrop" role="dialog" aria-modal="true">
        <div class="connectors-modal">
          <div class="connectors-modal-header">
            <h3 data-i18n="connectors_modal_title">Connecteurs disponibles</h3>
            <button type="button" class="connectors-modal-close" id="connectors-modal-close">×</button>
          </div>
          <div class="connectors-empty-card">
            <strong data-i18n="connectors_empty">Aucun connecteur</strong>
            <span data-i18n="connectors_empty_hint">Aucun connecteur n'est disponible pour le moment.</span>
          </div>
          <div class="connectors-modal-footer">
            <button type="button" class="settings-ghost-button" id="connectors-add-custom-btn" data-i18n="connectors_add_custom">Ajouter un connecteur personnalisé</button>
          </div>
        </div>
      </div>

      <!-- ── Modale Connecteur personnalisé (placeholder) ── -->
      <div class="connectors-modal-backdrop" id="connectors-custom-backdrop" role="dialog" aria-modal="true">
        <div class="connectors-modal">
          <div class="connectors-modal-header">
            <h3 data-i18n="connectors_custom_modal_title">Connecteur personnalisé</h3>
            <button type="button" class="connectors-modal-close" id="connectors-custom-close">×</button>
          </div>
          <p style="margin:0;color:var(--text-secondary);font-size:.9rem;line-height:1.5" data-i18n="connectors_custom_modal_desc">Cette fonction est en cours de développement.</p>
          <div class="connectors-modal-footer">
            <button type="button" class="settings-ghost-button" id="connectors-custom-ok" data-i18n="aide_close">Fermer</button>
          </div>
        </div>
      </div>

      <!-- ── Modale d'avertissement (activation prévisualisation) ── -->
      <div class="preview-warning-backdrop" id="preview-warning-backdrop" role="dialog" aria-modal="true">
        <div class="preview-warning-modal">
          <h3 data-i18n="preview_warning_title">Activer les fonctions de prévisualisation</h3>
          <p data-i18n="preview_warning_text">Plusieurs fonctions seront affichées, mais elles risquent d'être inutilisables ou en cours de test. Souhaitez-vous continuer ?</p>
          <div class="preview-warning-actions">
            <button type="button" class="settings-ghost-button" id="preview-warning-cancel" data-i18n="preview_warning_cancel">Annuler</button>
            <button type="button" class="settings-ghost-button primary" id="preview-warning-confirm" data-i18n="preview_warning_confirm">Activer</button>
          </div>
        </div>
      </div>

      <!-- Goat Developer -->
      <section class="settings-section" data-settings-content="goat_dev"><div class="settings-block">
        <div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="goat_dev_news">Nouveautés</div><div class="settings-row-subtitle" data-i18n="goat_dev_news_desc"></div></div><button type="button" class="settings-ghost-button" id="goat-dev-news-btn" data-i18n="goat_dev_news"></button></div>
        <div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="goat_dev_about">À propos</div><div class="settings-row-subtitle" data-i18n="goat_dev_about_desc"></div></div><button type="button" class="settings-ghost-button" id="goat-dev-about-btn" data-i18n="goat_dev_about"></button></div>
      </div></section>
      <section class="settings-section" data-settings-content="profile">
        <div class="profile-shell">
          <div class="profile-stack">
            <div class="profile-card">
              <div class="profile-banner" id="profile-banner-preview"></div>
              <div class="profile-card-body">
                <div class="profile-avatar-wrap"><img class="profile-avatar" id="profile-avatar-preview" alt="Profile avatar"></div>
                <div class="profile-headline">
                  <div class="profile-name-block">
                    <h3 class="profile-name" id="profile-name-preview"></h3>
                    <div class="profile-subline" id="profile-share-hint" data-i18n="profile_share_hint"></div>
                  </div>
                  <button type="button" class="settings-ghost-button" id="profile-edit-toggle" data-i18n="profile_edit">Modifier</button>
                </div>
                <p class="profile-description" id="profile-description-preview"></p>
                <div class="profile-metrics">
                  <div class="profile-metric"><span data-i18n="profile_chats_sent">Chats envoyés à l'IA</span><strong id="profile-chat-count">0</strong></div>
                  <!-- Option masquée temporairement : Goat Score
                  <div class="profile-metric"><span data-i18n="profile_goat_score">Goat Score</span><strong id="profile-goat-score">0</strong></div>
                  -->
                </div>
                <!-- Option masquée temporairement : réseaux sociaux
                <div>
                  <div class="profile-section-title" data-i18n="profile_social_links">Réseaux sociaux</div>
                  <div class="profile-socials" id="profile-socials-preview"></div>
                </div>
                -->
                <div class="profile-share-actions">
                  <!-- Option masquée temporairement : partage du profil professionnel
                  <button type="button" class="settings-ghost-button" id="profile-share-pro-btn" data-i18n="profile_share_pro">Envoyer le profil professionnel</button>
                  -->
                  <button type="button" class="settings-ghost-button primary" id="profile-share-full-btn" data-i18n="profile_share_full">Envoyer le profil complet</button>
                </div>
              </div>
            </div>
            <div class="profile-editor" id="profile-editor" hidden>
              <div class="profile-editor-header">
                <div class="profile-section-title">Profile Builder</div>
                <div class="profile-helper" data-i18n="profile_auto_save">Sauvegarde automatique locale.</div>
              </div>
              <div class="profile-inline-toggle">
                <div class="profile-inline-toggle-text">
                  <strong>Afficher ma photo à côté de mes messages</strong>
                  <span>Activé, vos messages s'affichent avec votre photo de profil. Par défaut : désactivé.</span>
                </div>
                <label class="profile-switch" aria-label="Afficher la photo dans le chat">
                  <input type="checkbox" id="profile-avatar-messages-toggle">
                  <span class="profile-switch-track"></span>
                </label>
              </div>
              <div class="profile-upload-grid">
                <div class="profile-upload-card">
                  <div class="profile-upload-title" data-i18n="profile_avatar">Photo de profil</div>
                  <div class="profile-upload-preview" id="profile-avatar-upload-preview"></div>
                  <div class="profile-upload-actions">
                    <button type="button" class="settings-ghost-button" id="profile-avatar-upload-btn" data-i18n="profile_choose_avatar">Choisir une image</button>
                    <button type="button" class="settings-ghost-button" id="profile-avatar-remove-btn" data-i18n="profile_remove_avatar">Retirer</button>
                  </div>
                </div>
                <div class="profile-upload-card">
                  <div class="profile-upload-title" data-i18n="profile_banner">Bannière</div>
                  <div class="profile-upload-preview" id="profile-banner-upload-preview"></div>
                  <div class="profile-upload-actions">
                    <button type="button" class="settings-ghost-button" id="profile-banner-upload-btn" data-i18n="profile_choose_banner">Choisir une bannière</button>
                    <button type="button" class="settings-ghost-button" id="profile-banner-remove-btn" data-i18n="profile_remove_banner">Retirer</button>
                  </div>
                </div>
              </div>
              <div class="profile-security-note">Les images passent par un filtre local de sécurité avant d'être acceptées. Ce filtre est volontairement conservateur.</div>
              <div class="profile-editor-grid">
                <div><div class="settings-row-title" data-i18n="profile_firstname">Prénom</div><input class="settings-input" id="profile-firstname-input" placeholder="Prénom"></div>
                <div><div class="settings-row-title" data-i18n="profile_lastname">Nom</div><input class="settings-input" id="profile-lastname-input" placeholder="Nom"></div>
                <div class="profile-span-2"><div class="settings-row-title" data-i18n="profile_bio">Bio</div><div class="settings-row-subtitle" data-i18n="profile_bio_help" style="margin-bottom:6px">Votre bio aide l'IA à mieux vous comprendre.</div><textarea class="settings-textarea" id="profile-bio-input" placeholder="Bio" maxlength="1000"></textarea><div class="char-counter" id="profile-bio-counter"><span id="profile-bio-count">0</span>/1000</div></div>
                <!-- Option masquée temporairement : réseaux sociaux en édition
                <div><div class="settings-row-title" data-i18n="profile_instagram">Instagram</div><input class="settings-input" id="profile-instagram-input" placeholder="https://instagram.com/... ou @pseudo"></div>
                <div><div class="settings-row-title" data-i18n="profile_tiktok">TikTok</div><input class="settings-input" id="profile-tiktok-input" placeholder="https://tiktok.com/... ou @pseudo"></div>
                <div><div class="settings-row-title" data-i18n="profile_youtube">YouTube</div><input class="settings-input" id="profile-youtube-input" placeholder="https://youtube.com/... ou @chaîne"></div>
                <div><div class="settings-row-title" data-i18n="profile_github">GitHub</div><input class="settings-input" id="profile-github-input" placeholder="https://github.com/... ou pseudo"></div>
                <div class="profile-span-2"><div class="settings-row-title" data-i18n="profile_bluesky">BleuSky</div><input class="settings-input" id="profile-bluesky-input" placeholder="https://bsky.app/... ou handle"></div>
                -->
              </div>
              <input class="profile-hidden-input" type="file" id="profile-avatar-file" accept="image/*">
              <input class="profile-hidden-input" type="file" id="profile-banner-file" accept="image/*">
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</section>
<div class="migrate-backdrop" id="migrate-backdrop"><div class="migrate-modal"><h3><span id="migrate-title"></span><button type="button" id="migrate-close-x">×</button></h3><div class="migrate-step" id="migrate-step1"></div><div class="migrate-prompt-box" id="migrate-prompt-box"></div><button type="button" class="migrate-copy-btn" id="migrate-copy-btn"></button><div class="migrate-step" id="migrate-step2" style="margin-top:8px"></div><textarea class="migrate-textarea" id="migrate-textarea"></textarea><div class="migrate-actions"><button type="button" class="migrate-btn-cancel" id="migrate-cancel-btn"></button><button type="button" class="migrate-btn-add" id="migrate-add-btn" disabled></button></div></div></div>
<div class="sheet-modal-backdrop" id="sheet-modal-backdrop"><div class="sheet-modal"><div class="sheet-modal-header"><h3 id="sheet-modal-title"></h3><span class="sheet-char-counter" id="sheet-char-counter">0 / 14 000</span></div><textarea id="sheet-textarea" placeholder=""></textarea><div class="sheet-modal-actions"><button type="button" class="sheet-btn-cancel" id="sheet-cancel"></button><button type="button" class="sheet-btn-add" id="sheet-add-btn"></button></div></div></div>
<!-- ── Modale "NAME Models" : ajout / renommage d'un modèle personnalisé ──
     Réutilisée pour les deux opérations (le titre est ajusté dynamiquement). -->
<div class="sheet-modal-backdrop" id="custom-model-backdrop" role="dialog" aria-modal="true">
  <div class="sheet-modal" style="max-width:480px;min-height:0">
    <div class="sheet-modal-header">
      <h3 id="custom-model-modal-title" data-i18n="models_modal_title">NAME Models</h3>
    </div>
    <input type="text" class="settings-input" id="custom-model-name-input" maxlength="64" autocomplete="off" data-placeholder-key="models_modal_placeholder">
    <div class="custom-model-error" id="custom-model-error" hidden></div>
    <div class="sheet-modal-actions">
      <button type="button" class="sheet-btn-cancel" id="custom-model-cancel-btn" data-i18n="models_modal_cancel">Annuler</button>
      <button type="button" class="sheet-btn-add" id="custom-model-enter-btn" data-i18n="models_modal_enter">Entrer</button>
    </div>
  </div>
</div>
<div class="profile-crop-backdrop" id="profile-crop-backdrop">
  <div class="profile-crop-modal">
    <div class="profile-crop-header"><strong id="profile-crop-title">Recadrer l'image</strong><button type="button" id="profile-crop-close">×</button></div>
    <div class="profile-crop-body">
      <div class="profile-crop-canvas-wrap"><canvas id="profile-crop-canvas"></canvas></div>
      <div class="profile-crop-controls">
        <span>Zoom</span>
        <input type="range" id="profile-crop-zoom" min="100" max="260" step="1" value="100">
      </div>
    </div>
    <div class="profile-crop-actions">
      <button type="button" class="settings-ghost-button" id="profile-crop-cancel">Annuler</button>
      <button type="button" class="settings-ghost-button primary" id="profile-crop-apply">Appliquer</button>
    </div>
  </div>
</div>
<div class="profile-picker-backdrop" id="profile-picker-backdrop">
  <div class="profile-picker-modal">
    <div class="profile-picker-header"><strong id="profile-picker-title">Choisir une image</strong><button type="button" id="profile-picker-close">×</button></div>
    <div class="profile-picker-body">
      <div class="profile-picker-section-title" id="profile-picker-section-title">Goat</div>
      <div class="profile-picker-grid" id="profile-picker-grid"></div>
    </div>
  </div>
</div>
<!-- Badge Goatistique retiré -->
<div class="overclock-backdrop" id="overclock-backdrop"><div class="overclock-modal"><h3>⚠ Overclocking IA</h3><div class="oc-warning-text" id="oc-warning-text"></div><div class="oc-actions"><button type="button" class="oc-btn-cancel" id="oc-cancel-btn"></button><button type="button" class="oc-btn-confirm" id="oc-confirm-btn"></button></div></div></div>
<div class="tooltip" id="tooltip" hidden></div>
<div class="profile-avatar-hover-card" id="profile-avatar-hover-card" hidden>
  <div class="profile-avatar-hover-banner" id="profile-avatar-hover-banner"></div>
  <div class="profile-avatar-hover-body">
    <div class="profile-avatar-hover-head">
      <img id="profile-avatar-hover-image" alt="Aperçu profil">
      <div class="profile-avatar-hover-copy">
        <strong id="profile-avatar-hover-name"></strong>
        <span id="profile-avatar-hover-bio"></span>
      </div>
    </div>
  </div>
</div>

<div class="wallpaper-backdrop" id="wallpaper-backdrop">
  <div class="wallpaper-modal" role="dialog" aria-modal="true">
    <div class="wallpaper-modal-header"><strong id="wallpaper-modal-title">Fond d'écran</strong><button type="button" id="wallpaper-close-btn">×</button></div>
    <div class="wallpaper-modal-body">
      <div class="wallpaper-modal-target" id="wallpaper-modal-target"></div>
      <div class="wallpaper-preview-box" id="wallpaper-modal-preview"><span class="label" data-i18n="appearance_preview">Aperçu</span></div>
      <div class="wallpaper-actions"><button type="button" class="settings-ghost-button" id="wallpaper-import-image-btn" data-i18n="appearance_import_image">Importer une image</button><button type="button" class="settings-ghost-button" id="wallpaper-import-video-btn" data-i18n="appearance_import_video">Importer une vidéo</button><button type="button" class="settings-ghost-button" id="wallpaper-remove-btn" data-i18n="appearance_remove">Retirer</button></div>
      <input type="file" id="wallpaper-file-input" class="profile-hidden-input" accept="image/*">
      <input type="file" id="wallpaper-video-file-input" class="profile-hidden-input" accept="video/*">
      <div class="settings-row" style="padding-top:0"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="appearance_video_volume">Volume de la vidéo</div><div class="settings-row-subtitle" data-i18n="appearance_video_help">Vidéo en boucle pour l’arrière-plan.</div></div><div class="settings-stepper"><input type="range" id="wallpaper-volume-input" min="0" max="100" step="1" value="35" style="width:180px"><span class="settings-stepper-value" id="wallpaper-volume-value">35%</span></div></div>
      <!-- Option masquée temporairement : FPS et qualité vidéo
      <div class="settings-row" style="padding-top:0"><div class="settings-row-stack"><div class="settings-row-title">FPS</div><div class="settings-row-subtitle">Images par seconde de la vidéo.</div></div><div class="settings-choice-group"><button type="button" class="settings-choice active" data-video-fps="30">30 fps</button><button type="button" class="settings-choice" data-video-fps="60">60 fps</button></div></div>
      <div class="settings-row" style="padding-top:0"><div class="settings-row-stack"><div class="settings-row-title">Qualité</div><div class="settings-row-subtitle">Résolution de rendu vidéo.</div></div><div class="settings-choice-group"><button type="button" class="settings-choice active" data-video-quality="1080p">1080p</button><button type="button" class="settings-choice" data-video-quality="4k">4K</button></div></div>
      -->
    </div>
  </div>
</div>

<!-- Éléments dummy cachés pour éléments désactivés (évite crash JS) -->
<div hidden>
  <button id="toggle-uiopt-button"></button><span id="uiopt-state"></span>
  <div id="calc-target-panel"></div><button id="calc-target-trigger"></button><span id="calc-target-label"></span><span id="calc-target-icon"></span><div id="calc-target-menu"></div><div id="calc-target-notification"></div>
  <div id="profile-socials-preview"></div>
  <input id="profile-instagram-input"><input id="profile-tiktok-input"><input id="profile-youtube-input"><input id="profile-github-input"><input id="profile-bluesky-input">
</div>
<script>
// ─────────────────────────────────────────────────────────────────
// Le Goat — Logique UI (vanilla JS, aucune dépendance externe)
//
// Architecture JS :
//   S            → état global persisté en localStorage
//   t(key)       → fonction de traduction (accède à T[S.lang][key])
//   applyXxx()   → applique un paramètre UI et le sauvegarde
//   renderXxx()  → re-génère un composant DOM
//   openXxx()    → ouvre une modale / dropdown
//   updateXxx()  → met à jour l'affichage sans recréer le DOM
//
// Pour ajouter un mode côté JS :
//   Les modes sont injectés via %%MODES_JSON%% — aucune modification JS
//   n'est nécessaire. Voir AppConfig.MODE_OPTIONS (Python).
//
// Pour ajouter un paramètre persisté :
//   1. Ajoutez une clé dans l'objet S avec sa valeur par défaut.
//   2. Créez une fonction applyMonParam(v, snd) qui appelle apply().
//   3. Liez l'événement UI et ajoutez l'init dans la section "Init".
// ─────────────────────────────────────────────────────────────────
!function(){"use strict";
const $=i=>document.getElementById(i),$$=s=>Array.from(document.querySelectorAll(s));
const T=%%TRANSLATIONS_JSON%%,WP=%%WELCOME_JSON%%,ST=%%STATUS_JSON%%,MO=%%MODES_JSON%%,DM=%%DISABLED_MODES_JSON%%,titleByLang=%%TITLE_BY_LANG_JSON%%,models=%%MODELS_JSON%%,wStyles=%%WSTYLES_JSON%%,gadgets=%%GADGETS_JSON%%,SP=%%STORAGE_PREFIX_JSON%%,appVersion=%%VERSION_JSON%%,sheetLimits=%%SHEET_LIMITS_JSON%%,migrationPrompt=%%MIGRATION_PROMPT_JSON%%,localProfilePresets=%%PROFILE_PRESETS_JSON%%;
const defs={lang:%%DEFAULT_LANG_JSON%%,theme:%%DEFAULT_THEME_JSON%%,effects:%%DEFAULT_EFFECTS_JSON%%,textSize:%%DEFAULT_TEXTSIZE_JSON%%,uiScale:100,accent:'blue',wallpaperNormalType:'none',wallpaperNormalSrc:'',wallpaperNormalVolume:35,wallpaperCoworkingType:'none',wallpaperCoworkingSrc:'',wallpaperCoworkingVolume:35,optResp:%%DEFAULT_OPTRESP_JSON%%,uiOpt:%%DEFAULT_UIOPT_JSON%%,kbSound:%%DEFAULT_KB_SOUND_JSON%%,kbStyle:%%DEFAULT_KB_STYLE_JSON%%,clickSound:%%DEFAULT_CLICK_SOUND_JSON%%,clickStyle:%%DEFAULT_CLICK_STYLE_JSON%%,aiSound:%%DEFAULT_AI_SOUND_JSON%%,mode:%%DEFAULT_MODE_JSON%%,model:%%DEFAULT_MODEL_JSON%%,wstyle:%%DEFAULT_WSTYLE_JSON%%,gadget:%%DEFAULT_GADGET_JSON%%,calcTarget:%%DEFAULT_CALC_TARGET_JSON%%,aifont:'default',userfont:'default',overclock:'off',videoFps:'30',videoQuality:'1080p',otherModelsOn:%%DEFAULT_OTHER_MODELS_JSON%%};
const CUSTOM_MODEL_SENTINEL=%%CUSTOM_MODEL_SENTINEL_JSON%%;
const ls=(k,v)=>{try{if(v!==undefined){localStorage.setItem(SP+'-'+k,v);return v}return localStorage.getItem(SP+'-'+k)}catch(err){console.warn('Local storage unavailable for',k,err);return v!==undefined?v:null}};
const shell=$('shell'),msgBox=$('messages'),form=$('chat-form'),ta=$('message-input'),sendBtn=$('send-button'),statusEl=$('status'),welcomeEl=$('welcome-copy'),welcomeDesc=$('welcome-desc'),brandText=$('brand-text');
const controlsRow=$('controls-row'),modePanel=$('mode-panel');
const modeTrigger=$('mode-trigger'),modeMenu=$('mode-menu'),modeLbl=$('selected-mode-label'),modeIcn=$('mode-icon'),modeAnn=$('mode-announcement');
const styleTrigger=$('style-trigger'),styleMenu=$('style-menu'),styleLbl=$('selected-style-label'),styleIcn=$('style-icon');
/* Gadgets desactive pour le moment
const gadgetTrigger=$('gadget-trigger'),gadgetMenu=$('gadget-menu'),gadgetLbl=$('selected-gadget-label'),gadgetIcn=$('gadget-icon');
*/
const modelTriggerBtn=$('model-trigger-btn'),modelDDMenu=$('model-dd-menu'),modelCurrentLabel=$('model-current-label');
// ── Modèles personnalisés (Settings → Personnalisation → Autres modèles) ──
const otherModelsToggle=$('other-models-toggle');
const customModelsPanel=$('custom-models-panel'),customModelsTrigger=$('custom-models-trigger'),customModelsMenu=$('custom-models-menu'),customModelsLabel=$('custom-models-label');
const customModelBackdrop=$('custom-model-backdrop'),customModelInput=$('custom-model-name-input'),customModelEnterBtn=$('custom-model-enter-btn'),customModelCancelBtn=$('custom-model-cancel-btn'),customModelTitleEl=$('custom-model-modal-title'),customModelErrorEl=$('custom-model-error');
const tabChat=$('tab-chat'),tabCoworking=$('tab-coworking');
const privateChatBtn=$('private-chat-btn');
const composerPlus=$('composer-plus'),plusMenu=$('plus-menu'),plusAddSheet=$('plus-add-sheet'),sheetsRow=$('sheets-row');
const sheetBackdrop=$('sheet-modal-backdrop'),sheetTA=$('sheet-textarea'),sheetAddBtn=$('sheet-add-btn'),sheetCancelBtn=$('sheet-cancel'),sheetTitle=$('sheet-modal-title');
const sheetCharCounter=$('sheet-char-counter');
const migrateBackdrop=$('migrate-backdrop'),migrateTA=$('migrate-textarea'),migrateAddBtn=$('migrate-add-btn'),migrateCancelBtn=$('migrate-cancel-btn'),migrateTitle=$('migrate-title'),migratePromptBox=$('migrate-prompt-box'),migrateStep1=$('migrate-step1'),migrateStep2=$('migrate-step2'),migrateCloseX=$('migrate-close-x');
const modal=$('settings-modal'),backdrop=$('settings-backdrop'),dragH=$('settings-drag-handle'),tooltipEl=$('tooltip');
const charCounterEl=$('char-counter'),charCounterText=$('char-counter-text'),charCounterTip=$('char-counter-tip');
const stopBtn=$('stop-button');
const voiceInputBtn=$('voice-input-btn');
const contractionTag=$('contraction-tag'),contractionTip=$('contraction-tip');
const overclockToggle=$('overclock-toggle'),ocBackdrop=$('overclock-backdrop'),ocWarningText=$('oc-warning-text'),ocConfirmBtn=$('oc-confirm-btn'),ocCancelBtn=$('oc-cancel-btn');
const uiScaleValue=$('ui-scale-value'),scaleDownButton=$('scale-down-button'),scaleUpButton=$('scale-up-button');
const wallpaperLayer=$('wallpaper-layer'),wallpaperImage=$('wallpaper-image'),wallpaperVideo=$('wallpaper-video'),normalWallpaperPreview=$('normal-wallpaper-preview'),coworkingWallpaperPreview=$('coworking-wallpaper-preview');
const wallpaperBackdrop=$('wallpaper-backdrop'),wallpaperModalTitle=$('wallpaper-modal-title'),wallpaperModalTarget=$('wallpaper-modal-target'),wallpaperModalPreview=$('wallpaper-modal-preview'),wallpaperImportImageBtn=$('wallpaper-import-image-btn'),wallpaperImportVideoBtn=$('wallpaper-import-video-btn'),wallpaperRemoveBtn=$('wallpaper-remove-btn'),wallpaperFileInput=$('wallpaper-file-input'),wallpaperVideoFileInput=$('wallpaper-video-file-input'),wallpaperVolumeInput=$('wallpaper-volume-input'),wallpaperVolumeValue=$('wallpaper-volume-value'),wallpaperCloseBtn=$('wallpaper-close-btn');
const calcTargetTrigger=$('calc-target-trigger'),calcTargetMenu=$('calc-target-menu'),calcTargetLabel=$('calc-target-label'),calcTargetIcon=$('calc-target-icon'),calcTargetNotification=$('calc-target-notification');
const profileEditToggle=$('profile-edit-toggle'),profileEditor=$('profile-editor'),profileNamePreview=$('profile-name-preview'),profileDescriptionPreview=$('profile-description-preview'),profileChatCount=$('profile-chat-count'),profileGoatScore=$('profile-goat-score'),profileSocialsPreview=$('profile-socials-preview'),profileAvatarPreview=$('profile-avatar-preview'),profileBannerPreview=$('profile-banner-preview');
const profileAvatarUploadPreview=$('profile-avatar-upload-preview'),profileBannerUploadPreview=$('profile-banner-upload-preview');
const profileFirstnameInput=$('profile-firstname-input'),profileLastnameInput=$('profile-lastname-input'),profileBioInput=$('profile-bio-input'),profileInstagramInput=$('profile-instagram-input'),profileTikTokInput=$('profile-tiktok-input'),profileYouTubeInput=$('profile-youtube-input'),profileGitHubInput=$('profile-github-input'),profileBlueskyInput=$('profile-bluesky-input');
const profileAvatarUploadBtn=$('profile-avatar-upload-btn'),profileBannerUploadBtn=$('profile-banner-upload-btn'),profileAvatarRemoveBtn=$('profile-avatar-remove-btn'),profileBannerRemoveBtn=$('profile-banner-remove-btn'),profileAvatarFile=$('profile-avatar-file'),profileBannerFile=$('profile-banner-file');
const profileShareProBtn=$('profile-share-pro-btn'),profileShareFullBtn=$('profile-share-full-btn');
const profileAvatarMessagesToggle=$('profile-avatar-messages-toggle'),settingsProfileTabAvatar=$('settings-profile-tab-avatar'),settingsProfileTabName=$('settings-profile-tab-name');
const cropBackdrop=$('profile-crop-backdrop'),cropCanvas=$('profile-crop-canvas'),cropZoom=$('profile-crop-zoom'),cropTitle=$('profile-crop-title'),cropApplyBtn=$('profile-crop-apply'),cropCancelBtn=$('profile-crop-cancel'),cropCloseBtn=$('profile-crop-close');
const profileAvatarHoverCard=$('profile-avatar-hover-card'),profileAvatarHoverBanner=$('profile-avatar-hover-banner'),profileAvatarHoverImage=$('profile-avatar-hover-image'),profileAvatarHoverName=$('profile-avatar-hover-name'),profileAvatarHoverBio=$('profile-avatar-hover-bio');
const profilePickerBackdrop=$('profile-picker-backdrop'),profilePickerTitle=$('profile-picker-title'),profilePickerSectionTitle=$('profile-picker-section-title'),profilePickerGrid=$('profile-picker-grid'),profilePickerCloseBtn=$('profile-picker-close');
// ── État global — tout l'état UI persisté en localStorage ────────
// Chaque clé correspond à un réglage sauvegardé entre les sessions.
let S={lang:ls('lang')||defs.lang,theme:ls('theme')||defs.theme,effects:ls('effects')||defs.effects,textSize:ls('textsize')||defs.textSize,uiScale:parseInt(ls('ui-scale')||String(defs.uiScale),10)||defs.uiScale,accent:ls('accent')||defs.accent,wallpaperNormalType:ls('wallpaper-normal-type')||defs.wallpaperNormalType,wallpaperNormalSrc:ls('wallpaper-normal-src')||defs.wallpaperNormalSrc,wallpaperNormalVolume:parseInt(ls('wallpaper-normal-volume')||String(defs.wallpaperNormalVolume),10)||defs.wallpaperNormalVolume,wallpaperCoworkingType:ls('wallpaper-coworking-type')||defs.wallpaperCoworkingType,wallpaperCoworkingSrc:ls('wallpaper-coworking-src')||defs.wallpaperCoworkingSrc,wallpaperCoworkingVolume:parseInt(ls('wallpaper-coworking-volume')||String(defs.wallpaperCoworkingVolume),10)||defs.wallpaperCoworkingVolume,optResp:ls('optresp')||defs.optResp,uiOpt:ls('uiopt')||defs.uiOpt,kbSound:ls('kb-sound')||defs.kbSound,kbStyle:ls('kb-style')||defs.kbStyle,clickSound:ls('click-sound')||defs.clickSound,clickStyle:ls('click-style')||defs.clickStyle,aiSound:ls('ai-sound')||defs.aiSound,mode:ls('mode')||defs.mode,model:ls('model')||defs.model,wstyle:ls('wstyle')||defs.wstyle,gadget:ls('gadget')||defs.gadget,calcTarget:ls('calc-target')||defs.calcTarget,privateChat:false,aifont:ls('aifont')||defs.aifont,userfont:ls('userfont')||defs.userfont,overclock:ls('overclock')||defs.overclock,videoFps:ls('video-fps')||defs.videoFps,videoQuality:ls('video-quality')||defs.videoQuality,aiName:ls('ai-name')||'',aiLogo:ls('ai-logo')||'',otherModelsOn:ls('other-models-on')||defs.otherModelsOn,activeCustomModel:ls('active-custom-model')||'',customModels:(function(){try{const raw=ls('custom-models');return raw?JSON.parse(raw):[]}catch(e){return[]}})()};
// ── Variables runtime (non persistées) ───────────────────────────
let messages=%%MESSAGES_JSON%%,messagesMeta=%%MESSAGES_META_JSON%%,settingsOpen=false,dragging=false,dragSX=0,dragSY=0,mSL=0,mST=0,audioCtx=null,ttTimer=null,avatarHoverTimer=null,profilePickerMode='avatar';
// Stocke quels panneaux « Spécificité » sont ouverts (clé = index du message
// dans la liste `messages`). Permet de conserver l'état d'ouverture entre deux
// appels à renderMessages() (par ex. après un Relancer ou une nouvelle requête).
let openSpecificityPanels=new Set();
let cropState=null;
let wallpaperTarget='normal';
let sheets=[];          // Feuilles d'écriture attachées à la requête courante
let isGenerating=false; // Vrai pendant qu'une réponse IA est en cours
let abortController=null; // Contrôleur pour interrompre la génération
let activeTab='chat';   // Onglet actif : "chat" | "coworking"
// ── Contenu de l'onglet Goat Code (localisé) ─────────────────────
// Pour modifier les messages d'accueil ou le placeholder de Goat Code,
// éditez les valeurs "messages", "placeholder" et "status" ci-dessous.
const coworkingContent={
  fr:{
    placeholder:"Décrivez votre besoin et Goat Code le traduit en code",
    status:"Le code généré par Goat Code est à titre indicatif — il est recommandé de le tester dans un environnement isolé avant toute intégration en production.",
    messages:[
      "Codez intelligemment avec Goat Code — local, rapide, sans compromis.",
      "Décrivez votre logique, Goat Code structure le code pour vous.",
      "De l'idée à l'implémentation, Goat Code pose les fondations techniques."
    ],
    desc:""
  },
  en:{
    placeholder:"Describe your need and Goat Code will write the code",
    status:"Code generated by Goat Code is provided for reference — it is recommended to test it in an isolated environment before any production integration.",
    messages:[
      "Code smarter with Goat Code — local, fast, no compromise.",
      "Describe your logic, Goat Code structures the code for you.",
      "From idea to implementation, Goat Code lays the technical foundation."
    ],
    desc:""
  },
  es:{
    placeholder:"Describa su necesidad y Goat Code lo traducirá en código",
    status:"El código generado por Goat Code es orientativo — se recomienda probarlo en un entorno aislado antes de cualquier integración en producción.",
    messages:[
      "Programe de forma inteligente con Goat Code — local, rápido, sin compromisos.",
      "Describa su lógica y Goat Code estructurará el código por usted.",
      "De la idea a la implementación, Goat Code sienta las bases técnicas."
    ],
    desc:""
  }
};
// ── Utilitaires de base ───────────────────────────────────────────
function t(k){return(T[S.lang]||T[defs.lang]||{})[k]||(T[defs.lang]||{})[k]||k}  // Traduction
function appTitle(){return S.aiName||(titleByLang[S.lang]||titleByLang[defs.lang])}  // Titre localisé (personnalisable)
// ── Met à jour en temps réel le footer de la sidebar (nom + avatar) ──
// Priorité nom   : aiName > prénom+nom utilisateur > titre par défaut
// Priorité logo  : aiLogo > avatar utilisateur > main-logo > initiales
function updateSidebarProfile(){
  try{
    const nameEl=document.getElementById('sidebar-profile-name');
    const avEl=document.getElementById('sidebar-profile-avatar');
    // On lit les deux jeux de clés : onglet "Profil" (profile-*) prioritaire,
    // sinon onglet "Personnalisation" (firstname / lastname).
    const _read=k=>(typeof ls==='function'?(ls(k)||''):'');
    const pFn=_read('profile-firstname').trim();
    const pLn=_read('profile-lastname').trim();
    const fn=(pFn||_read('firstname').trim());
    const ln=(pLn||_read('lastname').trim());
    const userFull=(fn+' '+ln).trim();
    const aiName=((typeof S!=='undefined'&&S&&S.aiName)||'').trim();
    // Priorité : prénom+nom utilisateur > aiName > titre par défaut
    const displayName=userFull||aiName||(typeof appTitle==='function'?appTitle():'Le Goat')||'Le Goat';
    if(nameEl)nameEl.textContent=displayName;
    if(avEl){
      const aiLogo=((typeof S!=='undefined'&&S&&S.aiLogo)||'');
      const userAvatar=_read('profile-avatar');
      const mainLogoEl=document.getElementById('main-logo');
      const mainLogoSrc=mainLogoEl?(mainLogoEl.getAttribute('src')||''):'';
      const src=aiLogo||userAvatar||mainLogoSrc;
      if(src){
        let img=avEl.querySelector('img');
        if(!img){avEl.textContent='';img=document.createElement('img');img.alt='';avEl.appendChild(img)}
        if(img.getAttribute('src')!==src)img.setAttribute('src',src);
      }else{
        if(avEl.querySelector('img'))avEl.innerHTML='';
        const initials=((fn[0]||'')+(ln[0]||'')).toUpperCase()||((displayName[0]||'G').toUpperCase());
        avEl.textContent=initials;
      }
    }
  }catch(e){/* tolère un appel précoce */}
}
function updateAiName(){if(brandText)brandText.textContent=appTitle();if(tabCoworking)tabCoworking.textContent=appTitle()+' Code';updateSidebarProfile();renderMessages()}
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;')}  // Échappement HTML

// ── Système audio (Web Audio API, synthèse additive) ─────────────
// Aucun fichier audio externe — les sons sont générés en temps réel.
// Pour ajouter un style sonore, ajoutez un cas dans playClick() / playKey().
function ensureAudio(){if(audioCtx)return audioCtx;const A=window.AudioContext||window.webkitAudioContext;if(!A)return null;audioCtx=new A();return audioCtx}
function tone(f,d,type,g,det){const c=ensureAudio();if(!c)return;if(c.state==='suspended')c.resume().catch(()=>{});const o=c.createOscillator(),a=c.createGain();o.type=type||'sine';o.frequency.value=f;o.detune.value=det||0;const n=c.currentTime;a.gain.setValueAtTime(.0001,n);a.gain.exponentialRampToValueAtTime(g||.1,n+.01);a.gain.exponentialRampToValueAtTime(.0001,n+d);o.connect(a);a.connect(c.destination);o.start(n);o.stop(n+d+.01)}
function playClick(){if(S.clickSound!=='on')return;if(S.clickStyle==='nebrise'){tone(260,.055,'sawtooth',.07);setTimeout(()=>tone(340,.045,'triangle',.05),22);return}tone(420,.06,'triangle',.08)}
function playSend(){if(S.clickSound!=='on')return;tone(600,.045,'sine',.10);setTimeout(()=>tone(820,.055,'sine',.08),35)}
function playAiReply(){if(S.aiSound!=='on')return;tone(520,.06,'sine',.085);setTimeout(()=>tone(680,.05,'sine',.07),40)}
let lastKS=0;function playKey(){if(S.kbSound!=='on')return;const n=performance.now();if(n-lastKS<22)return;lastKS=n;if(S.kbStyle==='aurela'){tone(320,.03,'triangle',.06);return}if(S.kbStyle==='verdrock'){tone(180,.025,'square',.045);return}if(S.kbStyle==='feryn'){tone(520,.02,'sine',.06,-12);setTimeout(()=>tone(520,.02,'sine',.05,14),18);return}tone(560,.02,'sine',.05)}

// ── Tooltips ─────────────────────────────────────────────────────
// Les tooltips sont positionnés dynamiquement pour rester dans la fenêtre.
// Liez un tooltip via bindTip(element, 'tooltip_cle') ou bindTip(element, 'Texte direct').
function showTip(el,txt){tooltipEl.textContent=txt;tooltipEl.hidden=false;const r=el.getBoundingClientRect();tooltipEl.style.top=Math.min(innerHeight-12,r.bottom+10)+'px';tooltipEl.style.left=Math.max(12,Math.min(innerWidth-12,r.left))+'px';requestAnimationFrame(()=>tooltipEl.classList.add('show'))}
function hideTip(){tooltipEl.classList.remove('show');setTimeout(()=>{if(!tooltipEl.classList.contains('show'))tooltipEl.hidden=true},120)}
function bindTip(el,k){if(!el)return;el.addEventListener('mouseenter',()=>{ttTimer=setTimeout(()=>showTip(el,k.startsWith('tooltip_')?t(k):k),520)});el.addEventListener('mouseleave',()=>{clearTimeout(ttTimer);hideTip()});el.addEventListener('mousedown',()=>{clearTimeout(ttTimer);hideTip()})}

// ── Character Counter & Contraction Of Chat ──
const CHAR_LIMIT=10000;
const SHEET_CHAR_LIMIT=14000;
function getTotalSheetChars(){return sheets.reduce((sum,txt)=>sum+txt.length,0)}
function getTotalChars(){return ta.value.length+getTotalSheetChars()}
function updateCharCounter(){const inputLen=ta.value.length;const isOC=S.overclock==='on';charCounterText.textContent=inputLen.toLocaleString('fr')+' / '+(isOC?'∞':'10 000');charCounterEl.classList.remove('warning','danger');if(!isOC&&inputLen>=CHAR_LIMIT){charCounterEl.classList.add('danger')}else if(!isOC&&inputLen>=CHAR_LIMIT*0.8){charCounterEl.classList.add('warning')}else if(isOC&&inputLen>=CHAR_LIMIT){charCounterEl.classList.add('danger')}charCounterTip.textContent=isOC&&inputLen>=CHAR_LIMIT?t('char_limit_overclock_tooltip'):t('char_limit_tooltip');updateContraction()}
function enforceCharLimit(){if(S.overclock==='on')return;if(ta.value.length>CHAR_LIMIT){ta.value=ta.value.substring(0,CHAR_LIMIT);updateCharCounter()}}
function updateContraction(){const total=getTotalChars();const show=total>=CHAR_LIMIT;contractionTag.hidden=!show;contractionTip.textContent=t('contraction_tooltip')}

// ── Overclock system ──
function updateOverclockUI(){overclockToggle.classList.toggle('active',S.overclock==='on');updateCharCounter();updateContraction()}
function openOverclockModal(){ocWarningText.textContent=t('overclock_warning');ocConfirmBtn.textContent=t('overclock_confirm');ocCancelBtn.textContent=t('overclock_cancel');ocBackdrop.classList.add('open')}
function closeOverclockModal(){ocBackdrop.classList.remove('open')}
overclockToggle.addEventListener('click',()=>{playClick();if(S.overclock==='on'){S.overclock='off';ls('overclock','off');updateOverclockUI()}else{openOverclockModal()}});
ocConfirmBtn.addEventListener('click',()=>{playClick();S.overclock='on';ls('overclock','on');closeOverclockModal();updateOverclockUI()});
ocCancelBtn.addEventListener('click',()=>{playClick();closeOverclockModal()});
ocBackdrop.addEventListener('click',e=>{if(e.target===ocBackdrop)closeOverclockModal()});

// ── Stop generation ──
function showStopBtn(){sendBtn.hidden=true;stopBtn.hidden=false;isGenerating=true}
function hideStopBtn(){stopBtn.hidden=true;sendBtn.hidden=false;sendBtn.disabled=false;isGenerating=false;abortController=null}
stopBtn.addEventListener('click',()=>{playClick();if(abortController){abortController.abort()}hideStopBtn();statusEl.textContent=ST[S.lang]||ST[defs.lang]});

// ── Font switching ──
function applyAiFont(v,snd){apply('aifont',['default','arial','opendyslexic'].includes(v)?v:'default','aifont',snd);document.body.dataset.aifont=S.aifont;$$('[data-aifont-value]').forEach(b=>b.classList.toggle('active',b.dataset.aifontValue===S.aifont))}
function applyUserFont(v,snd){apply('userfont',['default','arial','opendyslexic'].includes(v)?v:'default','userfont',snd);document.body.dataset.userfont=S.userfont;$$('[data-userfont-value]').forEach(b=>b.classList.toggle('active',b.dataset.userfontValue===S.userfont))}

// ── Model dropdown (ChatGPT style) ──
// Le bandeau supérieur affiche soit le modèle standard (Sukoshi /
// Traditionnel / Maestro), soit "Custom" lorsqu'un modèle personnalisé
// est actif (cf. section "Modèles personnalisés" plus bas).
function renderModelDD(){
  const customActive=(typeof cmHasCustomActive==='function')&&cmHasCustomActive();
  // Étiquette en haut (à gauche du chevron).
  if(customActive){
    modelCurrentLabel.textContent=t('models_custom_label');
  }else{
    const fallback=models.find(m=>m.id===S.model)||models.find(m=>m.id===defs.model)||models[0];
    if(fallback){if(S.model!==fallback.id){S.model=fallback.id;ls('model',S.model)}modelCurrentLabel.textContent=t(fallback.label_key)}
  }
  // Liste : tous les modèles standards. Si un modèle custom est actif,
  // ils sont visuellement verrouillés et un clic ouvre une alerte.
  modelDDMenu.innerHTML='<div class="model-dd-header">'+esc(t('model_recent'))+'</div>'+models.map(m=>{
    const sel=(!customActive&&m.id===S.model);
    const locked=customActive;
    return '<button type="button" class="model-dd-item'+(sel?' selected':'')+(locked?' locked':'')+'" data-model="'+esc(m.id)+'"'+(locked?' aria-disabled="true"':'')+' role="menuitemradio"><div class="m-info"><span class="m-name">'+esc(t(m.label_key))+'</span><span class="m-desc">'+esc(t(m.desc_key))+'</span></div><span class="m-check">✓</span></button>';
  }).join('')+'<div class="model-dd-sep"></div>';
  modelDDMenu.querySelectorAll('[data-model]').forEach(b=>b.addEventListener('click',()=>{
    playClick();
    if(customActive){
      // Verrou : pour basculer vers Sukoshi/Maestro/Traditionnel,
      // l'utilisateur doit d'abord remettre le modèle sur "Par défaut".
      alert(t('models_default_required'));
      return;
    }
    const nextModel=b.dataset.model;
    if(nextModel===S.model){closeModelDD();return}
    S.model=nextModel;ls('model',S.model);
    enforceMode();renderModelDD();renderModes();updateModeUI();renderStyles();updateStyleUI();renderGadgets();updateGadgetUI();
    if(typeof updateCustomModelTriggerUI==='function')updateCustomModelTriggerUI();
    closeModelDD();refreshWelcomeContent();
    statusEl.textContent=activeTab==='coworking'?getCoworkingContent().status:(ST[S.lang]||ST[defs.lang]);
  }));
}
function openModelDD(){modelDDMenu.classList.add('open');modelTriggerBtn.setAttribute('aria-expanded','true');var tc=$('tab-chat');if(tc)tc.setAttribute('aria-expanded','true')}
function closeModelDD(){modelDDMenu.classList.remove('open');modelTriggerBtn.setAttribute('aria-expanded','false');var tc=$('tab-chat');if(tc)tc.setAttribute('aria-expanded','false')}
modelTriggerBtn.addEventListener('click',()=>{playClick();modelDDMenu.classList.contains('open')?closeModelDD():openModelDD()});

// ── Private Chat (mode incognito) ──
let themeBeforePrivate=null;
function enterPrivateChat(){
  // Si on est dans Goat Code, revenir au chat d'abord
  if(activeTab==='coworking'){activeTab='chat';updateTabUI()}
  S.privateChat=true;
  privateChatBtn.classList.add('active');
  // Désactiver l'onglet Goat Code
  if(tabCoworking){tabCoworking.disabled=true}
  themeBeforePrivate=S.theme;
  document.body.dataset.theme='dark';S.theme='dark';
  $$('[data-theme-value]').forEach(b=>b.classList.toggle('active',b.dataset.themeValue==='dark'));
  updateThemedLogos();
  messages=[];renderMessages();
  welcomeEl.textContent=t('private_chat_welcome');
  welcomeDesc.textContent=t('private_chat_welcome_desc');
  ta.value='';autoResize();
  statusEl.textContent=ST[S.lang]||ST[defs.lang];
  fetch('/api/new_chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})}).catch(()=>{})
}
function exitPrivateChat(){
  S.privateChat=false;
  privateChatBtn.classList.remove('active');
  // Réactiver l'onglet Goat Code
  if(tabCoworking){tabCoworking.disabled=false}
  const restore=themeBeforePrivate||defs.theme;
  themeBeforePrivate=null;
  applyTheme(restore,false);
  refreshWelcomeContent()
}
privateChatBtn.addEventListener('click',()=>{playClick();S.privateChat?exitPrivateChat():enterPrivateChat()});
function updatePrivateChatLabels(){$('pc-title').textContent=t('private_chat');$('pc-desc').textContent=t('private_chat_desc')}

// ── Modes ──
function isModeOff(id){return S.optResp==='on'&&DM.includes(id)}
function isStyleOff(){return false}
function enforceMode(){if(S.mode&&isModeOff(S.mode)){S.mode='fast';ls('mode',S.mode)}if(S.wstyle&&isStyleOff()){S.wstyle='';ls('wstyle',S.wstyle)}}
function updateModeUI(){enforceMode();const m=MO.find(o=>o.id===S.mode);modeLbl.textContent=m?t('mode_'+m.id):t('no_mode');modeIcn.textContent=m?m.icon:'○';modeAnn.textContent=m?t('mode_active_prefix')+' '+t('mode_'+m.id):''}
function renderModes(){modeMenu.innerHTML=MO.map(o=>{const sel=o.id===S.mode,dis=isModeOff(o.id);return'<button type="button" class="dropdown-menu-item'+(sel?' selected':'')+(dis?' disabled':'')+'" data-mode-id="'+esc(o.id)+'" '+(dis?'disabled':'')+' role="menuitemradio"><span class="dm-icon">'+esc(o.icon)+'</span><span class="dm-label">'+esc(t('mode_'+o.id))+'</span><span class="dm-check">✓</span></button>'}).join('');modeMenu.querySelectorAll('[data-mode-id]').forEach(b=>{bindTip(b,'tooltip_mode_'+b.dataset.modeId);b.addEventListener('click',()=>{if(b.disabled)return;playClick();S.mode=(b.dataset.modeId===S.mode)?'':b.dataset.modeId;ls('mode',S.mode);renderModes();updateModeUI();closeMM()})})}
function openMM(){modeMenu.classList.add('open');modeTrigger.setAttribute('aria-expanded','true')}
function closeMM(){modeMenu.classList.remove('open');modeTrigger.setAttribute('aria-expanded','false')}

// ── Writing Styles ──
function updateStyleUI(){const s=wStyles.find(o=>o.id===S.wstyle);styleLbl.textContent=s?t('style_'+s.id):t('writing_style_label');styleIcn.textContent=s?s.icon:'✎'}
function renderStyles(){const blocked=isStyleOff();styleMenu.innerHTML=wStyles.map(o=>{const sel=o.id===S.wstyle;return'<button type="button" class="dropdown-menu-item'+(sel?' selected':'')+(blocked?' disabled':'')+'" data-style-id="'+esc(o.id)+'" '+(blocked?'disabled':'')+' role="menuitemradio"><span class="dm-icon">'+esc(o.icon)+'</span><span class="dm-label">'+esc(t('style_'+o.id))+'</span><span class="dm-check">✓</span></button>'}).join('');styleMenu.querySelectorAll('[data-style-id]').forEach(b=>{bindTip(b,'tooltip_style_'+b.dataset.styleId);b.addEventListener('click',()=>{if(b.disabled)return;playClick();S.wstyle=(b.dataset.styleId===S.wstyle)?'':b.dataset.styleId;ls('wstyle',S.wstyle);renderStyles();updateStyleUI();closeSM()})})}
function openSM(){styleMenu.classList.add('open');styleTrigger.setAttribute('aria-expanded','true')}
function closeSM(){styleMenu.classList.remove('open');styleTrigger.setAttribute('aria-expanded','false')}

/* ── Gadgets (desactive pour le moment) ──
function updateGadgetUI(){const g=gadgets.find(o=>o.id===S.gadget);gadgetLbl.textContent=g?t('gadget_'+g.id):t('gadget_label');gadgetIcn.textContent=g?g.icon:'⚙'}
function renderGadgets(){gadgetMenu.innerHTML=gadgets.map(o=>{const sel=o.id===S.gadget;return'<button type="button" class="dropdown-menu-item'+(sel?' selected':'')+'" data-gadget-id="'+esc(o.id)+'" role="menuitemradio"><span class="dm-icon">'+esc(o.icon)+'</span><span class="dm-label">'+esc(t('gadget_'+o.id))+'</span><span class="dm-check">✓</span></button>'}).join('');gadgetMenu.querySelectorAll('[data-gadget-id]').forEach(b=>{bindTip(b,'tooltip_gadget_'+b.dataset.gadgetId);b.addEventListener('click',()=>{playClick();S.gadget=(b.dataset.gadgetId===S.gadget)?'':b.dataset.gadgetId;ls('gadget',S.gadget);renderGadgets();updateGadgetUI();closeGM()})})}
function openGM(){gadgetMenu.classList.add('open');gadgetTrigger.setAttribute('aria-expanded','true')}
function closeGM(){gadgetMenu.classList.remove('open');gadgetTrigger.setAttribute('aria-expanded','false')}
*/
function updateGadgetUI(){}
function renderGadgets(){}
function openGM(){}
function closeGM(){}

// =================================================================
// ── Modèles personnalisés ─────────────────────────────────────────
// =================================================================
// Activé via Settings → Personnalisation → "Autres modèles".
// Lorsque actif, un bouton "Modèles" apparaît à côté du sélecteur
// de style d'écriture. Il permet d'ajouter / renommer / supprimer
// des modèles personnalisés. Sélectionner un modèle custom remplace
// l'étiquette du bandeau supérieur ("Traditionnel" → "Custom") et
// verrouille les modèles d'origine jusqu'à ce que l'utilisateur
// remette le modèle sur "Par défaut" via le menu modèle du haut.
// -----------------------------------------------------------------

// État utilitaires —
function cmGenId(){return 'cm-'+Date.now().toString(36)+'-'+Math.random().toString(36).slice(2,7)}
function cmSave(){ls('custom-models',JSON.stringify(S.customModels||[]))}
function cmGet(id){return (S.customModels||[]).find(m=>m.id===id)||null}
function cmHasCustomActive(){return !!(S.activeCustomModel&&cmGet(S.activeCustomModel))}
function cmTrimName(s){return String(s||'').trim().slice(0,64)}
function cmNameTaken(name,exceptId){const n=name.toLowerCase();return (S.customModels||[]).some(m=>m.id!==exceptId&&String(m.name).toLowerCase()===n)}

// Affiche/masque le bouton "Modèles" selon l'état de l'interrupteur.
function applyOtherModelsOn(v,snd){
  apply('otherModelsOn',v==='on'?'on':'off','other-models-on',snd);
  if(otherModelsToggle)otherModelsToggle.checked=(S.otherModelsOn==='on');
  if(customModelsPanel)customModelsPanel.hidden=(S.otherModelsOn!=='on');
  // Si désactivé : on ferme le menu et on retombe sur le modèle par défaut.
  if(S.otherModelsOn!=='on'){
    closeCustomModelsMenu();
    if(cmHasCustomActive()){
      S.activeCustomModel='';ls('active-custom-model','');
      S.model=defs.model;ls('model',S.model);
      renderModelDD();
    }
  }
  renderCustomModelsMenu();
  updateCustomModelTriggerUI();
}

// Met à jour l'icône + libellé du bouton "Modèles" (affiche le nom du
// modèle actif s'il y en a un, sinon le libellé générique).
function updateCustomModelTriggerUI(){
  if(!customModelsLabel)return;
  const active=cmHasCustomActive()?cmGet(S.activeCustomModel):null;
  customModelsLabel.textContent=active?active.name:t('models_btn_label');
  const icon=$('custom-models-icon');
  if(icon)icon.textContent=active?'✦':'⚙';
  if(customModelsTrigger)customModelsTrigger.classList.toggle('active',!!active);
}

// Rend le contenu du menu déroulant "Modèles".
function renderCustomModelsMenu(){
  if(!customModelsMenu)return;
  const list=S.customModels||[];
  let html='';
  if(cmHasCustomActive()){
    html+='<button type="button" class="custom-models-default-btn" id="cm-set-default-btn">'+esc(t('models_set_default'))+'</button>';
    html+='<div class="custom-models-sep"></div>';
  }
  if(!list.length){
    html+='<div class="custom-models-empty">'+esc(t('models_no_custom'))+'</div>';
  }else{
    html+=list.map(m=>{
      const sel=(S.activeCustomModel===m.id);
      return '<div class="custom-model-row'+(sel?' selected':'')+'" data-cm-id="'+esc(m.id)+'" role="menuitemradio">'+
        '<span class="cmr-name">'+esc(m.name)+'</span>'+
        '<span class="cmr-actions">'+
          '<button type="button" class="cmr-act-btn" data-cm-action="rename" data-cm-id="'+esc(m.id)+'" title="'+esc(t('models_rename'))+'" aria-label="'+esc(t('models_rename'))+'">✎</button>'+
          '<button type="button" class="cmr-act-btn" data-cm-action="delete" data-cm-id="'+esc(m.id)+'" title="'+esc(t('models_delete'))+'" aria-label="'+esc(t('models_delete'))+'">🗑</button>'+
        '</span>'+
      '</div>';
    }).join('');
  }
  html+='<button type="button" class="custom-models-add-btn" id="cm-add-btn">+ '+esc(t('models_add'))+'</button>';
  customModelsMenu.innerHTML=html;

  // Ajout
  const addBtn=$('cm-add-btn');
  if(addBtn)addBtn.addEventListener('click',e=>{e.stopPropagation();playClick();openCustomModelModal('add')});
  // Reset par défaut
  const resetBtn=$('cm-set-default-btn');
  if(resetBtn)resetBtn.addEventListener('click',e=>{e.stopPropagation();playClick();resetActiveCustomModel()});
  // Sélection / actions
  customModelsMenu.querySelectorAll('[data-cm-action]').forEach(btn=>{
    btn.addEventListener('click',e=>{
      e.stopPropagation();playClick();
      const id=btn.dataset.cmId,act=btn.dataset.cmAction;
      if(act==='rename')openCustomModelModal('rename',id);
      else if(act==='delete')deleteCustomModel(id);
    });
  });
  customModelsMenu.querySelectorAll('.custom-model-row').forEach(row=>{
    row.addEventListener('click',e=>{
      if(e.target.closest('[data-cm-action]'))return;
      playClick();selectCustomModel(row.dataset.cmId);
    });
  });
}

function openCustomModelsMenu(){if(!customModelsMenu)return;customModelsMenu.classList.add('open');if(customModelsTrigger)customModelsTrigger.setAttribute('aria-expanded','true')}
function closeCustomModelsMenu(){if(!customModelsMenu)return;customModelsMenu.classList.remove('open');if(customModelsTrigger)customModelsTrigger.setAttribute('aria-expanded','false')}

// Sélection d'un modèle custom : pose le sentinel sur S.model et
// l'id réel sur S.activeCustomModel. Re-cliquer déselectionne.
function selectCustomModel(id){
  const m=cmGet(id);if(!m)return;
  if(S.activeCustomModel===id){
    resetActiveCustomModel();
    return;
  }
  S.activeCustomModel=id;ls('active-custom-model',id);
  S.model=CUSTOM_MODEL_SENTINEL;ls('model',S.model);
  enforceMode();renderModelDD();renderModes();updateModeUI();renderStyles();updateStyleUI();
  renderCustomModelsMenu();updateCustomModelTriggerUI();
  closeCustomModelsMenu();
  refreshWelcomeContent();
}

// Remet le modèle sur le défaut (sortie du mode "custom").
function resetActiveCustomModel(){
  S.activeCustomModel='';ls('active-custom-model','');
  S.model=defs.model;ls('model',S.model);
  enforceMode();renderModelDD();renderModes();updateModeUI();renderStyles();updateStyleUI();
  renderCustomModelsMenu();updateCustomModelTriggerUI();
  refreshWelcomeContent();
}

// ── Modale "NAME Models" ─────────────────────────────────────
let customModelEditTarget=null;   // 'add' | id-en-cours-de-renommage
function openCustomModelModal(mode,id){
  customModelEditTarget=(mode==='rename'&&id)?id:'add';
  if(customModelTitleEl)customModelTitleEl.textContent=t('models_modal_title');
  customModelInput.value=(mode==='rename')?(cmGet(id)?cmGet(id).name:''):'';
  customModelErrorEl.hidden=true;customModelErrorEl.textContent='';
  customModelBackdrop.classList.add('open');
  setTimeout(()=>{customModelInput.focus();customModelInput.select()},40);
}
function closeCustomModelModal(){customModelBackdrop.classList.remove('open');customModelEditTarget=null}

function submitCustomModelModal(){
  const name=cmTrimName(customModelInput.value);
  if(!name){customModelErrorEl.textContent=t('models_invalid_name');customModelErrorEl.hidden=false;return}
  const editingId=(customModelEditTarget&&customModelEditTarget!=='add')?customModelEditTarget:null;
  if(cmNameTaken(name,editingId)){customModelErrorEl.textContent=t('models_duplicate_name');customModelErrorEl.hidden=false;return}
  if(editingId){
    const m=cmGet(editingId);if(m)m.name=name;
  }else{
    const newModel={id:cmGenId(),name:name};
    S.customModels.push(newModel);
  }
  cmSave();
  renderCustomModelsMenu();updateCustomModelTriggerUI();
  closeCustomModelModal();
}

function deleteCustomModel(id){
  if(!confirm(t('models_delete_confirm')))return;
  const list=S.customModels||[];
  S.customModels=list.filter(m=>m.id!==id);
  cmSave();
  if(S.activeCustomModel===id){
    // Le modèle actif vient d'être supprimé : on retombe sur le défaut.
    resetActiveCustomModel();
  }else{
    renderCustomModelsMenu();updateCustomModelTriggerUI();
  }
}

// Hook d'événements (déclenchés une seule fois au chargement).
if(otherModelsToggle){otherModelsToggle.addEventListener('change',()=>{playClick();applyOtherModelsOn(otherModelsToggle.checked?'on':'off')})}
if(customModelsTrigger){customModelsTrigger.addEventListener('click',e=>{e.stopPropagation();playClick();customModelsMenu.classList.contains('open')?closeCustomModelsMenu():openCustomModelsMenu()})}
if(customModelEnterBtn){customModelEnterBtn.addEventListener('click',submitCustomModelModal)}
if(customModelCancelBtn){customModelCancelBtn.addEventListener('click',closeCustomModelModal)}
if(customModelBackdrop){customModelBackdrop.addEventListener('click',e=>{if(e.target===customModelBackdrop)closeCustomModelModal()})}
if(customModelInput){customModelInput.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();submitCustomModelModal()}else if(e.key==='Escape'){e.preventDefault();closeCustomModelModal()}})}
// Fermer le menu déroulant lorsqu'on clique en dehors.
document.addEventListener('click',e=>{
  if(!customModelsMenu||!customModelsMenu.classList.contains('open'))return;
  if(customModelsMenu.contains(e.target)||(customModelsTrigger&&customModelsTrigger.contains(e.target)))return;
  closeCustomModelsMenu();
});

// ── Migration modal ──
function openMigrate(){migrateTitle.textContent=t('migrate_title');migrateStep1.textContent=t('migrate_step1');migrateStep2.textContent=t('migrate_step2');migratePromptBox.textContent=migrationPrompt;migrateTA.value='';migrateTA.placeholder=t('migrate_paste_placeholder');migrateAddBtn.textContent=t('migrate_add');migrateCancelBtn.textContent=t('migrate_cancel');migrateAddBtn.disabled=true;migrateBackdrop.classList.add('open')}
function closeMigrate(){migrateBackdrop.classList.remove('open')}
migrateTA.addEventListener('input',()=>{migrateAddBtn.disabled=!migrateTA.value.trim()});
migrateAddBtn.addEventListener('click',()=>{closeMigrate();alert(t('migrate_success'))});
migrateCancelBtn.addEventListener('click',closeMigrate);
migrateCloseX.addEventListener('click',closeMigrate);
migrateBackdrop.addEventListener('click',e=>{if(e.target===migrateBackdrop)closeMigrate()});
// Copy button inside prompt box
migratePromptBox.insertAdjacentHTML('afterend','');
document.addEventListener('click',e=>{if(e.target&&e.target.id==='migrate-copy-btn'){const tx=migrationPrompt;navigator.clipboard.writeText(tx).then(()=>{e.target.textContent='✓'}).catch(()=>{});setTimeout(()=>{if(e.target)e.target.textContent=t('migrate_copy')},1500)}});

// ── Messages ──
// ── Sheets system ──
function renderSheets(){sheetsRow.innerHTML=sheets.map((txt,i)=>'<div class="sheet-thumb"><span>'+esc(txt.substring(0,80))+'</span><button type="button" class="sheet-remove" data-sheet-idx="'+i+'">×</button></div>').join('');sheetsRow.querySelectorAll('.sheet-remove').forEach(b=>b.addEventListener('click',e=>{e.stopPropagation();sheets.splice(+b.dataset.sheetIdx,1);renderSheets();updateCharCounter()}));updateContraction()}
function openSheetModal(){sheetTitle.textContent=t('sheet_title');sheetAddBtn.textContent=t('sheet_add');sheetCancelBtn.textContent=t('sheet_cancel');sheetTA.value='';updateSheetCharCounter();sheetBackdrop.classList.add('open')}
function closeSheetModal(){sheetBackdrop.classList.remove('open')}
function updateSheetCharCounter(){const len=sheetTA.value.length;const isOC=S.overclock==='on';sheetCharCounter.textContent=len.toLocaleString('fr')+' / '+(isOC?'∞':'14 000');sheetCharCounter.classList.toggle('danger',!isOC&&len>=SHEET_CHAR_LIMIT)}
function enforceSheetCharLimit(){if(S.overclock==='on')return;if(sheetTA.value.length>SHEET_CHAR_LIMIT){sheetTA.value=sheetTA.value.substring(0,SHEET_CHAR_LIMIT);updateSheetCharCounter()}}
sheetTA.addEventListener('input',()=>{enforceSheetCharLimit();updateSheetCharCounter()});
sheetAddBtn.addEventListener('click',()=>{const v=sheetTA.value.trim();if(!v)return;const maxSheets=S.overclock==='on'?10:1;if(sheets.length>=maxSheets){alert(S.overclock==='on'?t('sheets_max'):t('sheets_max_one'));return}if(S.overclock!=='on'&&v.length>SHEET_CHAR_LIMIT){return}sheets.push(v);renderSheets();closeSheetModal();updateCharCounter()});
sheetCancelBtn.addEventListener('click',closeSheetModal);
sheetBackdrop.addEventListener('click',e=>{if(e.target===sheetBackdrop)closeSheetModal()});
composerPlus.addEventListener('click',()=>{playClick();plusMenu.classList.toggle('open')});
plusAddSheet.addEventListener('click',()=>{playClick();plusMenu.classList.remove('open');openSheetModal()});

// ── Messages (with Goat Code buttons) ──
function shouldShowProfileAvatarInMessages(){return profileGet('showMessageAvatar','off')==='on'}
function getProfileAvatarForMessages(){return profileGet('avatar','')||($('main-logo')?$('main-logo').getAttribute('src'):'')}
function showProfileAvatarHover(target){if(!profileAvatarHoverCard||!profileAvatarHoverImage||!profileAvatarHoverName||!profileAvatarHoverBio)return;const data=getProfileData();const src=data.avatar||getProfileAvatarForMessages();if(!src)return;profileAvatarHoverImage.src=src;applyAvatarFitMode(profileAvatarHoverImage,src);profileAvatarHoverName.textContent=getProfileFullName(data);profileAvatarHoverBio.textContent=(data.bio||t('profile_preview_title'));if(profileAvatarHoverBanner)profileAvatarHoverBanner.style.backgroundImage=data.banner?'url("'+String(data.banner).replace(/"/g,'\"')+'")':'';const rect=target.getBoundingClientRect();const cardW=288,cardH=178;let left=rect.left-cardW+rect.width;if(left<12)left=Math.min(window.innerWidth-cardW-12,rect.right+10);let top=rect.top-(cardH-rect.height)/2;top=Math.max(12,Math.min(window.innerHeight-cardH-12,top));profileAvatarHoverCard.hidden=false;profileAvatarHoverCard.style.left=left+'px';profileAvatarHoverCard.style.top=top+'px';requestAnimationFrame(()=>profileAvatarHoverCard.classList.add('show'))}
function hideProfileAvatarHover(immediate){clearTimeout(avatarHoverTimer);if(!profileAvatarHoverCard)return;if(immediate){profileAvatarHoverCard.classList.remove('show');profileAvatarHoverCard.hidden=true;return}profileAvatarHoverCard.classList.remove('show');setTimeout(()=>{if(profileAvatarHoverCard&&!profileAvatarHoverCard.classList.contains('show'))profileAvatarHoverCard.hidden=true},160)}
function bindUserAvatarHover(scope){if(!scope)return;scope.querySelectorAll('.message-user-avatar').forEach(el=>{el.addEventListener('mouseenter',()=>{clearTimeout(avatarHoverTimer);avatarHoverTimer=setTimeout(()=>showProfileAvatarHover(el),500)});el.addEventListener('mouseleave',()=>hideProfileAvatarHover(false))})}

// ── Helpers « Spécificité » ──────────────────────────────────────────────
// Ces fonctions formatent les méta-données associées à chaque réponse IA
// (mode, style, modèle, pièces jointes, horodatage, durée) pour les afficher
// dans le panneau dépliant sous chaque bulle assistant.

// Convertit un timestamp Python (secondes depuis epoch, float) en chaîne
// localisée du type "08/05/2026 14:32:18". Retourne '' si invalide.
function formatSpecTimestamp(ts){
  if(typeof ts!=='number'||!isFinite(ts)||ts<=0)return '';
  const d=new Date(ts*1000);
  if(isNaN(d.getTime()))return '';
  const lang=({fr:'fr-FR',en:'en-US',es:'es-ES'})[S.lang]||'fr-FR';
  try{
    return d.toLocaleString(lang,{
      year:'numeric',month:'2-digit',day:'2-digit',
      hour:'2-digit',minute:'2-digit',second:'2-digit'
    });
  }catch(e){return d.toISOString()}
}

// Formate une durée en millisecondes au format "1.42 s" ou "850 ms".
function formatSpecDuration(ms){
  if(typeof ms!=='number'||!isFinite(ms)||ms<0)return '';
  if(ms>=1000)return (ms/1000).toFixed(2).replace(/\.?0+$/,'')+' '+t('specificity_seconds_short');
  return Math.round(ms)+' '+t('specificity_milliseconds_short');
}

// Convertit une taille en octets en chaîne lisible (B / KB / MB).
function formatSpecSize(bytes){
  const n=Number(bytes)||0;
  if(n<=0)return '';
  if(n<1024)return n+' B';
  if(n<1024*1024)return (n/1024).toFixed(1).replace(/\.0$/,'')+' KB';
  return (n/(1024*1024)).toFixed(2).replace(/\.?0+$/,'')+' MB';
}

// Résolution id → libellé humain (réutilise les traductions existantes).
function resolveModeLabel(id){
  if(!id)return '';
  const opt=(MO||[]).find(m=>m&&m.id===id);
  if(opt){const k='mode_'+opt.id;const tr=t(k);if(tr&&tr!==k)return tr}
  const k='mode_'+id;const tr=t(k);return (tr&&tr!==k)?tr:id;
}
function resolveStyleLabel(id){
  if(!id)return '';
  const k='style_'+id;const tr=t(k);return (tr&&tr!==k)?tr:id;
}
function resolveModelLabel(meta){
  if(!meta)return '';
  // Modèle personnalisé saisi par l'utilisateur (ex. "mistral small 4 bas").
  if(meta.custom_model_name)return meta.custom_model_name;
  if(meta.model===CUSTOM_MODEL_SENTINEL){return t('specificity_custom_model')}
  if(!meta.model)return '';
  const opt=(models||[]).find(m=>m&&m.id===meta.model);
  if(opt&&opt.label_key){const tr=t(opt.label_key);if(tr&&tr!==opt.label_key)return tr}
  const k='model_'+meta.model;const tr=t(k);return (tr&&tr!==k)?tr:meta.model;
}

// Construit le HTML d'une ligne du panneau (label + valeur, ou état "vide").
function buildSpecRow(labelKey,value,muted){
  const v=(value===undefined||value===null||value==='')
    ? '<span class="specificity-value is-muted">'+esc(t('specificity_none'))+'</span>'
    : '<span class="specificity-value'+(muted?' is-muted':'')+'">'+value+'</span>';
  return '<div class="specificity-label">'+esc(t(labelKey))+'</div>'+v;
}

// Construit la liste HTML des pièces jointes pour le panneau.
function buildSpecAttachments(list){
  if(!Array.isArray(list)||list.length===0){
    return '<span class="specificity-value is-muted">'+esc(t('specificity_no_attachments'))+'</span>';
  }
  const items=list.map(a=>{
    const kind=esc((a&&a.kind)||'file');
    const name=esc((a&&a.name)||'-');
    const size=formatSpecSize(a&&a.size);
    return '<div class="specificity-attachment">'
      +'<span class="specificity-attachment-kind">'+kind+'</span>'
      +'<span class="specificity-attachment-name">'+name+'</span>'
      +(size?'<span class="specificity-attachment-size">'+esc(size)+'</span>':'')
      +'</div>';
  }).join('');
  return '<div class="specificity-attachments">'+items+'</div>';
}

// Construit le HTML du panneau dépliant pour un message assistant donné.
function buildSpecPanel(meta,idx){
  const isOpen=openSpecificityPanels.has(idx);
  if(!meta||meta.role!=='assistant'){
    return '<div class="specificity-panel'+(isOpen?' open':'')+'" data-spec-index="'+idx+'">'
      +'<p class="specificity-panel-title">'+esc(t('specificity_title'))+'</p>'
      +'<div class="specificity-value is-muted">'+esc(t('specificity_unavailable'))+'</div>'
      +'</div>';
  }
  const modeLabel  = resolveModeLabel(meta.mode);
  const styleLabel = resolveStyleLabel(meta.style);
  const modelLabel = resolveModelLabel(meta);
  const reqTime    = formatSpecTimestamp(meta.request_ts);
  const resTime    = formatSpecTimestamp(meta.response_ts);
  const dur        = formatSpecDuration(meta.duration_ms);
  let html='<div class="specificity-panel'+(isOpen?' open':'')+'" data-spec-index="'+idx+'">';
  html+='<p class="specificity-panel-title">'+esc(t('specificity_title'))+'</p>';
  html+='<div class="specificity-grid">';
  html+=buildSpecRow('specificity_mode',         modeLabel ?esc(modeLabel) :'');
  html+=buildSpecRow('specificity_style',        styleLabel?esc(styleLabel):'');
  html+=buildSpecRow('specificity_model',        modelLabel?esc(modelLabel):'');
  html+='<div class="specificity-label">'+esc(t('specificity_attachments'))+'</div>';
  html+=buildSpecAttachments(meta.attachments);
  html+=buildSpecRow('specificity_request_time', reqTime?esc(reqTime):'');
  html+=buildSpecRow('specificity_response_time',resTime?esc(resTime):'');
  html+=buildSpecRow('specificity_duration',     dur?esc(dur):'');
  html+='</div></div>';
  return html;
}

// Bascule l'affichage du panneau « Spécificité » pour le message d'index `idx`.
// On modifie uniquement la ligne concernée (pas de full re-render) afin de
// préserver la position de scroll et l'état des autres panneaux.
function toggleSpecificityPanel(idx){
  if(openSpecificityPanels.has(idx))openSpecificityPanels.delete(idx);
  else openSpecificityPanels.add(idx);
  const panel=msgBox.querySelector('.specificity-panel[data-spec-index="'+idx+'"]');
  if(panel)panel.classList.toggle('open',openSpecificityPanels.has(idx));
  const btn=msgBox.querySelector('.bubble-action[data-action="specificity"][data-msg-index="'+idx+'"]');
  if(btn)btn.classList.toggle('is-active',openSpecificityPanels.has(idx));
}

function renderMessages(){const last=messages.length-1;const dotsHtml='<div class="typing-dots"><span></span><span></span><span></span></div>';const isCode=activeTab==='coworking';const showUserAvatar=shouldShowProfileAvatarInMessages();const userAvatar=getProfileAvatarForMessages();msgBox.innerHTML=messages.map(([s,txt],i)=>{const e=esc(txt);const isLoading=txt==='\u2026';if(s!=='Vous'){
      // ── Bulle assistant ────────────────────────────────────────────
      let acts='';
      if(!isLoading){
        // Le bouton « Spécificité » est visible sur toutes les réponses IA
        // afin de pouvoir consulter rétrospectivement le contexte d'une
        // réponse, même après plusieurs envois.
        acts='<div class="bubble-actions">';
        acts+='<button type="button" class="bubble-action'+(openSpecificityPanels.has(i)?' is-active':'')+'" data-action="specificity" data-tooltip-key="tooltip_specificity" data-msg-index="'+i+'" aria-expanded="'+(openSpecificityPanels.has(i)?'true':'false')+'">'+esc(t('specificity'))+'</button>';
        // Les actions « Relancer / Relire / Analyser / Exécuter » ne
        // s'appliquent qu'à la dernière réponse pour éviter les régressions
        // (modifier une réponse intermédiaire briserait l'historique).
        if(i===last){
          acts+='<button type="button" class="bubble-action" data-action="regenerate" data-tooltip-key="tooltip_regenerate">'+esc(t('regenerate'))+'</button>';
          if(isCode){
            acts+='<button type="button" class="bubble-action" data-action="review">'+esc(t('review_code'))+'</button>';
            acts+='<button type="button" class="bubble-action" data-action="analyze">'+esc(t('analyze_code'))+'</button>';
            acts+='<button type="button" class="bubble-action" data-action="execute" data-tooltip-key="tooltip_execute_code">'+esc(t('execute_code'))+'</button>';
          }
        }
        acts+='</div>';
      }
      const panelHtml=isLoading?'':buildSpecPanel((messagesMeta||[])[i],i);
      return '<div class="message-row assistant"><div class="bubble">'+(isLoading?dotsHtml:e)+'</div>'+acts+panelHtml+'</div>';
    }const avatarHtml=showUserAvatar&&userAvatar?'<div class="message-user-avatar"><img class="'+(isLogoStyleAvatarSrc(userAvatar)?'is-logo':'')+'" src="'+esc(userAvatar)+'" alt="Photo utilisateur"></div>':'';return'<div class="message-row user"><div class="bubble">'+e+'</div>'+avatarHtml+'</div>'}).join('');shell.classList.toggle('has-messages',messages.length>0);msgBox.scrollTop=msgBox.scrollHeight;bindUserAvatarHover(msgBox);
  // ── Bouton « Spécificité » : toggle du panneau associé ───────────
  msgBox.querySelectorAll('[data-action="specificity"]').forEach(b=>{
    bindTip(b,'tooltip_specificity');
    b.addEventListener('click',()=>{
      playClick();
      const idx=parseInt(b.dataset.msgIndex,10);
      if(!isFinite(idx))return;
      toggleSpecificityPanel(idx);
      b.setAttribute('aria-expanded',openSpecificityPanels.has(idx)?'true':'false');
    });
  });
  msgBox.querySelectorAll('[data-action="regenerate"]').forEach(b=>{bindTip(b,'tooltip_regenerate');b.addEventListener('click',async()=>{playClick();statusEl.textContent='...';showStopBtn();abortController=new AbortController();try{const p=await apiSend(t('regenerate_command'),abortController.signal);messages=p.messages;messagesMeta=p.metas||[];renderMessages();statusEl.textContent=ST[S.lang]||ST[defs.lang];playAiReply()}catch(e){if(e.name!=='AbortError')statusEl.textContent=e.message}finally{hideStopBtn()}})});msgBox.querySelectorAll('[data-action="review"]').forEach(b=>b.addEventListener('click',async()=>{playClick();statusEl.textContent='...';try{const p=await apiSend('Relis et vérifie le code que tu viens de générer.');messages=p.messages;messagesMeta=p.metas||[];renderMessages();statusEl.textContent=ST[S.lang]||ST[defs.lang];playAiReply()}catch(e){statusEl.textContent=e.message}}));msgBox.querySelectorAll('[data-action="analyze"]').forEach(b=>b.addEventListener('click',async()=>{playClick();statusEl.textContent='...';try{const p=await apiSend('Analyse en détail le code que tu viens de générer : structure, complexité, points forts et points faibles.');messages=p.messages;messagesMeta=p.metas||[];renderMessages();statusEl.textContent=ST[S.lang]||ST[defs.lang];playAiReply()}catch(e){statusEl.textContent=e.message}}));msgBox.querySelectorAll('[data-action="execute"]').forEach(b=>{bindTip(b,'tooltip_execute_code');b.addEventListener('click',async()=>{playClick();statusEl.textContent='...';try{const p=await apiSend('Exécute en simulation le code que tu viens de générer et dis-moi si il devrait fonctionner correctement.');messages=p.messages;messagesMeta=p.metas||[];renderMessages();statusEl.textContent=ST[S.lang]||ST[defs.lang];playAiReply()}catch(e){statusEl.textContent=e.message}})})}
let resizeRAF=null;function autoResize(){if(resizeRAF)cancelAnimationFrame(resizeRAF);resizeRAF=requestAnimationFrame(()=>{ta.style.height='auto';ta.style.height=Math.min(ta.scrollHeight,180)+'px'})}

// ── Settings ──
function resetModal(){modal.style.left='50%';modal.style.top='50%';modal.style.transform='translate(-50%,-50%)'}
function openSettings(){playClick();if(settingsOpen)return;settingsOpen=true;resetModal();backdrop.hidden=false;modal.hidden=false;requestAnimationFrame(()=>{backdrop.classList.add('open');modal.classList.add('open')})}
function closeSettings(){playClick();if(!settingsOpen)return;settingsOpen=false;backdrop.classList.remove('open');modal.classList.remove('open');setTimeout(()=>{if(!settingsOpen){backdrop.hidden=true;modal.hidden=true;resetModal()}},180)}
function showTab(id){const section=id||'general';ls('settings-tab',section);$$('[data-settings-tab]').forEach(t=>t.classList.toggle('active',t.dataset.settingsTab===section));$$('[data-settings-content]').forEach(s=>s.classList.toggle('active',s.dataset.settingsContent===section));const content=$('settings-content');if(content)content.scrollTop=0}
function startDrag(e){if(innerWidth<=900)return;if(e.target.closest('button'))return;const r=modal.getBoundingClientRect();modal.style.left=r.left+'px';modal.style.top=r.top+'px';modal.style.transform='none';dragging=true;dragSX=e.clientX;dragSY=e.clientY;mSL=r.left;mST=r.top;e.preventDefault()}
function onDrag(e){if(!dragging)return;modal.style.left=Math.max(12,mSL+(e.clientX-dragSX))+'px';modal.style.top=Math.max(12,mST+(e.clientY-dragSY))+'px'}

// ── Apply settings (UI opt auto-disable quand on réactive un son) ──
function apply(key,val,lsKey,sound){if(sound!==false)playClick();S[key]=val;ls(lsKey||key,val)}
function checkUiOptOff(){if(S.uiOpt==='on'){S.uiOpt='off';ls('uiopt','off');updatePerf()}}
function applyLang(l,snd){apply('lang',['fr','en','es'].includes(l)?l:defs.lang,'lang',snd);document.documentElement.lang=S.lang;$$('[data-language-value]').forEach(b=>b.classList.toggle('active',b.dataset.languageValue===S.lang));applyTranslations()}
function updateThemedLogos(){const isDark=S.theme==='dark';const mainLogo=$('main-logo');if(mainLogo){if(S.aiLogo){mainLogo.src=S.aiLogo}else{const isCowork=activeTab==='coworking';if(isCowork){mainLogo.src=isDark?(mainLogo.dataset.pixelDark||mainLogo.dataset.dark):(mainLogo.dataset.pixelLight||mainLogo.dataset.light)}else{mainLogo.src=isDark?mainLogo.dataset.dark:mainLogo.dataset.light}}}const goatLogo=$('goatistique-logo');if(goatLogo)goatLogo.src=isDark?goatLogo.dataset.dark:goatLogo.dataset.light;const sbMark=document.getElementById('sidebar-brand-mark');const sbMarkImg=document.getElementById('sidebar-brand-mark-img');if(sbMarkImg&&mainLogo){let src='';if(S.aiLogo){src=S.aiLogo}else{src=isDark?(mainLogo.dataset.dark||mainLogo.getAttribute('src')||''):(mainLogo.dataset.light||mainLogo.getAttribute('src')||'')}sbMarkImg.setAttribute('src',src||'');if(sbMark)sbMark.classList.toggle('has-logo',!!src)}updateSidebarProfile()}
function applyTheme(v,snd){if(S.privateChat)return;apply('theme',v==='dark'?'dark':'light','theme',snd);document.body.dataset.theme=S.theme;$$('[data-theme-value]').forEach(b=>b.classList.toggle('active',b.dataset.themeValue===S.theme));updateThemedLogos()}
function applyEffects(v,snd){apply('effects',v==='off'?'off':'on','effects',snd);document.body.dataset.effects=S.effects;updatePerf()}
function applyTextSize(v,snd){apply('textSize',v==='large'?'large':'default','textsize',snd);document.body.dataset.textsize=S.textSize;$$('[data-textsize-value]').forEach(b=>b.classList.toggle('active',b.dataset.textsizeValue===S.textSize))}
function normalizeUIScale(v){const n=parseInt(v,10)||100;return Math.max(70,Math.min(130,n))}
function updateUIScaleUI(){S.uiScale=normalizeUIScale(S.uiScale);if(uiScaleValue)uiScaleValue.textContent=S.uiScale+'%';const scale=S.uiScale/100;document.documentElement.style.setProperty('--ui-scale-factor',String(scale));document.documentElement.style.fontSize='';document.body.style.zoom=String(scale);document.body.style.transformOrigin='top center';window.requestAnimationFrame(()=>window.dispatchEvent(new Event('resize')))}
function applyUIScale(v,snd){S.uiScale=normalizeUIScale(v);ls('ui-scale',String(S.uiScale));if(snd)playClick();updateUIScaleUI();window.dispatchEvent(new Event('resize'))}
function normalizeAccent(v){return['blue','red','green','yellow','pink','purple'].includes(v)?v:'blue'}
function applyAccent(v,snd){S.accent=normalizeAccent(v);ls('accent',S.accent);if(snd)playClick();document.body.dataset.accent=S.accent;$$('[data-accent-value]').forEach(b=>b.classList.toggle('active',b.dataset.accentValue===S.accent));updateThemedLogos();updateWallpaperPreviews()}
function normalizeWallpaperVolume(v){const n=parseInt(v,10);return Number.isFinite(n)?Math.max(0,Math.min(100,n)):35}
function wallpaperStateFor(target){return target==='coworking'?{type:S.wallpaperCoworkingType,src:S.wallpaperCoworkingSrc,volume:normalizeWallpaperVolume(S.wallpaperCoworkingVolume)}:{type:S.wallpaperNormalType,src:S.wallpaperNormalSrc,volume:normalizeWallpaperVolume(S.wallpaperNormalVolume)}}
function setWallpaperVolume(target,volume){const safeVolume=normalizeWallpaperVolume(volume);if(target==='coworking'){S.wallpaperCoworkingVolume=safeVolume;ls('wallpaper-coworking-volume',String(safeVolume))}else{S.wallpaperNormalVolume=safeVolume;ls('wallpaper-normal-volume',String(safeVolume))}if(activeTab===target){wallpaperVideo.volume=safeVolume/100;wallpaperVideo.muted=safeVolume<=0}if(wallpaperVolumeValue)wallpaperVolumeValue.textContent=safeVolume+'%'}
function setWallpaperState(target,type,src){const safeType=(type==='image'||type==='video')?type:'none';const safeSrc=src||'';if(target==='coworking'){S.wallpaperCoworkingType=safeType;S.wallpaperCoworkingSrc=safeSrc;ls('wallpaper-coworking-type',safeType);ls('wallpaper-coworking-src',safeSrc)}else{S.wallpaperNormalType=safeType;S.wallpaperNormalSrc=safeSrc;ls('wallpaper-normal-type',safeType);ls('wallpaper-normal-src',safeSrc)}applyWallpaper();updateWallpaperPreviews()}
function tryPlayWallpaperVideo(){if(!wallpaperVideo||!wallpaperVideo.classList.contains('show'))return;const p=wallpaperVideo.play();if(p&&typeof p.catch==='function')p.catch(()=>{})}
function applyWallpaper(){const activeTarget=activeTab==='coworking'?'coworking':'normal';const data=wallpaperStateFor(activeTarget);const has=data.type!=='none'&&!!data.src;document.body.dataset.wallpaperActive=has?'on':'off';document.body.dataset.cwWallpaper=(S.wallpaperCoworkingType!=='none'&&S.wallpaperCoworkingSrc)?'on':'off';wallpaperImage.classList.remove('show');wallpaperVideo.classList.remove('show');wallpaperImage.removeAttribute('src');wallpaperVideo.pause();wallpaperVideo.removeAttribute('src');wallpaperVideo.load();if(!has)return;if(data.type==='image'){wallpaperImage.src=data.src;wallpaperImage.classList.add('show');return}wallpaperVideo.preload='auto';wallpaperVideo.src=data.src;wallpaperVideo.classList.add('show');wallpaperVideo.loop=true;wallpaperVideo.playsInline=true;wallpaperVideo.volume=data.volume/100;wallpaperVideo.muted=data.volume<=0;const maxW=S.videoQuality==='4k'?3840:1920;wallpaperVideo.style.maxWidth=maxW+'px';wallpaperVideo.style.maxHeight=(maxW===3840?2160:1080)+'px';tryPlayWallpaperVideo()}
function renderWallpaperPreviewBox(box,data){if(!box)return;const label=box.querySelector('.label');box.innerHTML='';if(data.type==='image'&&data.src){const img=document.createElement('img');img.src=data.src;img.alt='';box.appendChild(img)}else if(data.type==='video'&&data.src){const vid=document.createElement('video');vid.src=data.src;vid.muted=true;vid.loop=true;vid.autoplay=true;vid.playsInline=true;vid.addEventListener('canplay',()=>{vid.play().catch(()=>{})},{once:true});box.appendChild(vid)}if(label)box.appendChild(label);else{const span=document.createElement('span');span.className='label';span.textContent=t('appearance_preview');box.appendChild(span)}}
function updateWallpaperPreviews(){renderWallpaperPreviewBox(normalWallpaperPreview,wallpaperStateFor('normal'));renderWallpaperPreviewBox(coworkingWallpaperPreview,wallpaperStateFor('coworking'));renderWallpaperPreviewBox(wallpaperModalPreview,wallpaperStateFor(wallpaperTarget))}
function openWallpaperModal(target){wallpaperTarget=target==='coworking'?'coworking':'normal';wallpaperModalTitle.textContent=t('appearance_modal_title');wallpaperModalTarget.textContent=wallpaperTarget==='coworking'?t('appearance_wallpaper_coworking'):t('appearance_wallpaper_normal');const state=wallpaperStateFor(wallpaperTarget);if(wallpaperVolumeInput)wallpaperVolumeInput.value=String(state.volume);if(wallpaperVolumeValue)wallpaperVolumeValue.textContent=state.volume+'%';updateWallpaperPreviews();wallpaperBackdrop.classList.add('open')}
function closeWallpaperModal(){wallpaperBackdrop.classList.remove('open');wallpaperFileInput.value='';wallpaperVideoFileInput.value=''}
async function handleWallpaperImage(file){if(!file||!file.type.startsWith('image/'))return;try{const dataUrl=await readFileAsDataURL(file);const moderation=await apiModerateProfileImage(file.name||'wallpaper',dataUrl);if(!moderation.safe){alert(moderation.reason||"Cette image ne respecte pas nos règles d'utilisation.");return}setWallpaperState(wallpaperTarget,'image',dataUrl);updateWallpaperPreviews()}catch(err){alert("Impossible de vérifier l'image. Veuillez réessayer.")}}
async function handleWallpaperVideo(file){if(!file||!file.type.startsWith('video/'))return;const reader=new FileReader();reader.onload=()=>{setWallpaperState(wallpaperTarget,'video',String(reader.result||''));setWallpaperVolume(wallpaperTarget,wallpaperVolumeInput?wallpaperVolumeInput.value:35);updateWallpaperPreviews();tryPlayWallpaperVideo()};reader.readAsDataURL(file)}

function applyOptResp(v,snd){apply('optResp',v==='on'?'on':'off','optresp',snd);enforceMode();renderModes();updateModeUI();updatePerf()}
function applyCalcTarget(v,snd,showNotif){const next=['cpu','gpu','default'].includes(v)?v:defs.calcTarget;apply('calcTarget',next,'calc-target',snd);updateCalcTargetUI();if(showNotif){const key='calc_target_notify_'+next;calcTargetNotification.textContent=t(key);calcTargetNotification.hidden=false;setTimeout(()=>{calcTargetNotification.hidden=true},6000)}}
const calcTargetOptions=[{id:'cpu',icon:'🖥️',labelKey:'calc_target_cpu'},{id:'gpu',icon:'🎮',labelKey:'calc_target_gpu'},{id:'default',icon:'⚡',labelKey:'calc_target_default'}];
function updateCalcTargetUI(){const current=calcTargetOptions.find(o=>o.id===S.calcTarget)||calcTargetOptions[2];calcTargetLabel.textContent=t(current.labelKey);calcTargetIcon.textContent=current.icon;renderCalcTargetMenu()}
function renderCalcTargetMenu(){calcTargetMenu.innerHTML=calcTargetOptions.map(o=>'<button type="button" class="dropdown-menu-item'+(o.id===S.calcTarget?' selected':'')+'" data-ct-value="'+esc(o.id)+'" role="menuitemradio"><span class="dm-icon">'+o.icon+'</span><span class="dm-label">'+esc(t(o.labelKey))+'</span><span class="dm-check">✓</span></button>').join('')}
// Portail vers document.body : .settings-modal est en transform → position:fixed
// est interprétée par rapport à la modale (et clippée par overflow:hidden).
// On déplace donc temporairement le menu sous <body> pour qu'il s'ancre au viewport.
let _calcTargetParent=null,_calcTargetNext=null;
function openCalcTargetMenu(){
  if(!calcTargetMenu)return;
  if(calcTargetMenu.parentNode!==document.body){
    _calcTargetParent=calcTargetMenu.parentNode;
    _calcTargetNext=calcTargetMenu.nextSibling;
    document.body.appendChild(calcTargetMenu);
  }
  const rect=calcTargetTrigger.getBoundingClientRect();
  const menuW=Math.max(280,rect.width);
  const left=Math.min(window.innerWidth-menuW-12,Math.max(12,rect.left));
  // Si pas assez de place sous le bouton, on bascule au-dessus.
  const spaceBelow=window.innerHeight-rect.bottom;
  const above=spaceBelow<260&&rect.top>260;
  calcTargetMenu.style.top=(above?(rect.top-8-Math.min(260,calcTargetMenu.scrollHeight||260)):(rect.bottom+8))+'px';
  calcTargetMenu.style.left=left+'px';
  calcTargetMenu.style.minWidth=menuW+'px';
  calcTargetMenu.classList.add('open');
  calcTargetTrigger.setAttribute('aria-expanded','true');
}
function closeCalcTargetMenu(){
  if(!calcTargetMenu)return;
  calcTargetMenu.classList.remove('open');
  calcTargetTrigger.setAttribute('aria-expanded','false');
  // Restaure la position DOM d'origine (utile si l'on rouvre la modale Settings).
  if(_calcTargetParent&&calcTargetMenu.parentNode===document.body){
    _calcTargetParent.insertBefore(calcTargetMenu,_calcTargetNext||null);
    _calcTargetParent=null;_calcTargetNext=null;
  }
}
// Ferme le menu si l'on clique à l'extérieur (le menu étant maintenant détaché).
document.addEventListener('click',e=>{
  if(!calcTargetMenu||!calcTargetMenu.classList.contains('open'))return;
  if(calcTargetMenu.contains(e.target)||(calcTargetTrigger&&calcTargetTrigger.contains(e.target)))return;
  closeCalcTargetMenu();
});
// Repositionne en cas de scroll/resize tant qu'il est ouvert.
window.addEventListener('resize',()=>{if(calcTargetMenu&&calcTargetMenu.classList.contains('open'))openCalcTargetMenu()});
window.addEventListener('scroll',()=>{if(calcTargetMenu&&calcTargetMenu.classList.contains('open'))openCalcTargetMenu()},true);
function applyUiOpt(v,snd){apply('uiOpt',v==='on'?'on':'off','uiopt',snd);if(S.uiOpt==='on'){applyEffects('off',false);applyKbSound('off',false);applyClickSound('off',false);applyAiSound('off',false)}updatePerf()}
function applyKbSound(v,snd){apply('kbSound',v==='on'?'on':'off','kb-sound',snd);$$('[data-kb-sound]').forEach(b=>b.classList.toggle('active',b.dataset.kbSound===S.kbSound));updateSndVis();if(v==='on')checkUiOptOff()}
function applyKbStyle(v,snd){apply('kbStyle',['bulle','aurela','verdrock','feryn'].includes(v)?v:'bulle','kb-style',snd);$$('[data-kb-style]').forEach(b=>b.classList.toggle('active',b.dataset.kbStyle===S.kbStyle))}
function applyClickSound(v,snd){apply('clickSound',v==='on'?'on':'off','click-sound',snd);$$('[data-click-sound]').forEach(b=>b.classList.toggle('active',b.dataset.clickSound===S.clickSound));updateSndVis();if(v==='on')checkUiOptOff()}
function applyClickStyle(v,snd){apply('clickStyle',['bulle','nebrise'].includes(v)?v:'bulle','click-style',snd);$$('[data-click-style]').forEach(b=>b.classList.toggle('active',b.dataset.clickStyle===S.clickStyle))}
function applyAiSound(v,snd){apply('aiSound',v==='on'?'on':'off','ai-sound',snd);$$('[data-ai-sound]').forEach(b=>b.classList.toggle('active',b.dataset.aiSound===S.aiSound));if(v==='on')checkUiOptOff()}
function updateSndVis(){const kr=$('keyboard-style-row'),cr=$('click-style-row');if(kr)kr.hidden=S.kbSound!=='on';if(cr)cr.hidden=S.clickSound!=='on'}
function updatePerf(){$('effects-state').textContent=S.effects==='off'?t('state_on'):t('state_off');$('responses-state').textContent=S.optResp==='on'?t('state_on'):t('state_off');const uiOptState=$('uiopt-state');if(uiOptState)uiOptState.textContent=S.uiOpt==='on'?t('state_on'):t('state_off');updateCalcTargetUI()}
function getCoworkingContent(){return coworkingContent[S.lang]||coworkingContent[defs.lang]||coworkingContent.fr}
function pickRandom(arr){return arr[Math.floor(Math.random()*arr.length)]}
function refreshWelcomeContent(){
  if(messages.length)return;
  if(S.privateChat){
    welcomeEl.textContent=t('private_chat_welcome');
    welcomeDesc.textContent=t('private_chat_welcome_desc');
    return;
  }
  if(activeTab==='coworking'){
    const cfg=getCoworkingContent();
    welcomeEl.textContent=pickRandom(cfg.messages);
    welcomeDesc.textContent=cfg.desc||'';
    return;
  }
  const pool=WP[S.lang]||WP[defs.lang]||['...'];
  welcomeEl.textContent=pickRandom(pool);
  welcomeDesc.textContent='';
}
function updateTabUI(){
  document.body.dataset.activeTab=activeTab;
  if(tabChat)tabChat.classList.toggle('active',activeTab==='chat');
  if(tabCoworking)tabCoworking.classList.toggle('active',activeTab==='coworking');
  if(modePanel)modePanel.hidden=activeTab==='coworking';
  if(modeAnn)modeAnn.hidden=activeTab==='coworking';
  ta.placeholder=activeTab==='coworking'?getCoworkingContent().placeholder:t('placeholder');
  statusEl.textContent=activeTab==='coworking'?getCoworkingContent().status:(ST[S.lang]||ST[defs.lang]);
  applyWallpaper();
  updateThemedLogos();
  refreshWelcomeContent();
}
async function switchTabWithReset(targetTab){
  if(activeTab===targetTab)return;
  statusEl.textContent='...';
  try{const p=await apiNewChat();messages=p.messages;messagesMeta=p.metas||[];openSpecificityPanels.clear()}catch(e){statusEl.textContent=e.message;return}
  activeTab=targetTab==='coworking'?'coworking':'chat';
  closeModelDD();closeMM();closeSM();
  refreshWelcomeContent();updateTabUI();renderMessages();ta.value='';autoResize();statusEl.textContent=activeTab==='coworking'?getCoworkingContent().status:(ST[S.lang]||ST[defs.lang]);
}
function setActiveTab(tab,refresh){
  activeTab=tab==='coworking'?'coworking':'chat';
  closeModelDD();
  closeMM();
  closeSM();
  if(refresh!==false)refreshWelcomeContent();
  updateTabUI();
}
function applyTranslations(){$$('[data-i18n]').forEach(n=>n.textContent=t(n.dataset.i18n));$$('[data-placeholder-key]').forEach(n=>n.placeholder=t(n.dataset.placeholderKey));$('settings-button-label').textContent=t('settings_label');$('newchat-button-label').textContent=t('new_chat');const _sl=$('sidebar-new-chat-label');if(_sl)_sl.textContent=t('new_chat');updateSidebarProfile();$('settings-version-value').textContent=appVersion;brandText.textContent=appTitle();plusAddSheet.textContent='📄 '+t('add_sheet');const mcb=$('migrate-copy-btn');if(mcb)mcb.textContent=t('migrate_copy');updatePrivateChatLabels();updateCharCounter();updateContraction();updatePerf();updateUIScaleUI();updateModeUI();renderModes();updateStyleUI();renderStyles();updateGadgetUI();renderGadgets();renderModelDD();if(typeof renderCustomModelsMenu==='function')renderCustomModelsMenu();if(typeof updateCustomModelTriggerUI==='function')updateCustomModelTriggerUI();updateTabUI();updateProfileUI();updateWallpaperPreviews();toggleProfileEditor(!profileEditor.hidden);renderMessages()}
function persistPerso(){ls('firstname',$('user-firstname').value);ls('lastname',$('user-lastname').value);ls('tone',$('user-tone').value);ls('info',$('user-info').value);updateSidebarProfile()}
function loadPerso(){$('user-firstname').value=ls('firstname')||'';$('user-lastname').value=ls('lastname')||'';$('user-tone').value=ls('tone')||'';$('user-info').value=ls('info')||''}
function profileGet(key,def=''){const v=ls('profile-'+key);return v===null||v===undefined||v===''?def:v}
function profileSet(key,val){ls('profile-'+key,val||'');return val||''}
function getChatCount(){const raw=ls('stats-chat-count');if(raw===null){const seeded=messages.filter(m=>Array.isArray(m)&&m[0]==='Vous').length;ls('stats-chat-count',String(seeded));return seeded}const n=parseInt(raw,10);return Number.isFinite(n)&&n>=0?n:0}
function setChatCount(n){ls('stats-chat-count',String(Math.max(0,Math.floor(n))));updateProfileUI()}
function incrementChatCount(){setChatCount(getChatCount()+1)}
function computeGoatScore(count){return Math.floor((count*10)+(Math.sqrt(Math.max(0,count))*25))}
function getProfileData(){return{firstname:profileGet('firstname'),lastname:profileGet('lastname'),bio:profileGet('bio'),avatar:profileGet('avatar'),banner:profileGet('banner'),instagram:profileGet('instagram'),tiktok:profileGet('tiktok'),youtube:profileGet('youtube'),github:profileGet('github'),bluesky:profileGet('bluesky'),showMessageAvatar:profileGet('showMessageAvatar','off')}}
function getProfileFullName(data){const full=[data.firstname,data.lastname].filter(Boolean).join(' ').trim();return full||t('profile_no_name')}
function normalizeSocialUrl(platform,value){const raw=String(value||'').trim();if(!raw)return'';if(/^https?:\/\//i.test(raw))return raw;const clean=raw.replace(/^@+/,'');const bases={instagram:'https://www.instagram.com/',tiktok:'https://www.tiktok.com/@',youtube:'https://www.youtube.com/@',github:'https://github.com/',bluesky:'https://bsky.app/profile/'};return(bases[platform]||'https://')+clean}
function socialEntries(data){return[]}
function svgDataUri(svg){return 'data:image/svg+xml;charset=UTF-8,'+encodeURIComponent(svg)}
function makeGoatAvatarPreset(id,title,c1,c2,accent){return{id,label:title,src:svgDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512"><defs><linearGradient id="${id}-bg" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stop-color="${c1}"/><stop offset="100%" stop-color="${c2}"/></linearGradient></defs><rect width="512" height="512" rx="120" fill="url(#${id}-bg)"/><circle cx="256" cy="208" r="124" fill="rgba(255,255,255,.15)"/><path d="M168 352c28-36 59-54 88-54s60 18 88 54" fill="none" stroke="rgba(255,255,255,.92)" stroke-width="28" stroke-linecap="round"/><text x="256" y="246" text-anchor="middle" font-family="JetBrains Mono, Arial" font-size="132" font-weight="800" fill="${accent}">G</text><text x="256" y="424" text-anchor="middle" font-family="JetBrains Mono, Arial" font-size="52" font-weight="700" fill="rgba(255,255,255,.92)">GOAT</text><!-- goat-preset --></svg>`)} }
function makeGoatBannerPreset(id,title,c1,c2,accent){return{id,label:title,src:svgDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 500"><defs><linearGradient id="${id}-bg" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" stop-color="${c1}"/><stop offset="100%" stop-color="${c2}"/></linearGradient></defs><rect width="1600" height="500" rx="42" fill="url(#${id}-bg)"/><circle cx="1250" cy="120" r="190" fill="rgba(255,255,255,.08)"/><circle cx="1340" cy="340" r="220" fill="rgba(255,255,255,.06)"/><path d="M0 360c170-50 280-66 430-36s260 56 410 10 320-84 760 24v142H0z" fill="rgba(10,15,35,.18)"/><text x="120" y="188" font-family="JetBrains Mono, Arial" font-size="150" font-weight="800" fill="${accent}">LE GOAT</text><text x="124" y="260" font-family="JetBrains Mono, Arial" font-size="46" font-weight="600" fill="rgba(255,255,255,.88)">Designed and coded in France</text><path d="M1048 214c40-40 74-60 102-60 30 0 60 20 100 60" fill="none" stroke="rgba(255,255,255,.92)" stroke-width="22" stroke-linecap="round"/><circle cx="1084" cy="170" r="18" fill="rgba(255,255,255,.92)"/><circle cx="1164" cy="170" r="18" fill="rgba(255,255,255,.92)"/><!-- goat-banner-preset --></svg>`)} }
let profilePresetLibrary=null;
function getProfilePresetLibrary(){
  if(profilePresetLibrary)return profilePresetLibrary;
  const logo=$('main-logo')?$('main-logo').getAttribute('src'):'';
  // Utilise les images locales si disponibles, sinon fallback sur les presets SVG
  const localAvatars=(localProfilePresets&&localProfilePresets.avatars)||[];
  const localBanners=(localProfilePresets&&localProfilePresets.banners)||[];
  const fallbackAvatars=[
    logo?{id:'goat-logo',label:'Logo Le Goat',src:logo}:makeGoatAvatarPreset('goat-logo','Logo Le Goat','#f8fafc','#e5e7eb','#111827'),
    makeGoatAvatarPreset('goat-midnight','Goat Midnight','#0f172a','#2563eb','#ffffff'),
    makeGoatAvatarPreset('goat-ultra','Goat Ultra','#0b1020','#7c3aed','#e0f2fe'),
    makeGoatAvatarPreset('goat-frost','Goat Frost','#eff6ff','#93c5fd','#1d4ed8')
  ];
  const fallbackBanners=[
    makeGoatBannerPreset('goat-banner-core','Goat Core','#111827','#2563eb','#ffffff'),
    makeGoatBannerPreset('goat-banner-neon','Goat Neon','#0f172a','#7c3aed','#f8fafc'),
    makeGoatBannerPreset('goat-banner-light','Goat Horizon','#1e3a8a','#60a5fa','#ffffff')
  ];
  profilePresetLibrary={
    avatar: localAvatars.length>0 ? localAvatars : fallbackAvatars,
    banner: localBanners.length>0 ? localBanners : fallbackBanners
  };
  return profilePresetLibrary;
}
function isLogoStyleAvatarSrc(src){const logo=$('main-logo')?$('main-logo').getAttribute('src'):'';return!!src&&(src===logo||src.indexOf('goat-preset')!==-1)}
function applyAvatarFitMode(el,src){if(!el)return;el.classList.toggle('is-logo',isLogoStyleAvatarSrc(src))}
function setUploadPreview(box,src,fallbackLabel,kind){if(!box)return;box.innerHTML=src?'<img class="'+((kind==='avatar'&&isLogoStyleAvatarSrc(src))?'is-logo':'')+'" src="'+esc(src)+'" alt="preview">':'<span>'+esc(fallbackLabel)+'</span>'}
function toggleProfileEditor(force){const open=typeof force==='boolean'?force:profileEditor.hidden;profileEditor.hidden=!open;profileEditToggle.textContent=open?t('profile_close_edit'):t('profile_edit')}
function loadProfileForm(){const data=getProfileData();profileFirstnameInput.value=data.firstname;profileLastnameInput.value=data.lastname;profileBioInput.value=data.bio;profileInstagramInput.value=data.instagram;profileTikTokInput.value=data.tiktok;profileYouTubeInput.value=data.youtube;profileGitHubInput.value=data.github;profileBlueskyInput.value=data.bluesky;if(profileAvatarMessagesToggle)profileAvatarMessagesToggle.checked=data.showMessageAvatar==='on';setUploadPreview(profileAvatarUploadPreview,data.avatar,t('profile_avatar'),'avatar');setUploadPreview(profileBannerUploadPreview,data.banner,t('profile_banner'),'banner');updateProfileUI()}
function persistProfileForm(){profileSet('firstname',profileFirstnameInput.value.trim());profileSet('lastname',profileLastnameInput.value.trim());profileSet('bio',profileBioInput.value.trim());profileSet('instagram',profileInstagramInput.value.trim());profileSet('tiktok',profileTikTokInput.value.trim());profileSet('youtube',profileYouTubeInput.value.trim());profileSet('github',profileGitHubInput.value.trim());profileSet('bluesky',profileBlueskyInput.value.trim());updateProfileUI()}
function updateProfileUI(){if(!profileNamePreview)return;const data=getProfileData();const count=getChatCount();const score=computeGoatScore(count);const fullName=getProfileFullName(data);const fallbackAvatar=$('main-logo')?$('main-logo').getAttribute('src'):'';const avatarSrc=data.avatar||fallbackAvatar;profileNamePreview.textContent=fullName;profileDescriptionPreview.textContent=data.bio||t('profile_no_description');profileDescriptionPreview.classList.toggle('empty',!data.bio);if(profileChatCount)profileChatCount.textContent=count.toLocaleString('fr-FR');if(profileGoatScore)profileGoatScore.textContent=score.toLocaleString('fr-FR');profileAvatarPreview.src=avatarSrc;applyAvatarFitMode(profileAvatarPreview,avatarSrc);profileBannerPreview.style.backgroundImage=data.banner?'url("'+String(data.banner).replace(/"/g,'\"')+'")':'';if(settingsProfileTabAvatar){settingsProfileTabAvatar.src=avatarSrc;applyAvatarFitMode(settingsProfileTabAvatar,avatarSrc)}if(settingsProfileTabName)settingsProfileTabName.textContent=fullName;setUploadPreview(profileAvatarUploadPreview,data.avatar,t('profile_avatar'),'avatar');setUploadPreview(profileBannerUploadPreview,data.banner,t('profile_banner'),'banner');if(profileAvatarMessagesToggle)profileAvatarMessagesToggle.checked=data.showMessageAvatar==='on';const socials=socialEntries(data).filter(item=>item.value.trim());if(!socials.length){profileSocialsPreview.innerHTML='<span class="profile-social-empty">'+esc(t('profile_share_hint'))+'</span>'}else{profileSocialsPreview.innerHTML=socials.map(item=>'<a class="profile-social-link" href="'+esc(normalizeSocialUrl(item.id,item.value))+'" target="_blank" rel="noreferrer noopener">'+esc(item.label)+'</a>').join('')}updateSidebarProfile();}
function closeProfilePicker(){if(!profilePickerBackdrop)return;profilePickerBackdrop.classList.remove('open')}
function renderProfilePicker(){if(!profilePickerGrid)return;const library=getProfilePresetLibrary()[profilePickerMode]||[];if(profilePickerTitle)profilePickerTitle.textContent=profilePickerMode==='banner'?t('profile_picker_title_banner'):t('profile_picker_title');if(profilePickerSectionTitle)profilePickerSectionTitle.textContent=t('profile_picker_category_goat');profilePickerGrid.innerHTML='';profilePickerGrid.classList.toggle('banner-mode',profilePickerMode==='banner');library.forEach(item=>{const btn=document.createElement('button');btn.type='button';btn.className='profile-picker-card';const thumb=document.createElement('div');thumb.className='profile-picker-thumb'+(profilePickerMode==='banner'?' banner':'');const img=document.createElement('img');img.src=item.src;if(profilePickerMode==='avatar')applyAvatarFitMode(img,item.src);thumb.appendChild(img);const label=document.createElement('span');label.className='profile-picker-card-label';label.textContent=item.label;btn.appendChild(thumb);btn.appendChild(label);btn.addEventListener('click',()=>{playClick();profileSet(profilePickerMode,item.src);loadProfileForm();closeProfilePicker();renderMessages()});profilePickerGrid.appendChild(btn)});const importBtn=document.createElement('button');importBtn.type='button';importBtn.className='profile-picker-card import';const importThumb=document.createElement('div');importThumb.className='profile-picker-thumb'+(profilePickerMode==='banner'?' banner':'');importThumb.innerHTML='<div>+</div><span>'+esc(profilePickerMode==='banner'?t('profile_picker_import_banner'):t('profile_picker_import_avatar'))+'</span>';const importLabel=document.createElement('span');importLabel.className='profile-picker-card-label';importLabel.textContent=profilePickerMode==='banner'?t('profile_choose_banner'):t('profile_choose_avatar');importBtn.appendChild(importThumb);importBtn.appendChild(importLabel);importBtn.addEventListener('click',()=>{playClick();closeProfilePicker();(profilePickerMode==='banner'?profileBannerFile:profileAvatarFile).click()});profilePickerGrid.appendChild(importBtn)}
function openProfilePicker(mode){profilePickerMode=mode||'avatar';renderProfilePicker();if(profilePickerBackdrop)profilePickerBackdrop.classList.add('open')}
function readFileAsDataURL(file){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result||''));reader.onerror=()=>reject(reader.error||new Error('read error'));reader.readAsDataURL(file)})}
async function apiModerateProfileImage(filename,dataUrl){const r=await fetch('/api/moderate_profile_image',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filename,dataUrl})});const p=await r.json();if(!r.ok||!p.ok)throw new Error(p.error||'Filtre image indisponible');return p}
function closeCropper(){cropState=null;cropBackdrop.classList.remove('open');cropCanvas.classList.remove('dragging')}
function cropAspect(mode){return mode==='banner'?3.2:1}
function resizeCropCanvas(){if(!cropState)return;const rect=cropCanvas.getBoundingClientRect();const ratio=window.devicePixelRatio||1;cropCanvas.width=Math.max(1,Math.round(rect.width*ratio));cropCanvas.height=Math.max(1,Math.round(rect.height*ratio));cropState.pixelRatio=ratio;cropState.canvasW=rect.width;cropState.canvasH=rect.height}
function initCropState(){if(!cropState||!cropState.img)return;resizeCropCanvas();const aspect=cropAspect(cropState.mode);let frameW=Math.min(cropState.canvasW*(cropState.mode==='banner'?0.82:0.58),cropState.canvasW-48);let frameH=frameW/aspect;if(frameH>cropState.canvasH*0.76){frameH=cropState.canvasH*0.76;frameW=frameH*aspect}cropState.frame={x:(cropState.canvasW-frameW)/2,y:(cropState.canvasH-frameH)/2,w:frameW,h:frameH};cropState.baseScale=Math.max(frameW/cropState.img.width,frameH/cropState.img.height);cropState.zoom=1;cropState.offsetX=0;cropState.offsetY=0;if(cropZoom)cropZoom.value='100';clampCropOffsets();renderCropper()}
function clampCropOffsets(){if(!cropState||!cropState.frame)return;const drawW=cropState.img.width*cropState.baseScale*cropState.zoom;const drawH=cropState.img.height*cropState.baseScale*cropState.zoom;const f=cropState.frame;const minOffsetX=f.x+f.w-drawW/2-cropState.canvasW/2;const maxOffsetX=f.x+drawW/2-cropState.canvasW/2;const minOffsetY=f.y+f.h-drawH/2-cropState.canvasH/2;const maxOffsetY=f.y+drawH/2-cropState.canvasH/2;cropState.offsetX=Math.min(maxOffsetX,Math.max(minOffsetX,cropState.offsetX));cropState.offsetY=Math.min(maxOffsetY,Math.max(minOffsetY,cropState.offsetY))}
function renderCropper(){if(!cropState)return;resizeCropCanvas();const ctx=cropCanvas.getContext('2d');const ratio=cropState.pixelRatio||1;ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,cropState.canvasW,cropState.canvasH);const drawW=cropState.img.width*cropState.baseScale*cropState.zoom;const drawH=cropState.img.height*cropState.baseScale*cropState.zoom;const centerX=cropState.canvasW/2+cropState.offsetX;const centerY=cropState.canvasH/2+cropState.offsetY;const dx=centerX-drawW/2;const dy=centerY-drawH/2;cropState.draw={dx,dy,dw:drawW,dh:drawH};ctx.drawImage(cropState.img,dx,dy,drawW,drawH);ctx.fillStyle='rgba(3,8,20,.56)';ctx.fillRect(0,0,cropState.canvasW,cropState.canvasH);const f=cropState.frame;ctx.save();ctx.beginPath();ctx.rect(f.x,f.y,f.w,f.h);ctx.clip();ctx.clearRect(f.x,f.y,f.w,f.h);ctx.drawImage(cropState.img,dx,dy,drawW,drawH);ctx.restore();ctx.strokeStyle='#ffffff';ctx.lineWidth=2;ctx.strokeRect(f.x,f.y,f.w,f.h);ctx.strokeStyle='rgba(255,255,255,.35)';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(f.x+f.w/3,f.y);ctx.lineTo(f.x+f.w/3,f.y+f.h);ctx.moveTo(f.x+2*f.w/3,f.y);ctx.lineTo(f.x+2*f.w/3,f.y+f.h);ctx.moveTo(f.x,f.y+f.h/3);ctx.lineTo(f.x+f.w,f.y+f.h/3);ctx.moveTo(f.x,f.y+2*f.h/3);ctx.lineTo(f.x+f.w,f.y+2*f.h/3);ctx.stroke()}
function openCropper(dataUrl,mode){cropState={mode,img:new Image(),zoom:1,offsetX:0,offsetY:0,pointerId:null};cropTitle.textContent=mode==='banner'?'Recadrer la bannière':'Recadrer la photo de profil';cropBackdrop.classList.add('open');cropState.img.onload=()=>initCropState();cropState.img.src=dataUrl}
function applyCrop(){if(!cropState||!cropState.draw)return;const f=cropState.frame;const d=cropState.draw;const scale=cropState.baseScale*cropState.zoom;const sx=Math.max(0,(f.x-d.dx)/scale);const sy=Math.max(0,(f.y-d.dy)/scale);const sw=Math.min(cropState.img.width-sx,f.w/scale);const sh=Math.min(cropState.img.height-sy,f.h/scale);const out=document.createElement('canvas');out.width=cropState.mode==='banner'?1600:768;out.height=cropState.mode==='banner'?500:768;const octx=out.getContext('2d');octx.drawImage(cropState.img,sx,sy,sw,sh,0,0,out.width,out.height);profileSet(cropState.mode,out.toDataURL('image/png'));closeCropper();loadProfileForm();renderMessages()}
async function handleProfileImage(file,key){if(!file)return;try{const dataUrl=await readFileAsDataURL(file);const moderation=await apiModerateProfileImage(file.name||'',dataUrl);if(!moderation.safe){alert(moderation.reason||"Désolé, nous ne pouvons pas mettre votre photo de profil en raison de nos règles d'utilisation.");return}openCropper(dataUrl,key)}catch(err){alert("Impossible de vérifier l'image. Veuillez réessayer.")}}
function formatProfileText(includeScore){const data=getProfileData();const count=getChatCount();const lines=[getProfileFullName(data)];if(data.bio)lines.push(data.bio);lines.push(t('profile_chats_sent')+' : '+count);if(includeScore)lines.push(t('profile_goat_score')+' : '+computeGoatScore(count));socialEntries(data).forEach(item=>{if(item.value.trim())lines.push(item.label+' : '+normalizeSocialUrl(item.id,item.value))});return lines.filter(Boolean).join('\n')}
function sanitizeFilename(value){return String(value||'profil-goat').normalize('NFD').replace(/[̀-ͯ]/g,'').replace(/[^a-zA-Z0-9_-]+/g,'-').replace(/-+/g,'-').replace(/^-|-$/g,'').toLowerCase()||'profil-goat'}
async function apiExportProfilePdf(includeScore){const payload={includeScore,chatCount:getChatCount(),goatScore:computeGoatScore(getChatCount()),profile:getProfileData()};const r=await fetch('/api/export_profile_pdf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const p=await r.json();if(!r.ok||!p.ok)throw new Error(p.error||'Export PDF impossible');return p}
async function apiProfileScreenshot(){const r=await fetch('/api/profile_screenshot',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});const p=await r.json();if(!r.ok||!p.ok)throw new Error(p.error||'Profile screenshot unavailable');return p}
async function shareProfile(includeScore){playClick();if(includeScore){try{const p=await apiProfileScreenshot();if(p.triggered)return}catch(e){}window.open('https://screenrec.com/fr/','_blank','noopener');return}alert(t('profile_share_dev'))}
async function apiVoiceShortcut(){const r=await fetch('/api/voice_shortcut',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});const p=await r.json();if(!r.ok||!p.ok)throw new Error(p.error||'Voice shortcut unavailable');return p}
async function triggerVoiceInput(){playClick();try{const p=await apiVoiceShortcut();if(p.triggered)return}catch(e){}window.open('https://wisprflow.ai/','_blank','noopener')}
// ── API HTTP — communication avec le backend Python ──────────────
// Toutes les requêtes sont en POST JSON vers localhost.
// Les endpoints sont définis dans GoatRequestHandler (Python).
// ── Construction du contexte « Spécificité » envoyé avec chaque requête ──
// On regroupe ici les méta-données affichées dans le panneau dépliant côté
// frontend : mode, style, modèle (standard ou custom), pièces jointes.
function buildRequestContext(){
  const customActive=(typeof cmHasCustomActive==='function')&&cmHasCustomActive();
  const customName=customActive?(cmGet(S.activeCustomModel)||{}).name||'':'';
  return {
    mode: S.mode||'',
    style: S.wstyle||'',
    model: S.model||'',
    customModelName: customName,
    attachments: (attachments||[]).map(a=>({
      name: a.name||'',
      kind: a.kind||'',
      type: a.type||'',
      size: a.size||0,
    })),
  };
}
async function apiSend(msg,signal){const bio=($('profile-bio-input')||{}).value||'';const tone=($('user-tone')||{}).value||'';const ctx=buildRequestContext();const r=await fetch('/api/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.assign({message:msg,userBio:bio,userTone:tone},ctx)),signal});const p=await r.json();if(!r.ok||!p.ok)throw new Error(p.error||'Erreur');incrementChatCount();return p}
async function apiRegen(signal){const ctx=buildRequestContext();const r=await fetch('/api/regenerate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(ctx),signal});const p=await r.json();if(!r.ok||!p.ok)throw new Error(p.error||'Erreur');return p}
async function apiNewChat(){const r=await fetch('/api/new_chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});const p=await r.json();if(!r.ok||!p.ok)throw new Error(p.error||'Erreur');return p}

// ── Soumission du formulaire (envoi message + gestion erreurs) ────
form.addEventListener('submit',async e=>{e.preventDefault();const v=ta.value.trim();if(!v)return;playSend();statusEl.textContent='...';showStopBtn();abortController=new AbortController();messages.push(['Vous',v],[appTitle(),'…']);messagesMeta.push(null,null);renderMessages();ta.value='';autoResize();updateCharCounter();try{const p=await apiSend(v,abortController.signal);messages=p.messages;messagesMeta=p.metas||[];renderMessages();statusEl.textContent=ST[S.lang]||ST[defs.lang];playAiReply()}catch(err){if(err.name==='AbortError'){if(messages.length&&messages[messages.length-1][1]==='…'){messages.pop();messagesMeta.pop()}renderMessages()}else{if(messages.length&&messages[messages.length-1][0]!=='Vous')messages[messages.length-1]=[appTitle(),'Erreur : '+err.message];renderMessages();statusEl.textContent=err.message}}finally{hideStopBtn();ta.focus()}});
// ── Liaisons événements contrôles UI ─────────────────────────────
modeTrigger.addEventListener('click',()=>{playClick();modeMenu.classList.contains('open')?closeMM():openMM()});
styleTrigger.addEventListener('click',()=>{playClick();styleMenu.classList.contains('open')?closeSM():openSM()});
/* gadgetTrigger.addEventListener('click',()=>{playClick();gadgetMenu.classList.contains('open')?closeGM():openGM()}); // desactive */
$('settings-button').addEventListener('click',openSettings);$('settings-close').addEventListener('click',closeSettings);backdrop.addEventListener('click',closeSettings);
dragH.addEventListener('mousedown',startDrag);document.addEventListener('mousemove',onDrag);document.addEventListener('mouseup',()=>{dragging=false});
$('newchat-button').addEventListener('click',async()=>{playClick();if(!confirm(t('new_chat_confirm')))return;statusEl.textContent='...';try{const p=await apiNewChat();messages=p.messages;messagesMeta=p.metas||[];openSpecificityPanels.clear();refreshWelcomeContent();renderMessages();statusEl.textContent=activeTab==='coworking'?getCoworkingContent().status:(ST[S.lang]||ST[defs.lang]);ta.value='';autoResize();ta.focus()}catch(e){statusEl.textContent=e.message}});
$$('[data-settings-tab]').forEach(t=>t.addEventListener('click',()=>{playClick();showTab(t.dataset.settingsTab||'general')}));
// Paramètres — tous les boutons data-xxx-value sont liés dynamiquement
$$('[data-language-value]').forEach(b=>b.addEventListener('click',()=>applyLang(b.dataset.languageValue)));
$$('[data-theme-value]').forEach(b=>b.addEventListener('click',()=>applyTheme(b.dataset.themeValue)));
$$('[data-textsize-value]').forEach(b=>b.addEventListener('click',()=>applyTextSize(b.dataset.textsizeValue)));
$$('[data-kb-sound]').forEach(b=>b.addEventListener('click',()=>applyKbSound(b.dataset.kbSound)));
$$('[data-kb-style]').forEach(b=>b.addEventListener('click',()=>applyKbStyle(b.dataset.kbStyle)));
$$('[data-click-sound]').forEach(b=>b.addEventListener('click',()=>applyClickSound(b.dataset.clickSound)));
$$('[data-click-style]').forEach(b=>b.addEventListener('click',()=>applyClickStyle(b.dataset.clickStyle)));
$$('[data-ai-sound]').forEach(b=>b.addEventListener('click',()=>applyAiSound(b.dataset.aiSound)));
$$('[data-aifont-value]').forEach(b=>b.addEventListener('click',()=>applyAiFont(b.dataset.aifontValue)));
$$('[data-userfont-value]').forEach(b=>b.addEventListener('click',()=>applyUserFont(b.dataset.userfontValue)));
$$('[data-accent-value]').forEach(b=>b.addEventListener('click',()=>applyAccent(b.dataset.accentValue,true)));
$('change-normal-wallpaper').addEventListener('click',()=>{playClick();openWallpaperModal('normal')});
$('change-coworking-wallpaper').addEventListener('click',()=>{playClick();openWallpaperModal('coworking')});
$('remove-normal-wallpaper').addEventListener('click',()=>{playClick();setWallpaperState('normal','none','')});
$('remove-coworking-wallpaper').addEventListener('click',()=>{playClick();setWallpaperState('coworking','none','')});
wallpaperImportImageBtn.addEventListener('click',()=>{playClick();wallpaperFileInput.click()});
wallpaperImportVideoBtn.addEventListener('click',()=>{playClick();alert(t('appearance_video_import_warning'));wallpaperVideoFileInput.click()});
wallpaperRemoveBtn.addEventListener('click',()=>{playClick();setWallpaperState(wallpaperTarget,'none','');updateWallpaperPreviews()});
wallpaperCloseBtn.addEventListener('click',()=>{playClick();closeWallpaperModal()});
wallpaperBackdrop.addEventListener('click',e=>{if(e.target===wallpaperBackdrop)closeWallpaperModal()});
wallpaperFileInput.addEventListener('change',async()=>{if(wallpaperFileInput.files&&wallpaperFileInput.files[0])await handleWallpaperImage(wallpaperFileInput.files[0]);wallpaperFileInput.value=''})
wallpaperVideoFileInput.addEventListener('change',async()=>{if(wallpaperVideoFileInput.files&&wallpaperVideoFileInput.files[0])await handleWallpaperVideo(wallpaperVideoFileInput.files[0]);wallpaperVideoFileInput.value=''})
if(wallpaperVolumeInput)wallpaperVolumeInput.addEventListener('input',()=>{setWallpaperVolume(wallpaperTarget,wallpaperVolumeInput.value);if(activeTab===wallpaperTarget)tryPlayWallpaperVideo()});
function applyVideoFps(v){S.videoFps=v==='60'?'60':'30';ls('video-fps',S.videoFps);$$('[data-video-fps]').forEach(b=>b.classList.toggle('active',b.dataset.videoFps===S.videoFps));applyWallpaper()}
function applyVideoQuality(v){S.videoQuality=v==='4k'?'4k':'1080p';ls('video-quality',S.videoQuality);$$('[data-video-quality]').forEach(b=>b.classList.toggle('active',b.dataset.videoQuality===S.videoQuality));applyWallpaper()}
$$('[data-video-fps]').forEach(b=>b.addEventListener('click',()=>{playClick();applyVideoFps(b.dataset.videoFps)}));
$$('[data-video-quality]').forEach(b=>b.addEventListener('click',()=>{playClick();applyVideoQuality(b.dataset.videoQuality)}));
$$('[data-video-fps]').forEach(b=>b.classList.toggle('active',b.dataset.videoFps===S.videoFps));
$$('[data-video-quality]').forEach(b=>b.classList.toggle('active',b.dataset.videoQuality===S.videoQuality));
$('toggle-effects-button').addEventListener('click',()=>applyEffects(S.effects==='on'?'off':'on'));
$('toggle-responses-button').addEventListener('click',()=>applyOptResp(S.optResp==='on'?'off':'on'));
$('toggle-uiopt-button').addEventListener('click',()=>applyUiOpt(S.uiOpt==='on'?'off':'on'));
['user-firstname','user-lastname','user-tone','user-info'].forEach(id=>$(id).addEventListener('input',persistPerso));
(function(){const aiIn=$('ai-name-input'),aiReset=$('ai-name-reset-btn');if(aiIn){aiIn.value=S.aiName||'';aiIn.addEventListener('input',()=>{S.aiName=aiIn.value.trim();ls('ai-name',S.aiName);updateAiName()})}if(aiReset){aiReset.addEventListener('click',()=>{playClick();S.aiName='';ls('ai-name','');if(aiIn)aiIn.value='';updateAiName()})}})();
(function(){const aiLogoChange=$('ai-logo-change-btn'),aiLogoReset=$('ai-logo-reset-btn'),aiLogoPreview=$('ai-logo-preview');function refreshLogoPreview(){if(!aiLogoPreview)return;const mainLogo=$('main-logo');const fallback=mainLogo?mainLogo.dataset.light||mainLogo.src:'';aiLogoPreview.src=S.aiLogo||fallback}if(aiLogoChange){aiLogoChange.addEventListener('click',()=>{playClick();const inp=document.createElement('input');inp.type='file';inp.accept='image/*';inp.onchange=e=>{const f=e.target.files&&e.target.files[0];if(!f)return;const r=new FileReader();r.onload=ev=>{const data=ev.target.result;S.aiLogo=data;ls('ai-logo',data);updateThemedLogos();refreshLogoPreview()};r.readAsDataURL(f)};inp.click()})}if(aiLogoReset){aiLogoReset.addEventListener('click',()=>{playClick();S.aiLogo='';ls('ai-logo','');updateThemedLogos();refreshLogoPreview()})}refreshLogoPreview()})();
['profile-firstname-input','profile-lastname-input','profile-bio-input','profile-instagram-input','profile-tiktok-input','profile-youtube-input','profile-github-input','profile-bluesky-input'].forEach(id=>$(id).addEventListener('input',persistProfileForm));
(function(){const bioIn=$('profile-bio-input'),bioCount=$('profile-bio-count'),bioCounter=$('profile-bio-counter');if(!bioIn||!bioCount)return;function updateBioCounter(){const len=bioIn.value.length;bioCount.textContent=String(len);bioCounter.classList.remove('warning','danger');if(len>900)bioCounter.classList.add('danger');else if(len>750)bioCounter.classList.add('warning')}bioIn.addEventListener('input',updateBioCounter);updateBioCounter()})();
profileEditToggle.addEventListener('click',()=>toggleProfileEditor());
calcTargetTrigger.addEventListener('click',()=>{playClick();calcTargetMenu.classList.contains('open')?closeCalcTargetMenu():openCalcTargetMenu()});
calcTargetMenu.addEventListener('click',e=>{const btn=e.target.closest('[data-ct-value]');if(!btn)return;playClick();applyCalcTarget(btn.dataset.ctValue,false,true);closeCalcTargetMenu()});
if(profileShareProBtn)profileShareProBtn.addEventListener('click',()=>shareProfile(false));
if(profileShareFullBtn)profileShareFullBtn.addEventListener('click',()=>shareProfile(true));
if(profileAvatarMessagesToggle)profileAvatarMessagesToggle.addEventListener('change',()=>{profileSet('showMessageAvatar',profileAvatarMessagesToggle.checked?'on':'off');updateProfileUI();renderMessages()});
voiceInputBtn.addEventListener('click',triggerVoiceInput);
profileAvatarUploadBtn.addEventListener('click',()=>openProfilePicker('avatar'));
profileBannerUploadBtn.addEventListener('click',()=>openProfilePicker('banner'));
if(profilePickerCloseBtn)profilePickerCloseBtn.addEventListener('click',closeProfilePicker);
if(profilePickerBackdrop)profilePickerBackdrop.addEventListener('click',e=>{if(e.target===profilePickerBackdrop)closeProfilePicker()});
profileAvatarRemoveBtn.addEventListener('click',()=>{profileSet('avatar','');loadProfileForm()});
profileBannerRemoveBtn.addEventListener('click',()=>{profileSet('banner','');loadProfileForm()});
profileAvatarFile.addEventListener('change',async()=>{if(profileAvatarFile.files&&profileAvatarFile.files[0])await handleProfileImage(profileAvatarFile.files[0],'avatar');profileAvatarFile.value=''})
profileBannerFile.addEventListener('change',async()=>{if(profileBannerFile.files&&profileBannerFile.files[0])await handleProfileImage(profileBannerFile.files[0],'banner');profileBannerFile.value=''})
cropApplyBtn.addEventListener('click',applyCrop);
cropCancelBtn.addEventListener('click',closeCropper);
cropCloseBtn.addEventListener('click',closeCropper);
cropBackdrop.addEventListener('click',e=>{if(e.target===cropBackdrop)closeCropper()});
cropZoom.addEventListener('input',()=>{if(!cropState)return;cropState.zoom=Math.max(1,Number(cropZoom.value||100)/100);clampCropOffsets();renderCropper()});
cropCanvas.addEventListener('pointerdown',e=>{if(!cropState)return;cropState.dragging=true;cropState.pointerId=e.pointerId;cropState.lastX=e.clientX;cropState.lastY=e.clientY;cropCanvas.classList.add('dragging');try{cropCanvas.setPointerCapture(e.pointerId)}catch{}});
cropCanvas.addEventListener('pointermove',e=>{if(!cropState||!cropState.dragging)return;cropState.offsetX+=e.clientX-cropState.lastX;cropState.offsetY+=e.clientY-cropState.lastY;cropState.lastX=e.clientX;cropState.lastY=e.clientY;clampCropOffsets();renderCropper()});
const releaseCropPointer=e=>{if(!cropState)return;cropState.dragging=false;cropCanvas.classList.remove('dragging');try{if(e&&cropState.pointerId!==null)cropCanvas.releasePointerCapture(cropState.pointerId)}catch{}cropState.pointerId=null};
cropCanvas.addEventListener('pointerup',releaseCropPointer);
cropCanvas.addEventListener('pointercancel',releaseCropPointer);
window.addEventListener('resize',()=>{if(cropState)initCropState();hideProfileAvatarHover(true)});
msgBox.addEventListener('scroll',()=>hideProfileAvatarHover(true));
// Boutons paramètres — fonctionnalités à venir (alertes temporaires)
const manageMemoryButton=$('manage-memory-button'),manageHistoryButton=$('manage-history-button'),releaseRamButton=$('release-ram-button'),updateInfoButton=$('update-info-button');
if(manageMemoryButton)manageMemoryButton.addEventListener('click',()=>{playClick();alert(t('soon'))});
if(manageHistoryButton)manageHistoryButton.addEventListener('click',()=>{playClick();alert(t('soon'))});
if(releaseRamButton)releaseRamButton.addEventListener('click',()=>{playClick();alert(t('soon'))});
if(updateInfoButton)updateInfoButton.addEventListener('click',()=>{playClick();alert(t('soon'))});
if(scaleDownButton)scaleDownButton.addEventListener('click',()=>applyUIScale(S.uiScale-10,true));
if(scaleUpButton)scaleUpButton.addEventListener('click',()=>applyUIScale(S.uiScale+10,true));
['pointerdown','keydown','touchstart'].forEach(evt=>document.addEventListener(evt,tryPlayWallpaperVideo,{passive:true}));
document.addEventListener('visibilitychange',()=>{if(!document.hidden)tryPlayWallpaperVideo()});
$('goat-dev-news-btn').addEventListener('click',()=>{playClick();alert(t('soon'))});
$('goat-dev-about-btn').addEventListener('click',()=>{playClick();alert(t('soon'))});
$('migrate-data-button').addEventListener('click',()=>{playClick();closeSettings();setTimeout(openMigrate,200)});

// ── Modal contact développeur (onglet Aide) ──────────────────
const aideContactBackdrop=$('aide-contact-backdrop');
function openAideContact(){aideContactBackdrop.classList.add('open');document.body.style.overflow='hidden'}
function closeAideContact(){aideContactBackdrop.classList.remove('open');document.body.style.overflow=''}
$('aide-contact-btn').addEventListener('click',()=>{playClick();openAideContact()});
$('aide-contact-close').addEventListener('click',()=>{playClick();closeAideContact()});
// Clic sur le fond pour fermer
aideContactBackdrop.addEventListener('click',e=>{if(e.target===aideContactBackdrop)closeAideContact()});

// Fermeture des dropdowns au clic en dehors
document.addEventListener('click',e=>{if(!(e.target instanceof Element))return;if(!modeMenu.contains(e.target)&&!modeTrigger.contains(e.target))closeMM();if(!styleMenu.contains(e.target)&&!styleTrigger.contains(e.target))closeSM();if(!gadgetMenu.contains(e.target)&&!gadgetTrigger.contains(e.target))closeGM();if(!modelDDMenu.contains(e.target)&&!modelTriggerBtn.contains(e.target))closeModelDD();if(!plusMenu.contains(e.target)&&!composerPlus.contains(e.target))plusMenu.classList.remove('open');if(!calcTargetMenu.contains(e.target)&&!calcTargetTrigger.contains(e.target))closeCalcTargetMenu()});
// ── Barre latérale (Sidebar) ─────────────────────────────────────
const sidebarPanel=$('sidebar-panel'),sidebarOverlay=$('sidebar-overlay');
let sidebarOpen=false;
function openSidebar(){
  sidebarOpen=true;
  if(sidebarPanel){sidebarPanel.classList.add('open');sidebarPanel.setAttribute('aria-hidden','false')}
  if(sidebarOverlay){sidebarOverlay.classList.add('open');sidebarOverlay.setAttribute('aria-hidden','false')}
}
function closeSidebar(){
  sidebarOpen=false;
  if(sidebarPanel){sidebarPanel.classList.remove('open');sidebarPanel.setAttribute('aria-hidden','true')}
  if(sidebarOverlay){sidebarOverlay.classList.remove('open');sidebarOverlay.setAttribute('aria-hidden','true')}
}
// Bouton toggle sidebar (☰)
const sidebarToggleBtn=$('sidebar-toggle-btn');
if(sidebarToggleBtn)sidebarToggleBtn.addEventListener('click',()=>{playClick();sidebarOpen?closeSidebar():openSidebar()});
// Bouton fermer dans la sidebar (×)
const sidebarCloseBtn=$('sidebar-close-btn');
if(sidebarCloseBtn)sidebarCloseBtn.addEventListener('click',()=>{playClick();closeSidebar()});
// Clic sur l'overlay ferme la sidebar
if(sidebarOverlay)sidebarOverlay.addEventListener('click',()=>{closeSidebar()});
// Bouton "Nouvelle discussion" dans la sidebar
const sidebarNewChatBtn=$('sidebar-new-chat-btn');
if(sidebarNewChatBtn)sidebarNewChatBtn.addEventListener('click',async()=>{
  closeSidebar();
  playClick();
  if(!confirm(t('new_chat_confirm')))return;
  statusEl.textContent='...';
  try{
    const p=await apiNewChat();
    messages=p.messages;messagesMeta=p.metas||[];
    refreshWelcomeContent();
    renderMessages();
    statusEl.textContent=activeTab==='coworking'?getCoworkingContent().status:(ST[S.lang]||ST[defs.lang]);
    ta.value='';autoResize();ta.focus();
  }catch(e){statusEl.textContent=e.message}
});
// Bouton "Paramètres" dans la sidebar
const sidebarSettingsBtn=$('sidebar-settings-btn');
if(sidebarSettingsBtn)sidebarSettingsBtn.addEventListener('click',()=>{playClick();closeSidebar();openSettings()});
// ── Système "Créer un fichier" : modale + persistance + menu actions ──
const sfBackdrop=$('sf-modal-backdrop'),sfTitleEl=$('sf-modal-title'),sfInput=$('sf-modal-input'),sfCancel=$('sf-modal-cancel'),sfConfirm=$('sf-modal-confirm');
const sfPopover=$('sf-popover'),sfPopRename=$('sf-popover-rename'),sfPopDelete=$('sf-popover-delete');
const sfFilesContainer=document.querySelector('[data-sidebar-content="files"]');
let sfMode='create',sfActiveId=null,sfMenuTargetId=null,sfMenuTargetEl=null;
function sfLoad(){try{const raw=ls('sidebar-files')||'[]';const arr=JSON.parse(raw);return Array.isArray(arr)?arr:[]}catch(e){return[]}}
function sfSave(arr){ls('sidebar-files',JSON.stringify(arr||[]))}
function sfNewId(){return 'f_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2,7)}
function sfOpenModal(mode,id){
  sfMode=mode;sfActiveId=id||null;
  if(mode==='rename'){
    const file=sfLoad().find(f=>f.id===id);
    sfTitleEl.textContent='Renommer le fichier';
    sfConfirm.textContent='Renommer';
    sfInput.value=file?file.name:'';
  }else{
    sfTitleEl.textContent='Nouveau fichier';
    sfConfirm.textContent='Créer';
    sfInput.value='';
  }
  sfBackdrop.classList.add('open');
  sfBackdrop.setAttribute('aria-hidden','false');
  setTimeout(()=>{try{sfInput.focus();sfInput.select()}catch(e){}},30);
}
function sfCloseModal(){sfBackdrop.classList.remove('open');sfBackdrop.setAttribute('aria-hidden','true');sfActiveId=null}
function sfConfirmModal(){
  const name=(sfInput.value||'').trim();
  if(!name){sfInput.focus();return}
  const arr=sfLoad();
  if(sfMode==='rename'&&sfActiveId){
    const idx=arr.findIndex(f=>f.id===sfActiveId);
    if(idx>=0){arr[idx].name=name;sfSave(arr)}
  }else{
    arr.push({id:sfNewId(),name:name,created:Date.now()});
    sfSave(arr);
  }
  sfCloseModal();sfRenderFiles();
}
function sfClosePopover(){
  if(!sfPopover)return;
  sfPopover.classList.remove('open');
  sfPopover.setAttribute('aria-hidden','true');
  if(sfMenuTargetEl)sfMenuTargetEl.classList.remove('menu-open');
  sfMenuTargetId=null;sfMenuTargetEl=null;
}
function sfOpenPopover(itemEl,id){
  sfClosePopover();
  sfMenuTargetId=id;sfMenuTargetEl=itemEl;
  itemEl.classList.add('menu-open');
  sfPopover.classList.add('open');
  sfPopover.setAttribute('aria-hidden','false');
  const r=itemEl.getBoundingClientRect();
  const popW=sfPopover.offsetWidth||180;
  const popH=sfPopover.offsetHeight||80;
  let left=r.right-popW;
  if(left<8)left=8;
  if(left+popW>window.innerWidth-8)left=window.innerWidth-popW-8;
  let top=r.bottom+4;
  if(top+popH>window.innerHeight-8)top=Math.max(8,r.top-popH-4);
  sfPopover.style.left=left+'px';
  sfPopover.style.top=top+'px';
}
function sfRenderFiles(){
  if(!sfFilesContainer)return;
  // Conserver le bouton "Créer un fichier" en tête de liste
  const createBtn=sfFilesContainer.querySelector('#sidebar-create-file-btn');
  sfFilesContainer.innerHTML='';
  if(createBtn)sfFilesContainer.appendChild(createBtn);
  const arr=sfLoad();
  arr.forEach(f=>{
    const row=document.createElement('div');
    row.className='sf-item';
    row.dataset.fileId=f.id;
    row.innerHTML='<svg class="sf-item-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>'+
      '<span class="sf-item-name"></span>'+
      '<button type="button" class="sf-item-more" aria-label="Options"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="5" r="1.4"/><circle cx="12" cy="12" r="1.4"/><circle cx="12" cy="19" r="1.4"/></svg></button>';
    row.querySelector('.sf-item-name').textContent=f.name;
    const more=row.querySelector('.sf-item-more');
    const opener=e=>{e.stopPropagation();if(sfMenuTargetId===f.id){sfClosePopover();return}sfOpenPopover(row,f.id)};
    row.addEventListener('click',opener);
    more.addEventListener('click',opener);
    sfFilesContainer.appendChild(row);
  });
}
const sidebarCreateFileBtn=$('sidebar-create-file-btn');
if(sidebarCreateFileBtn)sidebarCreateFileBtn.addEventListener('click',e=>{e.stopPropagation();playClick();sfClosePopover();sfOpenModal('create')});
if(sfCancel)sfCancel.addEventListener('click',()=>{playClick();sfCloseModal()});
if(sfConfirm)sfConfirm.addEventListener('click',()=>{playClick();sfConfirmModal()});
if(sfBackdrop)sfBackdrop.addEventListener('click',e=>{if(e.target===sfBackdrop)sfCloseModal()});
if(sfInput)sfInput.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();sfConfirmModal()}else if(e.key==='Escape'){e.preventDefault();sfCloseModal()}});
if(sfPopRename)sfPopRename.addEventListener('click',e=>{e.stopPropagation();playClick();const id=sfMenuTargetId;sfClosePopover();if(id)sfOpenModal('rename',id)});
if(sfPopDelete)sfPopDelete.addEventListener('click',e=>{e.stopPropagation();playClick();const id=sfMenuTargetId;sfClosePopover();if(!id)return;if(!confirm('Supprimer ce fichier ?'))return;const arr=sfLoad().filter(f=>f.id!==id);sfSave(arr);sfRenderFiles()});
document.addEventListener('click',e=>{if(!sfPopover||!sfPopover.classList.contains('open'))return;if(sfPopover.contains(e.target))return;if(sfMenuTargetEl&&sfMenuTargetEl.contains(e.target))return;sfClosePopover()});
window.addEventListener('resize',sfClosePopover);
window.addEventListener('scroll',sfClosePopover,true);
sfRenderFiles();
// Onglets de la sidebar (Fichiers / Historique)
$$('[data-sidebar-tab]').forEach(btn=>btn.addEventListener('click',()=>{
  playClick();
  const tab=btn.dataset.sidebarTab;
  $$('[data-sidebar-tab]').forEach(b=>b.classList.toggle('active',b.dataset.sidebarTab===tab));
  $$('[data-sidebar-content]').forEach(s=>s.hidden=s.dataset.sidebarContent!==tab);
}));
// Recherche dans la sidebar (placeholder — filtrage futur de l'historique)
const sidebarSearch=$('sidebar-search');
if(sidebarSearch)sidebarSearch.addEventListener('input',()=>{/* filtrage historique à implémenter */});
// Bouton profil dans le footer de la sidebar — ouvre l'onglet Profil des paramètres
const sidebarProfileBtn=$('sidebar-profile-btn');
if(sidebarProfileBtn)sidebarProfileBtn.addEventListener('click',()=>{
  playClick();closeSidebar();openSettings();
  // Bascule sur l'onglet Profil si présent
  const _pt=document.querySelector('[data-settings-tab="profile"]');if(_pt)_pt.click();
});

// ──────────────────────────────────────────────────────────────
// Composer : bouton + (Image / Fichier)
// ──────────────────────────────────────────────────────────────
const attachBtn=$('attach-btn'),attachMenu=$('attach-menu'),attachImageBtn=$('attach-image-btn'),attachFileBtn=$('attach-file-btn');
const attachImageInput=$('attach-image-input'),attachFileInput=$('attach-file-input'),attachmentsRow=$('attachments-row');
let attachments=[]; // [{kind:'image'|'file',name,size,type,dataUrl?}]
function fmtSize(n){if(!Number.isFinite(n))return'';const u=['o','Ko','Mo','Go'];let i=0,v=n;while(v>=1024&&i<u.length-1){v/=1024;i++}return (v<10?v.toFixed(1):Math.round(v))+' '+u[i]}
function escAttr(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function renderAttachments(){
  if(!attachmentsRow)return;
  if(!attachments.length){attachmentsRow.hidden=true;attachmentsRow.innerHTML='';return}
  attachmentsRow.hidden=false;
  attachmentsRow.innerHTML=attachments.map((a,i)=>{
    const thumb=a.kind==='image'&&a.dataUrl
      ?`<span class="attachment-thumb"><img src="${escAttr(a.dataUrl)}" alt=""></span>`
      :`<span class="attachment-thumb"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg></span>`;
    return `<div class="attachment-chip" data-att-idx="${i}">${thumb}<div class="attachment-meta"><span class="attachment-name" title="${escAttr(a.name)}">${escAttr(a.name)}</span><span class="attachment-size">${escAttr(fmtSize(a.size))}</span></div><button type="button" class="attachment-remove" data-att-remove="${i}" aria-label="Retirer">×</button></div>`;
  }).join('');
  attachmentsRow.querySelectorAll('[data-att-remove]').forEach(b=>b.addEventListener('click',e=>{e.stopPropagation();attachments.splice(+b.dataset.attRemove,1);renderAttachments()}));
}
function readImageFile(file){return new Promise(res=>{const r=new FileReader();r.onload=()=>res(r.result);r.onerror=()=>res(null);r.readAsDataURL(file)})}
async function addAttachmentsFromInput(input,kind){
  const files=Array.from(input.files||[]);input.value='';
  for(const f of files){
    const a={kind,name:f.name,size:f.size,type:f.type||''};
    if(kind==='image'&&/^image\//.test(f.type||'')){a.dataUrl=await readImageFile(f)}
    attachments.push(a);
  }
  renderAttachments();
}
function openAttachMenu(){if(!attachMenu)return;attachMenu.classList.add('open');attachBtn.setAttribute('aria-expanded','true')}
function closeAttachMenu(){if(!attachMenu)return;attachMenu.classList.remove('open');attachBtn.setAttribute('aria-expanded','false')}
if(attachBtn)attachBtn.addEventListener('click',e=>{e.stopPropagation();playClick();attachMenu.classList.contains('open')?closeAttachMenu():openAttachMenu()});
if(attachImageBtn)attachImageBtn.addEventListener('click',()=>{playClick();closeAttachMenu();attachImageInput.click()});
if(attachFileBtn)attachFileBtn.addEventListener('click',()=>{playClick();closeAttachMenu();attachFileInput.click()});
if(attachImageInput)attachImageInput.addEventListener('change',()=>addAttachmentsFromInput(attachImageInput,'image'));
if(attachFileInput)attachFileInput.addEventListener('change',()=>addAttachmentsFromInput(attachFileInput,'file'));
// Ferme le menu si l'on clique à l'extérieur
document.addEventListener('click',e=>{
  if(!attachMenu||!attachMenu.classList.contains('open'))return;
  if(attachMenu.contains(e.target)||(attachBtn&&attachBtn.contains(e.target)))return;
  closeAttachMenu();
});

// Touche Escape — ferme toutes les modales et dropdowns ouverts
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeSidebar();closeMM();closeSM();closeGM();closeModelDD();closeCalcTargetMenu();closeAttachMenu();closeSettings();closeMigrate();closeOverclockModal();closeCropper();closeWallpaperModal();closeAideContact();hideProfileAvatarHover(true);hideTip();
  // Fermetures des nouvelles modales (prévisualisation + connecteurs + menubar)
  if(typeof closePreviewWarning==='function')closePreviewWarning();
  if(typeof closeConnectorsModal==='function')closeConnectorsModal();
  if(typeof closeConnectorsCustom==='function')closeConnectorsCustom();
  if(typeof closeAllMenubar==='function')closeAllMenubar();
}});
// Textarea — redimensionnement auto + limite caractères + son clavier
ta.addEventListener('input',()=>{autoResize();enforceCharLimit();updateCharCounter()});
ta.addEventListener('keydown',e=>{const ign=new Set(['Shift','Control','Alt','Meta','CapsLock','Tab','ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Escape']);if(!ign.has(e.key)&&e.key!=='Enter')playKey();if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();form.requestSubmit()}});
// Tooltips data-attribute — liés automatiquement au chargement
$$('[data-tooltip-key]').forEach(el=>bindTip(el,el.dataset.tooltipKey));
bindTip(voiceInputBtn,'Micro vocal : Win + H sur Windows, sinon ouverture de Wispr Flow.');

// ── Initialisation au démarrage ───────────────────────────────────
// Ordre important : charger les préférences AVANT d'appliquer les traductions
// pour que la langue correcte soit déjà dans S.lang lors du premier rendu.
loadPerso();loadProfileForm();toggleProfileEditor(false);showTab(ls('settings-tab')||'general');
document.body.dataset.theme=S.theme;document.body.dataset.effects=S.effects;document.body.dataset.textsize=S.textSize;document.body.dataset.aifont=S.aifont;document.body.dataset.userfont=S.userfont;document.body.dataset.accent=normalizeAccent(S.accent);
applyLang(S.lang,false);applyTheme(S.theme,false);applyEffects(S.effects,false);applyTextSize(S.textSize,false);applyUIScale(S.uiScale,false);applyAccent(S.accent,false);
applyOptResp(S.optResp,false);applyCalcTarget(S.calcTarget,false);applyUiOpt(S.uiOpt,false);
applyKbSound(S.kbSound,false);applyKbStyle(S.kbStyle,false);applyClickSound(S.clickSound,false);applyClickStyle(S.clickStyle,false);applyAiSound(S.aiSound,false);
// ── Modèles personnalisés : normalisation de l'état au démarrage ──
// Si l'option globale est désactivée, on purge l'éventuel modèle actif.
// Si l'id actif ne correspond plus à aucun modèle (storage corrompu),
// on retombe également sur le modèle par défaut.
if(S.otherModelsOn!=='on'){S.activeCustomModel='';ls('active-custom-model','')}
if(S.activeCustomModel&&!cmGet(S.activeCustomModel)){S.activeCustomModel='';ls('active-custom-model','')}
if(S.model===CUSTOM_MODEL_SENTINEL&&!cmHasCustomActive()){S.model=defs.model;ls('model',S.model)}
applyOtherModelsOn(S.otherModelsOn,false);
updateSndVis();enforceMode();renderModes();updateModeUI();renderStyles();updateStyleUI();renderGadgets();updateGadgetUI();renderModelDD();updateCustomModelTriggerUI();renderCustomModelsMenu();updatePrivateChatLabels();updateThemedLogos();autoResize();renderMessages();renderSheets();updatePerf();
applyAiFont(S.aifont,false);applyUserFont(S.userfont,false);updateOverclockUI();updateCharCounter();updateWallpaperPreviews();
setActiveTab(activeTab,false);applyWallpaper();updateAiName();ta.focus(); // Focus textarea au démarrage

// ── Top Tab Bar (Chat / Goat Code) ──
if(tabChat){
  tabChat.addEventListener('click',()=>{
    playClick();
    if(activeTab!=='chat'){
      switchTabWithReset('chat');
      return;
    }
    const menu=modelDDMenu;
    if(menu.classList.contains('open')){
      menu.classList.remove('open');
      tabChat.setAttribute('aria-expanded','false');
    }else{
      menu.classList.add('open');
      tabChat.setAttribute('aria-expanded','true');
    }
  });
}
if(tabCoworking){
  tabCoworking.addEventListener('click',()=>{
    playClick();
    switchTabWithReset('coworking');
  });
}
// Fermer le model dropdown quand on clique ailleurs
document.addEventListener('click',function(e){if(tabChat&&modelDDMenu&&!tabChat.contains(e.target)&&!modelDDMenu.contains(e.target)){modelDDMenu.classList.remove('open');tabChat.setAttribute('aria-expanded','false')}});

// ──────────────────────────────────────────────────────────────
// Toggle "Version de prévisualisation" — active / désactive
// les fonctions expérimentales sans toucher au DOM (CSS toggle).
// ──────────────────────────────────────────────────────────────
const previewToggleInput=$('preview-toggle-input');
const previewWarningBackdrop=$('preview-warning-backdrop');
const previewWarningConfirm=$('preview-warning-confirm');
const previewWarningCancel=$('preview-warning-cancel');
function applyPreviewMode(state){
  // state : 'on' ou 'off'
  const v=state==='off'?'off':'on';
  S.preview=v;
  ls('preview',v);
  document.body.dataset.preview=v;
  if(previewToggleInput)previewToggleInput.checked=(v==='on');
  // Ferme la sidebar si on bascule en mode off et qu'elle est ouverte
  if(v==='off'&&typeof closeSidebar==='function')closeSidebar();
  // Sortir du chat privé si on bascule en off
  if(v==='off'&&S.privateChat&&typeof exitPrivateChat==='function')exitPrivateChat();
}
function openPreviewWarning(){if(previewWarningBackdrop)previewWarningBackdrop.classList.add('open')}
function closePreviewWarning(){if(previewWarningBackdrop)previewWarningBackdrop.classList.remove('open')}
if(previewToggleInput){
  previewToggleInput.addEventListener('change',()=>{
    playClick();
    if(previewToggleInput.checked){
      // Activation → on demande confirmation puis on applique
      previewToggleInput.checked=false; // on attend la confirmation
      openPreviewWarning();
    }else{
      // Désactivation → immédiate
      applyPreviewMode('off');
    }
  });
}
if(previewWarningConfirm)previewWarningConfirm.addEventListener('click',()=>{playClick();closePreviewWarning();applyPreviewMode('on')});
if(previewWarningCancel)previewWarningCancel.addEventListener('click',()=>{playClick();closePreviewWarning();applyPreviewMode('off')});
if(previewWarningBackdrop)previewWarningBackdrop.addEventListener('click',e=>{if(e.target===previewWarningBackdrop){closePreviewWarning();applyPreviewMode('off')}});

// État initial : "on" par défaut sauf si l'utilisateur a explicitement désactivé.
applyPreviewMode(ls('preview')||'on');

// ──────────────────────────────────────────────────────────────
// Onglet Connecteurs — modale "Aucun connecteur" + bouton custom
// ──────────────────────────────────────────────────────────────
const connectorsModalBackdrop=$('connectors-modal-backdrop');
const connectorsModalClose=$('connectors-modal-close');
const connectorsAddBtn=$('connectors-add-btn');
const connectorsAddCustomBtn=$('connectors-add-custom-btn');
const connectorsCustomBackdrop=$('connectors-custom-backdrop');
const connectorsCustomClose=$('connectors-custom-close');
const connectorsCustomOk=$('connectors-custom-ok');
function openConnectorsModal(){if(connectorsModalBackdrop)connectorsModalBackdrop.classList.add('open')}
function closeConnectorsModal(){if(connectorsModalBackdrop)connectorsModalBackdrop.classList.remove('open')}
function openConnectorsCustom(){if(connectorsCustomBackdrop)connectorsCustomBackdrop.classList.add('open')}
function closeConnectorsCustom(){if(connectorsCustomBackdrop)connectorsCustomBackdrop.classList.remove('open')}
if(connectorsAddBtn)connectorsAddBtn.addEventListener('click',()=>{playClick();openConnectorsModal()});
if(connectorsModalClose)connectorsModalClose.addEventListener('click',()=>{playClick();closeConnectorsModal()});
if(connectorsModalBackdrop)connectorsModalBackdrop.addEventListener('click',e=>{if(e.target===connectorsModalBackdrop)closeConnectorsModal()});
if(connectorsAddCustomBtn)connectorsAddCustomBtn.addEventListener('click',()=>{playClick();closeConnectorsModal();openConnectorsCustom()});
if(connectorsCustomClose)connectorsCustomClose.addEventListener('click',()=>{playClick();closeConnectorsCustom()});
if(connectorsCustomOk)connectorsCustomOk.addEventListener('click',()=>{playClick();closeConnectorsCustom()});
if(connectorsCustomBackdrop)connectorsCustomBackdrop.addEventListener('click',e=>{if(e.target===connectorsCustomBackdrop)closeConnectorsCustom()});

// ──────────────────────────────────────────────────────────────
// Barre de menu (Fichier / Édition / Aide)
// ──────────────────────────────────────────────────────────────
const menuFileBtn=$('menu-file-btn'),menuEditBtn=$('menu-edit-btn'),menuHelpBtn=$('menu-help-btn');
const menubarItems=[menuFileBtn,menuEditBtn,menuHelpBtn].filter(Boolean);
function closeAllMenubar(){menubarItems.forEach(b=>{b.classList.remove('open');b.setAttribute('aria-expanded','false')})}
function toggleMenubar(btn){
  const isOpen=btn.classList.contains('open');
  closeAllMenubar();
  if(!isOpen){btn.classList.add('open');btn.setAttribute('aria-expanded','true')}
}
menubarItems.forEach(btn=>btn.addEventListener('click',e=>{e.stopPropagation();playClick();toggleMenubar(btn)}));
// Survol : si un item est déjà ouvert et qu'on survole un autre, on bascule.
menubarItems.forEach(btn=>btn.addEventListener('mouseenter',()=>{
  const anyOpen=menubarItems.some(b=>b.classList.contains('open'));
  if(anyOpen&&!btn.classList.contains('open')){closeAllMenubar();btn.classList.add('open');btn.setAttribute('aria-expanded','true')}
}));
// Clic en dehors → fermeture
document.addEventListener('click',e=>{
  if(!e.target||!e.target.closest)return;
  if(!e.target.closest('#app-menubar'))closeAllMenubar();
});

// Actions des items de menu
async function handleMenubarAction(action){
  closeAllMenubar();
  switch(action){
    case 'open-location':
      try{
        const r=await fetch('/api/open_app_folder',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});
        const p=await r.json();
        if(!p||!p.ok)alert((p&&p.error)||t('soon'));
      }catch(err){alert(t('soon'))}
      break;
    case 'open-settings':
      openSettings();
      break;
    case 'new-chat':
      if(!confirm(t('new_chat_confirm')))return;
      try{
        statusEl.textContent='...';
        const p=await apiNewChat();
        messages=p.messages;messagesMeta=p.metas||[];refreshWelcomeContent();renderMessages();
        statusEl.textContent=activeTab==='coworking'?getCoworkingContent().status:(ST[S.lang]||ST[defs.lang]);
        ta.value='';autoResize();ta.focus();
      }catch(e){statusEl.textContent=e.message}
      break;
    case 'undo':document.execCommand('undo');break;
    case 'redo':document.execCommand('redo');break;
    case 'cut':document.execCommand('cut');break;
    case 'copy':document.execCommand('copy');break;
    case 'paste':
      try{
        if(navigator.clipboard&&navigator.clipboard.readText){
          const text=await navigator.clipboard.readText();
          if(document.activeElement&&'value' in document.activeElement){
            const el=document.activeElement;
            const start=el.selectionStart||0,end=el.selectionEnd||0;
            el.value=el.value.substring(0,start)+text+el.value.substring(end);
            el.selectionStart=el.selectionEnd=start+text.length;
            el.dispatchEvent(new Event('input',{bubbles:true}));
          }
        }else{document.execCommand('paste')}
      }catch(e){/* l'API clipboard nécessite une permission */}
      break;
    case 'select-all':
      if(document.activeElement&&document.activeElement.select){document.activeElement.select()}
      else{document.execCommand('selectAll')}
      break;
    case 'find':
      // Focus la barre de recherche de la sidebar si dispo, sinon ouvre la sidebar
      if(typeof openSidebar==='function')openSidebar();
      setTimeout(()=>{const s=$('sidebar-search');if(s){s.focus();s.select&&s.select()}},120);
      break;
    case 'contact-dev':
      // Ouvre la même modale que dans Paramètres → Aide → Contacter
      if(typeof openAideContact==='function')openAideContact();
      break;
    case 'open-doc':
      // Documentation du projet — placeholder, rien pour le moment.
      break;
  }
}
document.querySelectorAll('[data-menu-action]').forEach(b=>{
  b.addEventListener('click',e=>{e.stopPropagation();playClick();handleMenubarAction(b.dataset.menuAction)});
});

}();
</script>
</body>
</html>'''


def build_index_html(logo_uri: str, messages: Iterable[Message], themed_logos: Optional[Dict[str, str]] = None) -> str:
    cfg, tm = AppConfig, TranslationManager
    tpl = _load_html_template()
    tl = themed_logos or {}
    replacements = {
        "%%APP_TITLE%%": html.escape(cfg.DEFAULT_TITLE),
        "%%LOGO_DATA_URI%%": html.escape(logo_uri, quote=True),
        "%%LEGOAT_LIGHT_URI%%": html.escape(tl.get("legoat_light", logo_uri), quote=True),
        "%%LEGOAT_DARK_URI%%": html.escape(tl.get("legoat_dark", logo_uri), quote=True),
        "%%LEGOAT_PIXEL_LIGHT_URI%%": html.escape(tl.get("legoat_pixel_light", tl.get("legoat_light", logo_uri)), quote=True),
        "%%LEGOAT_PIXEL_DARK_URI%%": html.escape(tl.get("legoat_pixel_dark", tl.get("legoat_dark", logo_uri)), quote=True),
        "%%GOATISTIQUE_LIGHT_URI%%": html.escape(tl.get("goatistique_light", ""), quote=True),
        "%%GOATISTIQUE_DARK_URI%%": html.escape(tl.get("goatistique_dark", ""), quote=True),
        "%%APP_VERSION%%": html.escape(cfg.VERSION),
        "%%TRANSLATIONS_JSON%%": json.dumps(tm.STRINGS, ensure_ascii=False),
        "%%WELCOME_JSON%%": json.dumps(tm.WELCOME, ensure_ascii=False),
        "%%STATUS_JSON%%": json.dumps(tm.STATUS, ensure_ascii=False),
        "%%MODES_JSON%%": json.dumps(cfg.MODE_OPTIONS, ensure_ascii=False),
        "%%DISABLED_MODES_JSON%%": json.dumps(sorted(cfg.DISABLED_MODES_OPTIMIZED)),
        "%%DEFAULT_LANG_JSON%%": json.dumps(cfg.DEFAULT_LANG),
        "%%DEFAULT_THEME_JSON%%": json.dumps(cfg.DEFAULT_THEME),
        "%%DEFAULT_EFFECTS_JSON%%": json.dumps(cfg.DEFAULT_EFFECTS),
        "%%DEFAULT_TEXTSIZE_JSON%%": json.dumps(cfg.DEFAULT_TEXT_SIZE),
        "%%DEFAULT_OPTRESP_JSON%%": json.dumps(cfg.DEFAULT_OPT_RESPONSES),
        "%%DEFAULT_UIOPT_JSON%%": json.dumps(cfg.DEFAULT_UI_OPT),
        "%%DEFAULT_KB_SOUND_JSON%%": json.dumps(cfg.DEFAULT_KB_SOUND),
        "%%DEFAULT_KB_STYLE_JSON%%": json.dumps(cfg.DEFAULT_KB_STYLE),
        "%%DEFAULT_CLICK_SOUND_JSON%%": json.dumps(cfg.DEFAULT_CLICK_SOUND),
        "%%DEFAULT_CLICK_STYLE_JSON%%": json.dumps(cfg.DEFAULT_CLICK_STYLE),
        "%%DEFAULT_AI_SOUND_JSON%%": json.dumps(cfg.DEFAULT_AI_SOUND),
        "%%DEFAULT_MODE_JSON%%": json.dumps(cfg.DEFAULT_MODE_ID),
        "%%DEFAULT_MODEL_JSON%%": json.dumps(cfg.DEFAULT_MODEL),
        "%%DEFAULT_WSTYLE_JSON%%": json.dumps(cfg.DEFAULT_WRITING_STYLE),
        "%%VERSION_JSON%%": json.dumps(cfg.VERSION, ensure_ascii=False),
        "%%TITLE_BY_LANG_JSON%%": json.dumps(cfg.TITLE_BY_LANG, ensure_ascii=False),
        "%%MODELS_JSON%%": json.dumps(cfg.MODELS, ensure_ascii=False),
        "%%WSTYLES_JSON%%": json.dumps(cfg.WRITING_STYLES, ensure_ascii=False),
        "%%GADGETS_JSON%%": json.dumps(cfg.GADGETS, ensure_ascii=False),
        "%%DEFAULT_GADGET_JSON%%": json.dumps(cfg.DEFAULT_GADGET),
        "%%DEFAULT_OTHER_MODELS_JSON%%": json.dumps(cfg.DEFAULT_OTHER_MODELS_ENABLED),
        "%%CUSTOM_MODEL_SENTINEL_JSON%%": json.dumps(cfg.CUSTOM_MODEL_SENTINEL),
        "%%MIGRATION_PROMPT_JSON%%": json.dumps(cfg.MIGRATION_PROMPT, ensure_ascii=False),
        "%%SHEET_LIMITS_JSON%%": json.dumps(cfg.SHEET_LIMITS, ensure_ascii=False),
        "%%STORAGE_PREFIX_JSON%%": json.dumps(cfg.STORAGE_PREFIX),
        "%%MESSAGES_JSON%%": json.dumps(list(messages), ensure_ascii=False),
        "%%MESSAGES_META_JSON%%": json.dumps([], ensure_ascii=False),
        "%%PROFILE_PRESETS_JSON%%": json.dumps(LogoLoader.get_profile_presets(), ensure_ascii=False),
    }
    for k, v in replacements.items():
        tpl = tpl.replace(k, v)
    return tpl


# ============================================================
# Génération de la page HTML
# ============================================================

def build_index_html(
    logo_uri: str,
    messages: Iterable[Message],
    themed_logos: Optional[Dict[str, str]] = None,
    metas: Optional[Iterable[dict]] = None,
) -> str:
    """
    Injecte toutes les données de configuration dans le template HTML.

    Paramètres
    ----------
    logo_uri      : data URI base64 du logo principal (fallback)
    messages      : historique de la session courante (injecté dans le JS)
    themed_logos  : dict {"legoat_light", "legoat_dark", …} → data URI

    Retour
    ------
    str : page HTML complète prête à être servie au client.

    Note : tous les marqueurs %%NOM%% doivent avoir une entrée dans
    `replacements`. Un marqueur non résolu reste visible tel quel dans l'UI.
    """
    cfg, tm = AppConfig, TranslationManager
    tpl = _load_html_template()
    tl = themed_logos or {}

    # Table de remplacement — chaque clé est un marqueur dans le template HTML.
    # Les valeurs sont sérialisées en JSON pour être directement utilisables en JS.
    replacements = {
        # ── Métadonnées ──────────────────────────────────────────
        "%%APP_TITLE%%":     html.escape(cfg.DEFAULT_TITLE),
        "%%APP_VERSION%%":   html.escape(cfg.VERSION),
        "%%VERSION_JSON%%":  json.dumps(cfg.VERSION, ensure_ascii=False),

        # ── Logos (data URI base64) ───────────────────────────────
        "%%LOGO_DATA_URI%%":        html.escape(logo_uri, quote=True),
        "%%LEGOAT_LIGHT_URI%%":     html.escape(tl.get("legoat_light", logo_uri), quote=True),
        "%%LEGOAT_DARK_URI%%":      html.escape(tl.get("legoat_dark",  logo_uri), quote=True),
        "%%GOATISTIQUE_LIGHT_URI%%":html.escape(tl.get("goatistique_light", ""), quote=True),
        "%%GOATISTIQUE_DARK_URI%%": html.escape(tl.get("goatistique_dark",  ""), quote=True),

        # ── Traductions et contenu dynamique ─────────────────────
        "%%TRANSLATIONS_JSON%%": json.dumps(tm.STRINGS,  ensure_ascii=False),
        "%%WELCOME_JSON%%":      json.dumps(tm.WELCOME,  ensure_ascii=False),
        "%%STATUS_JSON%%":       json.dumps(tm.STATUS,   ensure_ascii=False),
        "%%TITLE_BY_LANG_JSON%%":json.dumps(cfg.TITLE_BY_LANG, ensure_ascii=False),

        # ── Modes, modèles, styles ────────────────────────────────
        "%%MODES_JSON%%":          json.dumps(cfg.MODE_OPTIONS,           ensure_ascii=False),
        "%%DISABLED_MODES_JSON%%": json.dumps(sorted(cfg.DISABLED_MODES_OPTIMIZED)),
        "%%MODELS_JSON%%":         json.dumps(cfg.MODELS,                 ensure_ascii=False),
        "%%WSTYLES_JSON%%":        json.dumps(cfg.WRITING_STYLES,         ensure_ascii=False),
        "%%GADGETS_JSON%%":        json.dumps(cfg.GADGETS,                ensure_ascii=False),
        "%%SHEET_LIMITS_JSON%%":   json.dumps(cfg.SHEET_LIMITS,           ensure_ascii=False),

        # ── Valeurs par défaut (injectées dans l'objet `defs` JS) ─
        "%%DEFAULT_LANG_JSON%%":       json.dumps(cfg.DEFAULT_LANG),
        "%%DEFAULT_THEME_JSON%%":      json.dumps(cfg.DEFAULT_THEME),
        "%%DEFAULT_EFFECTS_JSON%%":    json.dumps(cfg.DEFAULT_EFFECTS),
        "%%DEFAULT_TEXTSIZE_JSON%%":   json.dumps(cfg.DEFAULT_TEXT_SIZE),
        "%%DEFAULT_OPTRESP_JSON%%":    json.dumps(cfg.DEFAULT_OPT_RESPONSES),
        "%%DEFAULT_UIOPT_JSON%%":      json.dumps(cfg.DEFAULT_UI_OPT),
        "%%DEFAULT_KB_SOUND_JSON%%":   json.dumps(cfg.DEFAULT_KB_SOUND),
        "%%DEFAULT_KB_STYLE_JSON%%":   json.dumps(cfg.DEFAULT_KB_STYLE),
        "%%DEFAULT_CLICK_SOUND_JSON%%":json.dumps(cfg.DEFAULT_CLICK_SOUND),
        "%%DEFAULT_CLICK_STYLE_JSON%%":json.dumps(cfg.DEFAULT_CLICK_STYLE),
        "%%DEFAULT_AI_SOUND_JSON%%":   json.dumps(cfg.DEFAULT_AI_SOUND),
        "%%DEFAULT_MODE_JSON%%":       json.dumps(cfg.DEFAULT_MODE_ID),
        "%%DEFAULT_MODEL_JSON%%":      json.dumps(cfg.DEFAULT_MODEL),
        "%%DEFAULT_WSTYLE_JSON%%":     json.dumps(cfg.DEFAULT_WRITING_STYLE),
        "%%DEFAULT_GADGET_JSON%%":     json.dumps(cfg.DEFAULT_GADGET),
        "%%DEFAULT_CALC_TARGET_JSON%%":json.dumps(cfg.DEFAULT_CALC_TARGET),
        "%%DEFAULT_OTHER_MODELS_JSON%%": json.dumps(cfg.DEFAULT_OTHER_MODELS_ENABLED),
        "%%CUSTOM_MODEL_SENTINEL_JSON%%": json.dumps(cfg.CUSTOM_MODEL_SENTINEL),

        # ── Divers ────────────────────────────────────────────────
        "%%MIGRATION_PROMPT_JSON%%": json.dumps(cfg.MIGRATION_PROMPT, ensure_ascii=False),
        "%%STORAGE_PREFIX_JSON%%":   json.dumps(cfg.STORAGE_PREFIX),
        "%%MESSAGES_JSON%%":         json.dumps(list(messages), ensure_ascii=False),
        "%%MESSAGES_META_JSON%%":    json.dumps(list(metas) if metas else [], ensure_ascii=False),
        "%%PROFILE_PRESETS_JSON%%":  json.dumps(LogoLoader.get_profile_presets(), ensure_ascii=False),
    }

    # Remplacement séquentiel — chaque marqueur ne peut apparaître qu'une fois
    for key, value in replacements.items():
        tpl = tpl.replace(key, value)
    return tpl



# ============================================================
# Serveur HTTP
# ============================================================



PROFILE_IMAGE_REJECTION_MESSAGE = "Désolé, nous ne pouvons pas mettre votre photo de profil en raison de nos règles d'utilisation."

# ── Tokens de noms de fichiers à risque ──
# Tout fichier contenant l'un de ces tokens (en minuscule) dans son nom
# sera immédiatement rejeté AVANT même l'analyse d'image.
RISKY_IMAGE_NAME_TOKENS = {
    # Contenu pornographique / sexuel explicite
    'porn', 'porno', 'pornography', 'pornographique', 'nsfw',
    'sex', 'sexe', 'sexual', 'sexuel', 'sexuelle',
    'nude', 'nudity', 'nudes', 'naked', 'nu', 'nue',
    'xxx', 'hentai', 'rule34', 'r34', 'onlyfans', 'fansly',
    'lewd', 'explicit', 'fetish', 'fetiche', 'orgasm', 'orgasme',
    'erotic', 'erotique', 'masturbat', 'ejaculat', 'penetrat',
    'gangbang', 'blowjob', 'handjob', 'creampie', 'cumshot',
    'stripteuse', 'stripper', 'escort', 'prostitut',
    # Contenu pédopornographique (TOLÉRANCE ZÉRO)
    'loli', 'lolicon', 'shotacon', 'shota', 'pedo', 'pedophil',
    'cp', 'childporn', 'child_porn', 'childabuse', 'child_abuse',
    'minors', 'underage', 'preteen', 'jailbait',
    'pedoporno', 'pedopornograph',
    # Violence / gore
    'gore', 'guro', 'snuff', 'violence', 'violent',
    'blood', 'bloody', 'execution', 'beheading', 'decapitat',
    'torture', 'mutilat', 'dismember', 'stabbing', 'shooting',
    'massacre', 'carnage', 'cadavre', 'corpse',
    # Haine / extrémisme
    'hate', 'racist', 'racisme', 'racism',
    'nazi', 'naz', 'whitepower', 'white_power', 'kkk',
    'homophobe', 'homophobic', 'homophobie',
    'misogyny', 'misogynie', 'misogynist',
    'antisemite', 'antisemitic', 'antisemitisme',
    'supremacist', 'terroris',
}

# ── Patterns regex appliqués au nom de fichier ──
# Complètent les tokens ci-dessus avec des formes composées
# et des variantes orthographiques.
RISKY_IMAGE_TEXT_PATTERNS = [
    # Porno / sexuel explicite
    re.compile(
        r'\b(?:porn|porno|pornograph|nsfw|nude|nudity|nudes|naked|xxx|hentai'
        r'|rule\s*34|r34|onlyfans|fansly|lewd|explicit|fetish|fetiche'
        r'|erotic|erotique|orgasm|masturbat|ejaculat|penetrat'
        r'|gangbang|blowjob|handjob|creampie|cumshot|stripteuse|stripper'
        r'|escort|prostitut)\b', re.I
    ),
    # Pédopornographie (TOLÉRANCE ZÉRO)
    re.compile(
        r'\b(?:loli|lolicon|shotacon|shota|pedo|pedophil|pedoporno'
        r'|child\s*porn|child\s*abuse|cp|jailbait|underage|preteen'
        r'|minors?\s*(?:sex|nude|naked|porn))\b', re.I
    ),
    # Violence / gore
    re.compile(
        r'\b(?:gore|guro|snuff|violen(?:t|ce)|blood(?:y)?|execution'
        r'|beheading|decapitat|torture|mutilat|dismember|stabbing'
        r'|massacre|carnage|cadavre|corpse)\b', re.I
    ),
    # Haine / extrémisme
    re.compile(
        r'\b(?:nazi|white\s*power|kkk|racist|racis(?:m|me)|homophob'
        r'|misogyn|antisemit|supremacist|terroris)\b', re.I
    ),
]

_NSFW_MODEL_CACHE = None
_NSFW_MODEL_CACHE_FAILED = False

# Labels durs — nudité/pornographie explicite → rejet si score > seuil
HARD_NSFW_LABEL_TOKENS = (
    'nsfw', 'explicit', 'sexual', 'porn', 'pornography', 'nudity', 'nude',
    'hentai', 'xxx', 'graphic nudity', 'graphic sexual', 'adult content',
    'exposed genitalia', 'exposed breast', 'full nudity',
    'gore', 'violence', 'blood', 'disturbing',
)

# Labels doux — contenu suggestif mais potentiellement tolérable
# Bikini/maillot de bain sont TOLÉRES (ne figurent pas dans les labels doux)
SOFT_NSFW_LABEL_TOKENS = (
    'sexy', 'suggestive', 'adult', 'erotic', 'lingerie',
    'provocative', 'seductive', 'risque', 'racy',
)

# Labels TOLÉRES — ne déclenchent PAS de rejet même avec un score élevé
# Ceci couvre les femmes en bikini et les hommes en maillot de bain
TOLERATED_LABEL_TOKENS = (
    'bikini', 'swimsuit', 'swimwear', 'maillot', 'bathing suit',
    'beachwear', 'beach', 'pool', 'swimming',
)

def _decode_data_url(data_url: str) -> bytes:
    if not data_url or ',' not in data_url:
        raise ValueError('Invalid data URL')
    header, payload = data_url.split(',', 1)
    if ';base64' not in header:
        raise ValueError('Unsupported data URL encoding')
    return base64.b64decode(payload)

def _image_from_data_url(data_url: str):
    if Image is None:
        raise RuntimeError('Pillow is required for image processing.')
    raw = _decode_data_url(data_url)
    image = Image.open(io.BytesIO(raw))
    return image

def _normalize_label(label: str) -> str:
    value = re.sub(r'[^a-z0-9]+', ' ', str(label or '').lower()).strip()
    return re.sub(r'\s+', ' ', value)

def _get_local_nsfw_classifier():
    global _NSFW_MODEL_CACHE, _NSFW_MODEL_CACHE_FAILED
    if _NSFW_MODEL_CACHE is not None:
        return _NSFW_MODEL_CACHE
    if _NSFW_MODEL_CACHE_FAILED:
        return None
    model_path = os.getenv('GOAT_NSFW_MODEL_PATH', '').strip()
    if not model_path:
        _NSFW_MODEL_CACHE_FAILED = True
        return None
    try:
        from transformers import pipeline  # type: ignore
        _NSFW_MODEL_CACHE = pipeline(
            'image-classification',
            model=model_path,
            image_processor=model_path,
            local_files_only=True,
        )
        return _NSFW_MODEL_CACHE
    except Exception:
        _NSFW_MODEL_CACHE_FAILED = True
        return None

def _classify_with_local_model(image) -> tuple[bool, float] | None:
    """
    Classification via modèle local (transformers pipeline).

    Seuils de décision :
      - hard_risk >= 0.45 → REJET (nudité, porno, violence)
      - soft_risk >= 0.80 → REJET (suggestif/érotique)
      - SAUF si le label dominant est toléré (bikini, maillot)
        → dans ce cas on relâche le soft_risk
    """
    classifier = _get_local_nsfw_classifier()
    if classifier is None:
        return None
    try:
        results = classifier(image)
    except Exception:
        return None
    hard_risk = 0.0
    soft_risk = 0.0
    tolerated_score = 0.0
    for item in results or []:
        label = _normalize_label(item.get('label'))
        score = float(item.get('score', 0.0) or 0.0)
        if any(token in label for token in HARD_NSFW_LABEL_TOKENS):
            hard_risk = max(hard_risk, score)
        elif any(token in label for token in SOFT_NSFW_LABEL_TOKENS):
            soft_risk = max(soft_risk, score)
        if any(token in label for token in TOLERATED_LABEL_TOKENS):
            tolerated_score = max(tolerated_score, score)
    # Si le contenu est principalement de type bikini/maillot et que
    # le risque dur est bas, on tolère
    if tolerated_score > 0.5 and hard_risk < 0.30:
        safe = True
        return safe, max(hard_risk, soft_risk)
    safe = hard_risk < 0.45 and soft_risk < 0.80
    return safe, max(hard_risk, soft_risk)

def _fallback_visual_nsfw_score(image) -> float:
    """
    Heuristique visuelle de dernier recours quand aucun modèle ML n'est
    disponible. Analyse la distribution de couleurs (peau, rouge, rose,
    zones sombres) pour estimer un score de risque entre 0 et 1.

    Un score >= 0.24 provoque le rejet de l'image.
    Ce seuil est volontairement conservateur : mieux vaut rejeter un
    faux positif que laisser passer du contenu interdit.

    Détection spécifique pour les illustrations anime/dessin :
    Les contenus anime suggestifs ont des caractéristiques visuelles
    distinctes (couleurs très uniformes, contours nets, saturation élevée)
    qui permettent un malus supplémentaire.
    """
    sample = image.copy().convert('RGB')
    sample.thumbnail((256, 256))
    pixels = sample.load()
    total = max(1, sample.width * sample.height)
    skin_like = 0
    red_dominant = 0
    dark_dominant = 0
    pink_like = 0
    bright_like = 0
    blue_cyan_like = 0
    line_dark = 0
    center_skin = 0
    center_total = 0
    top_skin = 0
    top_total = 0
    bottom_skin = 0
    bottom_total = 0
    # Compteurs spécifiques anime/illustration
    high_saturation = 0      # Pixels avec saturation très élevée (aplats)
    uniform_skin_blocks = 0  # Zones de peau très uniformes (sans texture)
    prev_skin = False
    skin_run = 0
    for y in range(sample.height):
        for x in range(sample.width):
            r, g, b = pixels[x, y]
            mx, mn = max(r, g, b), min(r, g, b)
            # Détection peau humaine :
            # - r dominant, écart r-g > 25 (exclut sable/beige/bois)
            # - écart r-b > 35 (exclut gris/pastel)
            # - pas trop lumineux uniformément (exclut blanc cassé)
            is_skin = (r > 100 and g > 50 and b > 20
                       and r > g and r > b
                       and (r - g) > 25
                       and (r - b) > 35
                       and (r + g + b) < 650)
            if is_skin:
                skin_like += 1
                # Détection peau anime : très peu de texture (écart r-g faible)
                if abs(r - g) < 40 and abs(g - b) < 50 and r > 160:
                    if prev_skin:
                        skin_run += 1
                    else:
                        skin_run = 1
                    prev_skin = True
                else:
                    if skin_run > 12:
                        uniform_skin_blocks += skin_run
                    skin_run = 0
                    prev_skin = False
            else:
                if skin_run > 12:
                    uniform_skin_blocks += skin_run
                skin_run = 0
                prev_skin = False
            # Saturation élevée = illustration / anime
            if mx > 60 and mn < mx:
                sat = (mx - mn) / mx
                if sat > 0.45:
                    high_saturation += 1
            if r > 120 and g < 90 and b < 90:
                red_dominant += 1
            if r < 45 and g < 45 and b < 45:
                dark_dominant += 1
            if r > 150 and 90 < g < 190 and 80 < b < 180:
                pink_like += 1
            if (r + g + b) / 3 > 140:
                bright_like += 1
            if b > 110 and g > 90 and r < 120:
                blue_cyan_like += 1
            if mx < 85 and (mx - mn) < 30:
                line_dark += 1
            if sample.width * 0.25 <= x <= sample.width * 0.75 and sample.height * 0.25 <= y <= sample.height * 0.75:
                center_total += 1
                if is_skin:
                    center_skin += 1
            if y < sample.height * 0.35:
                top_total += 1
                if is_skin:
                    top_skin += 1
            if y > sample.height * 0.65:
                bottom_total += 1
                if is_skin:
                    bottom_skin += 1
    skin_ratio = skin_like / total
    red_ratio = red_dominant / total
    dark_ratio = dark_dominant / total
    pink_ratio = pink_like / total
    bright_ratio = bright_like / total
    blue_cyan_ratio = blue_cyan_like / total
    line_dark_ratio = line_dark / total
    center_skin_ratio = center_skin / max(1, center_total)
    top_skin_ratio = top_skin / max(1, top_total)
    bottom_skin_ratio = bottom_skin / max(1, bottom_total)
    high_sat_ratio = high_saturation / total
    uniform_skin_ratio = uniform_skin_blocks / total

    # ── Détection anime/illustration ──
    # Les illustrations ont beaucoup de pixels très saturés et des zones
    # de peau très uniformes (aplats sans texture photographique)
    is_likely_anime = high_sat_ratio > 0.20 and uniform_skin_ratio > 0.04

    score = 0.0

    # Peau globale élevée → risque
    if skin_ratio > 0.42:
        score += min(0.32, (skin_ratio - 0.42) * 1.2)
    # Peau concentrée au centre → risque plus élevé
    if center_skin_ratio > 0.55:
        score += min(0.32, (center_skin_ratio - 0.55) * 1.1)
    # Peau concentrée en bas → risque élevé (zone intime)
    if bottom_skin_ratio > 0.50:
        score += min(0.30, (bottom_skin_ratio - 0.50) * 1.1)
    # Peau concentrée en haut aussi → corps entier exposé
    if top_skin_ratio > 0.55 and bottom_skin_ratio > 0.45:
        score += 0.10
    # Beaucoup de rose → potentiel suggestif
    if pink_ratio > 0.20:
        score += min(0.12, (pink_ratio - 0.20) * 0.7)
    # Image très lumineuse avec beaucoup de peau → suggestif
    if bright_ratio > 0.40 and skin_ratio > 0.35:
        score += min(0.10, (bright_ratio - 0.40) * 0.3)
    # Rouge dominant + sombre → violence potentielle
    if red_ratio > 0.28 and dark_ratio > 0.20:
        score += 0.24

    # ── Malus anime/illustration suggestif ──
    # Les images anime avec beaucoup de peau sont presque toujours
    # du contenu suggestif/ecchi → pénalité forte
    if is_likely_anime and skin_ratio > 0.30:
        score += 0.18
    if is_likely_anime and center_skin_ratio > 0.45:
        score += 0.12

    # ── Tolérance photos plage/piscine ──
    # UNIQUEMENT pour les photos réalistes (pas anime)
    # et seulement si le bleu/cyan est significatif dans l'image
    if not is_likely_anime and blue_cyan_ratio > 0.12:
        score -= min(0.20, (blue_cyan_ratio - 0.12) * 0.6)

    return max(0.0, min(1.0, score))

def _local_image_safety_check(filename: str, data_url: str) -> tuple[bool, str]:
    lower_name = (filename or '').lower()
    if any(token in lower_name for token in RISKY_IMAGE_NAME_TOKENS):
        return False, PROFILE_IMAGE_REJECTION_MESSAGE
    for pattern in RISKY_IMAGE_TEXT_PATTERNS:
        if pattern.search(lower_name):
            return False, PROFILE_IMAGE_REJECTION_MESSAGE
    if Image is None:
        return False, "Pillow est requis pour l'analyse locale des images."
    try:
        image = _image_from_data_url(data_url).convert('RGB')
        if image.width < 64 or image.height < 64:
            return False, 'Image trop petite ou invalide.'
        classified = _classify_with_local_model(image)
        if classified is not None:
            safe, _score = classified
            return (safe, '' if safe else PROFILE_IMAGE_REJECTION_MESSAGE)
        heuristic_score = _fallback_visual_nsfw_score(image)
        if heuristic_score >= 0.24:
            return False, PROFILE_IMAGE_REJECTION_MESSAGE
    except Exception:
        return False, 'Image invalide ou non lisible.'
    return True, ''

def _sanitize_pdf_filename(value: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9_-]+', '-', value.strip().lower())
    cleaned = re.sub(r'-+', '-', cleaned).strip('-')
    return cleaned or 'profil-goat'

def _wrap_pdf_text(pdf, text: str, max_width: float) -> list[str]:
    words = str(text or '').split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = current + ' ' + word
        if pdf.stringWidth(candidate, 'Helvetica', 11) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines

def _draw_pdf_image(pdf, data_url: str, x: float, y: float, w: float, h: float) -> None:
    if not data_url or Image is None or ImageReader is None:
        return
    image = _image_from_data_url(data_url)
    if image.mode not in ('RGB', 'RGBA'):
        image = image.convert('RGBA')
    buf = io.BytesIO()
    image.save(buf, format='PNG')
    buf.seek(0)
    pdf.drawImage(ImageReader(buf), x, y, width=w, height=h, mask='auto', preserveAspectRatio=False)

def _build_profile_pdf(profile: dict, chat_count: int, goat_score: int, include_score: bool) -> bytes:
    if pdf_canvas is None or A4 is None:
        raise RuntimeError("reportlab est requis pour l'export PDF.")
    width, height = A4
    buffer = io.BytesIO()
    pdf = pdf_canvas.Canvas(buffer, pagesize=A4)
    margin = 36
    card_x, card_y = margin, 72
    card_w, card_h = width - (margin * 2), height - 120
    banner_h = 130
    pdf.setFillColorRGB(0.97, 0.98, 1)
    pdf.roundRect(card_x, card_y, card_w, card_h, 18, fill=1, stroke=0)
    if profile.get('banner'):
        _draw_pdf_image(pdf, str(profile.get('banner') or ''), card_x, card_y + card_h - banner_h, card_w, banner_h)
    else:
        pdf.setFillColorRGB(0.12, 0.19, 0.34)
        pdf.roundRect(card_x, card_y + card_h - banner_h, card_w, banner_h, 18, fill=1, stroke=0)
    avatar_size = 76
    avatar_x = card_x + 24
    avatar_y = card_y + card_h - banner_h - (avatar_size / 2)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.roundRect(avatar_x - 4, avatar_y - 4, avatar_size + 8, avatar_size + 8, 20, fill=1, stroke=0)
    if profile.get('avatar'):
        _draw_pdf_image(pdf, str(profile.get('avatar') or ''), avatar_x, avatar_y, avatar_size, avatar_size)
    full_name = ' '.join([str(profile.get('firstname') or '').strip(), str(profile.get('lastname') or '').strip()]).strip() or 'Profil Goat'
    pdf.setFillColorRGB(0.08, 0.11, 0.17)
    pdf.setFont('Helvetica-Bold', 20)
    pdf.drawString(card_x + 120, avatar_y + 42, full_name)
    pdf.setFont('Helvetica', 10)
    pdf.setFillColorRGB(0.34, 0.38, 0.44)
    pdf.drawString(card_x + 120, avatar_y + 24, 'Profil exporté depuis Le Goat')
    current_y = avatar_y - 26
    pdf.setFillColorRGB(0.08, 0.11, 0.17)
    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(card_x + 24, current_y, 'Description')
    current_y -= 18
    pdf.setFont('Helvetica', 11)
    pdf.setFillColorRGB(0.18, 0.22, 0.28)
    bio_lines = _wrap_pdf_text(pdf, str(profile.get('bio') or 'Aucune description renseignée.'), card_w - 48)
    for line in bio_lines[:6]:
        pdf.drawString(card_x + 24, current_y, line)
        current_y -= 15
    current_y -= 8
    pdf.setFillColorRGB(0.08, 0.11, 0.17)
    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(card_x + 24, current_y, f"Chats envoyés à l'IA : {chat_count}")
    current_y -= 18
    if include_score:
        pdf.drawString(card_x + 24, current_y, f'Goat Score : {goat_score}')
        current_y -= 22
    else:
        current_y -= 4
    socials = [
        ('Instagram', profile.get('instagram')),
        ('TikTok', profile.get('tiktok')),
        ('YouTube', profile.get('youtube')),
        ('GitHub', profile.get('github')),
        ('Bluesky', profile.get('bluesky')),
    ]
    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(card_x + 24, current_y, 'Réseaux')
    current_y -= 18
    pdf.setFont('Helvetica', 10.5)
    pdf.setFillColorRGB(0.18, 0.22, 0.28)
    for label, value in socials:
        value = str(value or '').strip()
        if not value:
            continue
        for idx, line in enumerate(_wrap_pdf_text(pdf, f'{label} : {value}', card_w - 48)[:2]):
            pdf.drawString(card_x + 24, current_y, line)
            current_y -= 14
        current_y -= 2 
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()

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


# ============================================================
# Tests unitaires
# ============================================================

class TestChatSession(unittest.TestCase):
    """Tests de la logique de session de chat."""

    def test_normalize(self):
        s = ChatSession()
        s.submit("  Bonjour   Le Goat  ")
        self.assertEqual(s.messages[0], ("Vous", "Bonjour Le Goat"))

    def test_empty_ignored(self):
        s = ChatSession()
        self.assertEqual(s.submit("   "), "")


class TestLogo(unittest.TestCase):
    """Tests du chargement des ressources graphiques."""

    def test_fallback(self):
        uri = LogoLoader.get_data_uri([Path("/no/such/file")])
        self.assertTrue(uri.startswith("data:image/svg+xml,"))


def run_tests() -> None:
    suite = unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestChatSession))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestLogo))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        raise SystemExit(1)


# ============================================================
# Point d'entrée principal
# ============================================================

def main() -> None:
    """
    Initialise et lance l'application Le Goat.

    Modes de lancement
    ------------------
    (défaut)      Fenêtre native pywebview
    --browser     Ouvre dans le navigateur système
    --no-browser  Serveur HTTP pur (headless)
    --test        Lance la suite de tests unitaires et quitte
    """
    parser = argparse.ArgumentParser(description="Le Goat — Interface desktop native")
    parser.add_argument("--host",       default=AppConfig.HOST)
    parser.add_argument("--port",       type=int, default=AppConfig.PORT)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--browser",    action="store_true")
    parser.add_argument("--test",       action="store_true")
    args = parser.parse_args()

    if args.test:
        run_tests()
        return

    app    = GoatWebApp()
    server = GoatHTTPServer((args.host, args.port), GoatRequestHandler, app)
    url    = f"http://{args.host}:{args.port}"
    print(f"Le Goat lancé sur {url}")

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    if args.no_browser:
        try:
            server_thread.join()
        except KeyboardInterrupt:
            print("Arrêt du serveur Le Goat.")
        finally:
            server.server_close()

    elif args.browser or webview is None:
        import webbrowser
        if webview is None:
            print("pywebview non installé — ouverture dans le navigateur.")
        webbrowser.open(url)
        try:
            server_thread.join()
        except KeyboardInterrupt:
            print("Arrêt du serveur Le Goat.")
        finally:
            server.server_close()

    else:
        webview.create_window(
            AppConfig.DEFAULT_TITLE,
            url,
            width=1280,
            height=820,
            min_size=(800, 500),
            resizable=True,
            text_select=True,
        )
        icon_path = LogoLoader.get_icon_path()
        # Conversion PNG → ICO avec Pillow si disponible (Windows exige .ico)
        if icon_path and not icon_path.lower().endswith('.ico'):
            if Image is not None:
                try:
                    ico_str = str(Path(icon_path).with_suffix('.ico'))
                    if not Path(ico_str).exists():
                        img = Image.open(icon_path).convert('RGBA')
                        img.save(ico_str, format='ICO',
                                 sizes=[(256, 256), (128, 128), (64, 64), (32, 32)])
                    icon_path = ico_str
                except Exception:
                    icon_path = None
            else:
                icon_path = None  # Pillow absent — pas d'icône personnalisée
        try:
            webview.start(debug=False, icon=icon_path)
        except TypeError:
            webview.start(debug=False)
        except KeyboardInterrupt:
            pass
        finally:
            print("Arrêt du serveur Le Goat.")
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
