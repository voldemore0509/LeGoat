# -*- coding: utf-8 -*-
# UI Desktop native — Le Goat (Goatistique)
# Refactorisé par Claude — v3 fenêtre native pywebview (fallback navigateur)

from __future__ import annotations

import argparse
import base64
import html
import json
import threading
import unittest
try:
    import webview
except ImportError:
    webview = None
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar, Dict, Iterable, List, Optional, Sequence, Tuple


# ============================================================
# Configuration
# ============================================================

class AppConfig:
    TITLE_BY_LANG: ClassVar[Dict[str, str]] = {"fr": "Le Goat", "en": "The Goat", "es": "El Goat"}
    DEFAULT_TITLE = "Le Goat"
    VERSION = "Goatesque 1.0.0"
    HOST = "127.0.0.1"
    PORT = 8765
    DEFAULT_LANG = "fr"
    DEFAULT_THEME = "light"
    DEFAULT_EFFECTS = "on"
    DEFAULT_TEXT_SIZE = "default"
    DEFAULT_OPT_RESPONSES = "off"
    DEFAULT_UI_OPT = "off"
    DEFAULT_KB_SOUND = "on"
    DEFAULT_KB_STYLE = "bulle"
    DEFAULT_CLICK_SOUND = "on"
    DEFAULT_CLICK_STYLE = "bulle"
    DEFAULT_AI_SOUND = "on"
    STORAGE_PREFIX = "goat"
    MODE_OPTIONS: ClassVar[list] = [
        {"id": "reflection", "icon": "\u25cc"},
        {"id": "fast", "icon": "\u26a1"},
        {"id": "research_in_data", "icon": "\u25a3"},
        {"id": "research_in_memory", "icon": "\u25cd"},
        # {"id": "creativity", "icon": "\u2726"},  # Désactivé
        {"id": "deep_research", "icon": "\u2b23"},
    ]
    DEFAULT_MODE_ID = ""
    DISABLED_MODES_OPTIMIZED: ClassVar[set] = {"reflection", "research_in_memory", "deep_research"}
    MODELS: ClassVar[list] = [
        {"id": "goat", "label_key": "model_goat", "desc_key": "model_goat_desc"},
        {"id": "maestro", "label_key": "model_maestro", "desc_key": "model_maestro_desc"},
        {"id": "goat_code", "label_key": "model_goat_code", "desc_key": "model_goat_code_desc"},
    ]
    DEFAULT_MODEL = "goat"
    # Taille max par feuille (en octets) selon le modèle
    SHEET_LIMITS: ClassVar[Dict[str, int]] = {
        "goat": 6 * 1024,        # 6 Ko par feuille
        "goat_code": 6 * 1024,   # 6 Ko par feuille
        "maestro": 350 * 1024,   # 350 Ko par feuille
    }
    WRITING_STYLES: ClassVar[list] = [
        {"id": "explicatif", "icon": "\U0001f4d6"},
        {"id": "educatif", "icon": "\U0001f393"},
    ]
    DEFAULT_WRITING_STYLE = ""
    GADGETS: ClassVar[list] = [
        {"id": "schema", "icon": "\U0001f4ca"},
    ]
    DEFAULT_GADGET = ""
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
    LOGO_PATHS: ClassVar[list] = [Path("le_goat.png"), Path("logo_goat.png")]


# ============================================================
# Traductions
# ============================================================

class TranslationManager:
    STATUS: ClassVar[Dict[str, str]] = {
        "fr": "Le Goat peut commettre des erreurs. Vérifiez les informations importantes, en particulier si le degré de sûreté affiché est inférieur à 50 %.",
        "en": "The Goat can make mistakes. Verify important information, especially if the displayed confidence score is below 50%.",
        "es": "El Goat puede cometer errores. Verifique la información importante, especialmente si el grado de fiabilidad mostrado es inferior al 50%.",
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
            "general_text_size": "Taille du texte", "general_keyboard_sounds": "Son du clavier",
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
            "data_security_memory": "Gérer la mémoire", "data_security_history": "Gérer l'historique des discussions",
            "optimization_effects": "Optimiser les effets visuels", "optimization_responses": "Optimiser les réponses",
            "optimization_ui": "Optimisation de l'interface", "optimization_ram": "Libération mémoire vive",
            "optimization_ram_hint": "Placeholder (ne fait rien pour l'instant).",
            "state_on": "Activé", "state_off": "Désactivé",
            "mode_active_prefix": "Mode actif :", "no_mode": "Aucun mode",
            "close": "Fermer", "settings_hint": "Astuce : vous pouvez déplacer cette fenêtre avec la souris.",
            "new_chat": "Nouvelle discussion",
            "new_chat_confirm": "La discussion actuelle sera supprimée et irrécupérable. Continuer ?",
            "regenerate": "Relancer", "soon": "Bientôt disponible.",
            "mode_reflection": "Reflection", "mode_fast": "Fast",
            "mode_research_in_data": "Research In Data", "mode_research_in_memory": "Research In Memory",
            "mode_creativity": "Creativity", "mode_deep_research": "Deep Research",
            "model_goat": "Goat", "model_maestro": "Maestro", "model_goat_code": "Goat Code",
            "model_goat_desc": "Modèle par défaut, rapide et polyvalent.",
            "model_maestro_desc": "IA plus lourde, apte à traiter des tâches complexes et de grande envergure.",
            "model_goat_code_desc": "Modèle fait pour la génération de code, correction de code et analyse de code.",
            "model_label": "Modèle", "model_recent": "Le plus récent",
            "tooltip_send": "Envoyer le message (Entrée).", "tooltip_settings": "Ouvrir les paramètres.",
            "tooltip_new_chat": "Démarrer une nouvelle discussion (supprime l'actuelle).",
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
            "thanks_message": "Merci d'utiliser Le Goat !",
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
            "font_default": "Par défaut (Noto Serif)",
            "font_arial": "Arial",
            "font_opendyslexic": "Open Dyslexic",
        },
        "en": {
            "placeholder": "Ask The Goat...", "settings_label": "Settings", "settings_title": "Settings",
            "settings_subtitle": "Local configuration for The Goat",
            "tab_general": "General", "tab_personalization": "Personalization",
            "tab_data_security": "Data & Security", "tab_optimization": "Optimization & Performance",
            "general_language": "Language", "general_version": "Version", "general_theme": "Theme",
            "general_text_size": "Text size", "general_keyboard_sounds": "Keyboard sound",
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
            "data_security_memory": "Manage memory", "data_security_history": "Manage chat history",
            "optimization_effects": "Optimize visual effects", "optimization_responses": "Optimize responses",
            "optimization_ui": "Interface optimization", "optimization_ram": "Free RAM",
            "optimization_ram_hint": "Placeholder (does nothing yet).",
            "state_on": "On", "state_off": "Off",
            "mode_active_prefix": "Active mode:", "no_mode": "No mode",
            "close": "Close", "settings_hint": "Tip: you can move this window with your mouse.",
            "new_chat": "New chat",
            "new_chat_confirm": "The current chat will be deleted and cannot be recovered. Continue?",
            "regenerate": "Regenerate", "soon": "Coming soon.",
            "mode_reflection": "Reflection", "mode_fast": "Fast",
            "mode_research_in_data": "Research In Data", "mode_research_in_memory": "Research In Memory",
            "mode_creativity": "Creativity", "mode_deep_research": "Deep Research",
            "model_goat": "Goat", "model_maestro": "Maestro", "model_goat_code": "Goat Code",
            "model_goat_desc": "Default model, fast and versatile.",
            "model_maestro_desc": "Heavier AI, capable of handling complex and large-scale tasks.",
            "model_goat_code_desc": "Model built for code generation, code correction and code analysis.",
            "model_label": "Model", "model_recent": "Most recent",
            "tooltip_send": "Send message (Enter).", "tooltip_settings": "Open settings.",
            "tooltip_new_chat": "Start a new chat (deletes current).",
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
            "thanks_message": "Thanks for using The Goat!",
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
            "font_default": "Default (Noto Serif)",
            "font_arial": "Arial",
            "font_opendyslexic": "Open Dyslexic",
        },
        "es": {
            "placeholder": "Pregunte a El Goat...", "settings_label": "Ajustes", "settings_title": "Ajustes",
            "settings_subtitle": "Configuración local de El Goat",
            "tab_general": "General", "tab_personalization": "Personalización",
            "tab_data_security": "Datos y seguridad", "tab_optimization": "Optimización y rendimiento",
            "general_language": "Idioma", "general_version": "Versión", "general_theme": "Tema",
            "general_text_size": "Tamaño del texto", "general_keyboard_sounds": "Sonido del teclado",
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
            "data_security_memory": "Gestionar memoria", "data_security_history": "Gestionar historial de chats",
            "optimization_effects": "Optimizar efectos visuales", "optimization_responses": "Optimizar respuestas",
            "optimization_ui": "Optimización de interfaz", "optimization_ram": "Liberar RAM",
            "optimization_ram_hint": "Placeholder (no hace nada todavía).",
            "state_on": "Activado", "state_off": "Desactivado",
            "mode_active_prefix": "Modo activo:", "no_mode": "Sin modo",
            "close": "Cerrar", "settings_hint": "Consejo: puede mover esta ventana con el ratón.",
            "new_chat": "Nuevo chat",
            "new_chat_confirm": "El chat actual se eliminará y no se podrá recuperar. ¿Continuar?",
            "regenerate": "Regenerar", "soon": "Próximamente.",
            "mode_reflection": "Reflection", "mode_fast": "Fast",
            "mode_research_in_data": "Research In Data", "mode_research_in_memory": "Research In Memory",
            "mode_creativity": "Creativity", "mode_deep_research": "Deep Research",
            "model_goat": "Goat", "model_maestro": "Maestro", "model_goat_code": "Goat Code",
            "model_goat_desc": "Modelo por defecto, rápido y versátil.",
            "model_maestro_desc": "IA más pesada, capaz de manejar tareas complejas y de gran envergadura.",
            "model_goat_code_desc": "Modelo hecho para generación de código, corrección de código y análisis de código.",
            "model_label": "Modelo", "model_recent": "Más reciente",
            "tooltip_send": "Enviar mensaje (Enter).", "tooltip_settings": "Abrir ajustes.",
            "tooltip_new_chat": "Iniciar un nuevo chat (borra el actual).",
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
            "thanks_message": "¡Gracias por usar El Goat!",
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
            "font_default": "Por defecto (Noto Serif)",
            "font_arial": "Arial",
            "font_opendyslexic": "Open Dyslexic",
        },
    }


# ============================================================
# Session / Logo / Build (inchangés sauf ajout writing_style au submit)
# ============================================================

Message = Tuple[str, str]

@dataclass
class ChatSession:
    messages: List[Message] = field(default_factory=list)
    last_user_message: str = ""
    last_mode_id: str = ""

    def submit(self, text: str, mode: str = "") -> str:
        cleaned = " ".join(text.strip().split())
        if not cleaned:
            return ""
        self.last_user_message = cleaned
        self.last_mode_id = mode
        self.messages.append(("Vous", cleaned))
        try:
            reply = generate_reply(cleaned, mode)
        except Exception as exc:
            reply = f"Erreur backend IA : {exc}"
        self.messages.append((AppConfig.DEFAULT_TITLE, reply))
        return reply

    def regenerate(self, mode: str | None = None) -> str:
        if not self.last_user_message:
            return ""
        active_mode = mode if mode is not None else self.last_mode_id
        try:
            reply = generate_reply(self.last_user_message, active_mode)
        except Exception as exc:
            reply = f"Erreur backend IA : {exc}"
        self.last_mode_id = active_mode
        if self.messages and self.messages[-1][0] != "Vous":
            self.messages[-1] = (AppConfig.DEFAULT_TITLE, reply)
        else:
            self.messages.append((AppConfig.DEFAULT_TITLE, reply))
        return reply

    def reset(self) -> None:
        self.messages.clear()
        self.last_user_message = ""
        self.last_mode_id = ""


class LogoLoader:
    @classmethod
    def get_data_uri(cls, paths: Optional[Sequence[Path]] = None) -> str:
        search = list(paths) if paths else cls._build_search_paths()
        for p in search:
            try:
                if p.is_file():
                    b64 = base64.b64encode(p.read_bytes()).decode("ascii")
                    return f"data:image/png;base64,{b64}"
            except OSError:
                continue
        return cls._fallback_svg()

    @classmethod
    def _build_search_paths(cls) -> List[Path]:
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
        """Charge un fichier image et retourne un data URI base64."""
        try:
            if filepath.is_file():
                b64 = base64.b64encode(filepath.read_bytes()).decode("ascii")
                return f"data:image/png;base64,{b64}"
        except OSError:
            pass
        return ""

    @classmethod
    def get_themed_logos(cls) -> Dict[str, str]:
        """Charge les logos LeGoat et Goatistique pour les thèmes clair et sombre."""
        base = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
        logo_dir = base / "Logo"
        return {
            "legoat_light": cls._load_file_as_data_uri(logo_dir / "Image_LeGoat_FondBlanc.png"),
            "legoat_dark": cls._load_file_as_data_uri(logo_dir / "Image_LeGoat_FondNoire.png"),
            "goatistique_light": cls._load_file_as_data_uri(logo_dir / "Logo Goatistique fond blanc.png"),
            "goatistique_dark": cls._load_file_as_data_uri(logo_dir / "logo goatistique fond noire.png"),
        }

    @staticmethod
    def _fallback_svg() -> str:
        svg = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 128 128'><defs><linearGradient id='g' x1='0%' y1='0%' x2='100%' y2='100%'><stop offset='0%' stop-color='#19b7ff'/><stop offset='100%' stop-color='#2f5bff'/></linearGradient></defs><rect width='128' height='128' rx='28' fill='#050816'/><circle cx='44' cy='46' r='9' fill='url(#g)'/><circle cx='84' cy='46' r='9' fill='url(#g)'/><path d='M34 84c9-10 18-15 30-15s21 5 30 15' fill='none' stroke='url(#g)' stroke-width='10' stroke-linecap='round'/></svg>"
        import urllib.parse
        return "data:image/svg+xml," + urllib.parse.quote(svg)


# ============================================================
# Template HTML
# ============================================================

def _load_html_template() -> str:
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
:root{--text-scale:1;--bg:#fff;--text-primary:#1f2937;--text-secondary:#6b7280;--text-muted:#b8b8b8;--line:rgba(148,163,184,.22);--bubble-user:#f3f4f6;--bubble-assistant:#fafafa;--input-bg:#f3f4f6;--input-placeholder:#9d9d9d;--surface-soft:#f3f4f6;--surface-softer:#fcfcfd;--surface-border:#cfd6df;--surface-border-soft:#eef2f7;--shadow-soft:0 18px 46px rgba(15,23,42,.10);--send-bg:#1f2937;--send-color:#fff;--send-shadow:0 0 0 2px #374151,4px 4px 0 0 rgba(15,23,42,.7),0 8px 18px rgba(0,0,0,.12);--settings-backdrop:rgba(15,23,42,.34);--settings-panel:rgba(255,255,255,.98);--settings-panel-border:rgba(148,163,184,.16);--settings-sidebar:rgba(243,244,246,.88);--settings-tab-hover:rgba(59,130,246,.08);--settings-tab-active:rgba(59,130,246,.14);--settings-row-border:rgba(148,163,184,.18);--menu-bg:rgba(41,41,41,.98);--menu-border:rgba(255,255,255,.08);--menu-text:#f5f5f5;--menu-hover:rgba(255,255,255,.08);--menu-selected:rgba(121,166,255,.18);--status-color:#b8b8b8;--action-bg:rgba(255,255,255,.65);--action-border:rgba(148,163,184,.18);--action-text:#4b5563;--tooltip-bg:rgba(17,24,39,.95);--tooltip-text:#f8fafc;--tooltip-border:rgba(255,255,255,.08)}
body[data-theme="dark"]{--bg:#161616;--text-primary:#f5f5f5;--text-secondary:#c3c7ce;--text-muted:#9ca3af;--line:rgba(255,255,255,.10);--bubble-user:#262626;--bubble-assistant:#202020;--input-bg:#252525;--input-placeholder:#8a8f98;--surface-soft:#2a2a2a;--surface-softer:#343434;--surface-border:#525867;--surface-border-soft:#2f3440;--shadow-soft:0 20px 48px rgba(0,0,0,.32);--send-bg:#f5f5f5;--send-color:#161616;--send-shadow:0 0 0 2px #d1d5db,4px 4px 0 0 rgba(255,255,255,.3),0 8px 18px rgba(255,255,255,.08);--settings-backdrop:rgba(0,0,0,.52);--settings-panel:rgba(28,28,28,.98);--settings-panel-border:rgba(255,255,255,.06);--settings-sidebar:rgba(38,38,38,.96);--settings-tab-hover:rgba(255,255,255,.06);--settings-tab-active:rgba(121,166,255,.18);--settings-row-border:rgba(255,255,255,.08);--status-color:#9ca3af;--action-bg:rgba(0,0,0,.32);--action-border:rgba(255,255,255,.08);--action-text:rgba(255,255,255,.84)}
body[data-textsize="large"]{--text-scale:1.15}
body[data-effects="off"] *{transition:none!important;animation:none!important}
body[data-effects="off"] .bubble,body[data-effects="off"] .composer,body[data-effects="off"] .settings-modal,body[data-effects="off"] .settings-ghost-button,body[data-effects="off"] .settings-choice,body[data-effects="off"] .bubble-action{box-shadow:none!important;filter:none!important}
body[data-effects="off"] .composer,body[data-effects="off"] .settings-backdrop{backdrop-filter:none!important}
*{box-sizing:border-box}body{margin:0;min-height:100vh;font-family:"JetBrains Mono","Segoe UI",Arial,sans-serif;font-size:calc(16px * var(--text-scale));background:var(--bg);color:var(--text-primary)}
button,input,textarea,select{font:inherit}

/* ── Goat Coworking visual mode ── */
body[data-active-tab="coworking"]{background-image:linear-gradient(rgba(59,130,246,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(59,130,246,.08) 1px,transparent 1px);background-size:32px 32px;background-position:center center}
body[data-theme="dark"][data-active-tab="coworking"]{background-image:linear-gradient(rgba(96,165,250,.11) 1px,transparent 1px),linear-gradient(90deg,rgba(96,165,250,.11) 1px,transparent 1px)}

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
.private-chat-btn{position:fixed;top:18px;right:18px;z-index:50;width:44px;height:44px;border-radius:14px;border:1px solid var(--line);background:var(--bubble-user);color:var(--text-primary);display:inline-flex;align-items:center;justify-content:center;cursor:pointer;font-size:1.1rem;box-shadow:var(--shadow-soft);transition:transform .14s}
.private-chat-btn:hover{transform:translateY(-1px)}
.private-chat-btn .pc-tooltip{display:none;position:fixed;top:66px;right:18px;background:var(--tooltip-bg);color:var(--tooltip-text);padding:10px 14px;border-radius:12px;font-size:.8rem;white-space:nowrap;box-shadow:0 12px 30px rgba(0,0,0,.3);z-index:100}
.private-chat-btn .pc-tooltip .pc-title{font-weight:700;margin-bottom:3px}
.private-chat-btn .pc-tooltip .pc-desc{opacity:.7;font-size:.75rem}
.private-chat-btn:hover .pc-tooltip{display:block}
.private-chat-btn.active{background:rgba(59,130,246,.14);border-color:rgba(59,130,246,.3);color:#3b82f6}

.shell{min-height:100vh;width:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:22px;padding:72px 16px 40px}
.shell.has-messages{justify-content:flex-start;padding-top:82px}
.brand-stack{display:flex;flex-direction:column;align-items:center;gap:12px;opacity:1;transform:translateY(0) scale(1);max-height:260px;overflow:hidden;transition:opacity .26s,transform .26s,max-height .32s,margin .26s}
.shell.has-messages .brand-stack{opacity:0;transform:translateY(-14px) scale(.92);max-height:0;margin:0;pointer-events:none}
.logo-card{width:auto;height:auto;background:none;display:grid;place-items:center;box-shadow:none;border:none;overflow:visible}
.logo-card img{width:110px;height:110px;object-fit:contain;display:block;filter:none}
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
.message-row{display:flex;width:100%}.message-row.user{justify-content:flex-end}
.message-row.assistant{justify-content:flex-start;flex-direction:column;align-items:flex-start;gap:6px}
.bubble{max-width:min(84%,640px);padding:14px 16px;border-radius:22px;line-height:1.5;white-space:pre-wrap;word-break:break-word;box-shadow:var(--shadow-soft);border:1px solid var(--line)}
.message-row.user .bubble{background:var(--bubble-user);color:var(--text-primary);border-top-right-radius:8px}
.message-row.assistant .bubble{background:var(--bubble-assistant);color:var(--text-primary);border-top-left-radius:8px;font-family:"Noto Serif",Georgia,serif}
.bubble-actions{display:inline-flex;gap:10px;padding-left:6px}
.bubble-action{border:1px solid var(--action-border);background:var(--action-bg);color:var(--action-text);border-radius:999px;padding:8px 12px;cursor:pointer;font-size:.75rem;box-shadow:0 10px 24px rgba(15,23,42,.06);transition:transform .14s,box-shadow .14s}
.bubble-action:hover{transform:translateY(-1px)}
.composer-wrap{width:min(760px,calc(100vw - 32px));position:relative}
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
.sheet-thumb{width:100px;height:80px;border-radius:10px;border:1px solid var(--line);background:var(--surface-soft);position:relative;overflow:hidden;display:flex;align-items:center;justify-content:center;font-size:.65rem;color:var(--text-secondary);padding:6px;word-break:break-all;line-height:1.2}
.sheet-thumb .sheet-remove{position:absolute;top:3px;right:3px;width:20px;height:20px;border-radius:50%;border:none;background:rgba(0,0,0,.6);color:#fff;font-size:.7rem;cursor:pointer;display:flex;align-items:center;justify-content:center}
.sheet-modal-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.5);backdrop-filter:blur(4px);z-index:80;display:none;align-items:center;justify-content:center}
.sheet-modal-backdrop.open{display:flex}
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
.send-button{width:42px;height:42px;border:none;border-radius:0;background:var(--send-bg);color:var(--send-color);display:inline-flex;align-items:center;justify-content:center;cursor:pointer;flex:0 0 auto;box-shadow:var(--send-shadow);transition:transform .12s,opacity .12s;font-size:.95rem;font-weight:700;font-family:"JetBrains Mono","Courier New",monospace;clip-path:polygon(18% 0%,82% 0%,82% 9%,91% 9%,91% 18%,100% 18%,100% 82%,91% 82%,91% 91%,82% 91%,82% 100%,18% 100%,18% 91%,9% 91%,9% 82%,0% 82%,0% 18%,9% 18%,9% 9%,18% 9%)}
.send-button:hover{transform:translateY(-1px)}.send-button:disabled{cursor:default;opacity:.55;transform:none}

/* ── Mode + Style rows ── */
.controls-row{display:flex;align-items:center;gap:10px;margin-top:12px;flex-wrap:wrap}
.mode-panel,.style-panel{position:relative;display:flex;flex-direction:column;align-items:flex-start;gap:8px}
.mode-trigger,.style-trigger{min-height:42px;padding:0 14px;border-radius:12px;border:1px solid var(--line);background:var(--surface-soft);color:#2563eb;box-shadow:var(--shadow-soft);display:inline-flex;align-items:center;gap:8px;cursor:pointer;font-size:.8125rem;font-weight:600;transition:transform .14s,box-shadow .14s,background .14s}
.mode-trigger:hover,.style-trigger:hover{transform:translateY(-1px)}
.mode-trigger[aria-expanded="true"],.style-trigger[aria-expanded="true"]{background:rgba(59,130,246,.12);border-color:rgba(59,130,246,.26)}
.trigger-icon{font-size:1rem;color:#3b82f6}.trigger-chevron{color:var(--text-secondary);font-size:.875rem}
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
.settings-modal{position:fixed;left:50%;top:50%;transform:translate(-50%,-50%);width:min(980px,calc(100vw - 36px));min-height:560px;max-height:calc(100vh - 48px);border-radius:26px;overflow:hidden;background:var(--settings-panel);border:1px solid var(--settings-panel-border);box-shadow:0 32px 80px rgba(0,0,0,.32);z-index:70;display:grid;grid-template-columns:250px 1fr;opacity:0;transition:opacity .18s,transform .18s}
.settings-modal.open{opacity:1;transform:translate(-50%,-50%) scale(1)}
.settings-sidebar{background:var(--settings-sidebar);border-right:1px solid var(--settings-panel-border);padding:18px;display:flex;flex-direction:column;gap:8px}
.settings-close-row{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}.settings-close-row strong{color:var(--text-primary);font-size:.9375rem}
.settings-close{width:38px;height:38px;border-radius:12px;border:1px solid var(--line);background:transparent;color:var(--text-primary);cursor:pointer;display:inline-flex;align-items:center;justify-content:center;font-size:1.25rem}
.settings-tab{width:100%;min-height:46px;border:none;border-radius:14px;background:transparent;color:var(--text-primary);cursor:pointer;display:flex;align-items:center;gap:12px;padding:0 14px;text-align:left;transition:background .14s}
.settings-tab:hover{background:var(--settings-tab-hover)}.settings-tab.active{background:var(--settings-tab-active);color:#3b82f6}
.settings-tab-icon{width:18px;text-align:center;opacity:.9;flex:0 0 18px}
.settings-main{display:flex;flex-direction:column;min-width:0}
.settings-header{padding:20px 24px 12px;border-bottom:1px solid var(--settings-row-border);cursor:grab;user-select:none;display:flex;align-items:center;justify-content:space-between;gap:16px}
.settings-header:active{cursor:grabbing}
.settings-header h2{margin:0;font-size:1.5rem;font-weight:600;color:var(--text-primary)}
.settings-header p{margin:6px 0 0;font-size:.8125rem;color:var(--text-secondary)}
.settings-hint{font-size:.75rem;color:var(--text-secondary);text-align:right;max-width:260px}
.settings-content{padding:12px 24px 24px;overflow:auto}
.settings-section{display:none;flex-direction:column;gap:18px}.settings-section.active{display:flex}
.settings-block{border-bottom:1px solid var(--settings-row-border);padding-bottom:18px}.settings-block:last-child{border-bottom:none;padding-bottom:0}
.settings-row{display:flex;align-items:center;justify-content:space-between;gap:20px;padding:12px 0}
.settings-row-stack{display:flex;flex-direction:column;gap:6px}
.settings-row-title{font-size:1rem;color:var(--text-primary);font-weight:500}
.settings-row-subtitle{font-size:.8125rem;color:var(--text-secondary);line-height:1.4}
.settings-version-value{font-size:.9375rem;color:var(--text-primary);font-weight:600}
.settings-ghost-button{min-height:40px;padding:0 16px;border-radius:999px;border:1px solid var(--line);background:var(--bubble-user);color:var(--text-primary);cursor:pointer;box-shadow:var(--shadow-soft)}
.settings-choice-group{display:inline-flex;flex-wrap:wrap;gap:10px;justify-content:flex-end}
.settings-choice{min-height:38px;padding:0 14px;border-radius:999px;border:1px solid var(--line);background:var(--bubble-assistant);color:var(--text-primary);cursor:pointer}
.settings-choice.active{background:rgba(59,130,246,.12);border-color:rgba(59,130,246,.26);color:#3b82f6}
.settings-input,.settings-textarea{width:min(420px,100%);border-radius:16px;border:1px solid var(--line);background:var(--bubble-assistant);color:var(--text-primary);padding:12px 14px;box-shadow:var(--shadow-soft);outline:none}
.settings-textarea{min-height:110px;resize:vertical}
.settings-state{display:inline-flex;align-items:center;justify-content:center;padding:6px 10px;border-radius:999px;font-size:.75rem;border:1px solid var(--line);background:var(--bubble-assistant);color:var(--text-secondary);min-width:92px;text-align:center}
.tooltip{position:fixed;z-index:999;max-width:360px;padding:10px 12px;border-radius:12px;background:var(--tooltip-bg);color:var(--tooltip-text);border:1px solid var(--tooltip-border);box-shadow:0 24px 60px rgba(0,0,0,.28);font-size:.8125rem;line-height:1.35;pointer-events:none;opacity:0;transform:translateY(4px);transition:opacity .12s,transform .12s}
.tooltip.show{opacity:1;transform:translateY(0)}
[hidden]{display:none!important}
.thanks-text{text-align:center;font-size:1rem;font-weight:600;padding:18px 0 6px;background:linear-gradient(90deg,#3b82f6,#8b5cf6,#ec4899,#3b82f6);background-size:300% 100%;-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;animation:shimmer 3s linear infinite}
@keyframes shimmer{0%{background-position:0% 50%}100%{background-position:300% 50%}}
@media(max-width:900px){.settings-modal{width:min(980px,calc(100vw - 24px));grid-template-columns:1fr}.settings-sidebar{border-right:none;border-bottom:1px solid var(--settings-panel-border)}.settings-header{cursor:default}.settings-hint{display:none}}
@media(max-width:640px){.composer{padding:14px;border-radius:22px}.bubble{max-width:92%}.controls-row{flex-wrap:wrap}.mode-announcement{padding-left:0}.dropdown-menu{min-width:min(280px,calc(100vw - 32px))}.settings-anchor{left:12px;bottom:12px}.newchat-anchor{left:12px;top:58px}.settings-modal{min-height:auto;max-height:calc(100vh - 24px)}.settings-header h2{font-size:1.25rem}.settings-row{flex-direction:column;align-items:flex-start}.settings-choice-group{justify-content:flex-start}}

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
body[data-aifont="opendyslexic"] .message-row.assistant .bubble{font-family:"Open Dyslexic","OpenDyslexic",sans-serif}
</style>
</head>
<body data-theme="light" data-effects="on" data-textsize="default" data-active-tab="chat">

<!-- Top Tab Bar -->
<div class="top-tab-bar">
  <div class="top-tab-bar-inner">
    <div class="tab-chat-wrap">
      <button type="button" class="top-tab-btn active" id="tab-chat" aria-expanded="false"><span id="model-current-label">Chat</span><span class="chevron">▾</span></button>
      <div class="model-dd-menu" id="model-dd-menu" role="menu"></div>
    </div>
    <button type="button" class="top-tab-btn" id="tab-coworking" data-tab="coworking">Goat Coworking</button>
  </div>
</div>

<!-- Model dropdown ancien (caché, dummy pour JS) -->
<div class="model-dropdown" id="model-dropdown" hidden>
  <button type="button" class="model-trigger-btn" id="model-trigger-btn" aria-expanded="false"></button>
</div>

<button type="button" class="private-chat-btn" id="private-chat-btn">🔍<div class="pc-tooltip"><div class="pc-title" id="pc-title"></div><div class="pc-desc" id="pc-desc"></div></div></button>

<main class="shell" id="shell">
  <section class="brand-stack"><div class="logo-card"><img id="main-logo" src="%%LEGOAT_LIGHT_URI%%" data-light="%%LEGOAT_LIGHT_URI%%" data-dark="%%LEGOAT_DARK_URI%%" alt="Logo"></div><div class="brand-text" id="brand-text">%%APP_TITLE%%</div><div class="welcome-copy" id="welcome-copy"></div><div class="welcome-desc" id="welcome-desc"></div></section>
  <section class="messages" id="messages" aria-live="polite"></section>
  <section class="composer-wrap">
    <!-- Sheets system désactivé
    <div class="sheets-row" id="sheets-row"></div>
    -->
    <form class="composer" id="chat-form">
      <!-- Plus button désactivé
      <button type="button" class="composer-plus" id="composer-plus" data-tooltip-key="tooltip_plus_btn">+</button>
      -->
      <textarea id="message-input" rows="1"></textarea>
      <button type="submit" class="send-button" id="send-button" data-tooltip-key="tooltip_send">↑</button>
      <button type="button" class="stop-button" id="stop-button" hidden>■</button>
      <!-- Plus menu désactivé
      <div class="plus-menu" id="plus-menu"><button type="button" class="plus-menu-item" id="plus-add-sheet"></button></div>
      -->
    </form>
    <div style="display:flex;justify-content:flex-end;width:100%;padding:0 4px;position:relative">
      <div class="char-counter" id="char-counter"><span id="char-counter-text">0 / 10 000</span><div class="char-counter-tip" id="char-counter-tip"></div></div>
    </div>
    <div class="controls-row" id="controls-row">
      <!-- Modes -->
      <div class="mode-panel" id="mode-panel"><button type="button" class="mode-trigger" id="mode-trigger" aria-haspopup="true" aria-expanded="false" data-tooltip-key="tooltip_mode_trigger"><span class="trigger-icon" id="mode-icon">○</span><span id="selected-mode-label"></span><span class="trigger-chevron">⌄</span></button><div class="dropdown-menu" id="mode-menu" role="menu"></div></div>
      <!-- Writing Styles -->
      <div class="style-panel"><button type="button" class="style-trigger" id="style-trigger" aria-haspopup="true" aria-expanded="false" data-tooltip-key="tooltip_style_trigger"><span class="trigger-icon" id="style-icon">✎</span><span id="selected-style-label"></span><span class="trigger-chevron">⌄</span></button><div class="dropdown-menu" id="style-menu" role="menu"></div></div>
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
<div class="newchat-anchor"><button type="button" class="newchat-button" id="newchat-button" data-tooltip-key="tooltip_new_chat">＋</button><div class="newchat-button-label" id="newchat-button-label"></div></div>
<div class="settings-anchor"><button type="button" class="settings-button" id="settings-button" data-tooltip-key="tooltip_settings">⚙</button><div class="settings-button-label" id="settings-button-label"></div></div>
<div class="settings-backdrop" id="settings-backdrop" hidden></div>
<section class="settings-modal" id="settings-modal" hidden aria-modal="true" role="dialog">
  <aside class="settings-sidebar">
    <div class="settings-close-row"><strong data-i18n="settings_label">Paramètres</strong><button type="button" class="settings-close" id="settings-close">×</button></div>
    <button type="button" class="settings-tab active" data-settings-tab="general"><span class="settings-tab-icon">⚙</span><span data-i18n="tab_general">Générale</span></button>
    <button type="button" class="settings-tab" data-settings-tab="personalization"><span class="settings-tab-icon">✦</span><span data-i18n="tab_personalization">Personnalisation</span></button>
    <button type="button" class="settings-tab" data-settings-tab="data_security"><span class="settings-tab-icon">☑</span><span data-i18n="tab_data_security">Données</span></button>
    <button type="button" class="settings-tab" data-settings-tab="optimization"><span class="settings-tab-icon">⚡</span><span data-i18n="tab_optimization">Optimisation</span></button>
    <button type="button" class="settings-tab" data-settings-tab="goat_dev"><span class="settings-tab-icon">🐐</span><span data-i18n="tab_goat_dev">Goat Developer</span></button>
  </aside>
  <div class="settings-main">
    <div class="settings-header" id="settings-drag-handle"><div><h2 data-i18n="settings_title">Paramètres</h2><p data-i18n="settings_subtitle"></p></div><div class="settings-hint" data-i18n="settings_hint"></div></div>
    <div class="settings-content">
      <section class="settings-section active" data-settings-content="general">
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="general_version">Version</div></div><div class="settings-version-value" id="settings-version-value">%%APP_VERSION%%</div></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="update_info">Mises à jour</div></div><button type="button" class="settings-ghost-button" id="update-info-button" data-i18n="update_info"></button></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="general_language">Langue</div></div><div class="settings-choice-group"><button type="button" class="settings-choice" data-language-value="fr" data-i18n="language_fr">Français</button><button type="button" class="settings-choice" data-language-value="en" data-i18n="language_en">Anglais</button><button type="button" class="settings-choice" data-language-value="es" data-i18n="language_es">Espagnol</button></div></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="general_theme">Thème</div><div class="settings-row-subtitle" data-i18n="theme_description"></div></div><div class="settings-choice-group"><button type="button" class="settings-choice" data-theme-value="light" data-i18n="theme_light">Claire</button><button type="button" class="settings-choice" data-theme-value="dark" data-i18n="theme_dark">Sombre</button></div></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="general_text_size">Taille</div></div><div class="settings-choice-group"><button type="button" class="settings-choice" data-textsize-value="default" data-i18n="text_size_default">Par défaut</button><button type="button" class="settings-choice" data-textsize-value="large" data-i18n="text_size_large">Grand</button></div></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="general_keyboard_sounds">Son clavier</div></div><div class="settings-choice-group" id="keyboard-sound-toggle"><button type="button" class="settings-choice" data-kb-sound="on" data-i18n="sound_on">Activer</button><button type="button" class="settings-choice" data-kb-sound="off" data-i18n="sound_off">Désactiver</button></div></div><div class="settings-row" id="keyboard-style-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="general_keyboard_sound_style">Style</div></div><div class="settings-choice-group"><button type="button" class="settings-choice" data-kb-style="bulle" data-i18n="sound_style_bulle">Bulle</button><button type="button" class="settings-choice" data-kb-style="aurela" data-i18n="sound_style_aurela">Aurela</button><button type="button" class="settings-choice" data-kb-style="verdrock" data-i18n="sound_style_verdrock">Verdrock</button><button type="button" class="settings-choice" data-kb-style="feryn" data-i18n="sound_style_feryn">Feryn</button></div></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="general_click_sounds">Son boutons</div></div><div class="settings-choice-group" id="click-sound-toggle"><button type="button" class="settings-choice" data-click-sound="on" data-i18n="sound_on">Activer</button><button type="button" class="settings-choice" data-click-sound="off" data-i18n="sound_off">Désactiver</button></div></div><div class="settings-row" id="click-style-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="general_click_sound_style">Style</div></div><div class="settings-choice-group"><button type="button" class="settings-choice" data-click-style="bulle" data-i18n="sound_style_bulle">Bulle</button><button type="button" class="settings-choice" data-click-style="nebrise" data-i18n="sound_style_nebrise">Nebrise</button></div></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="general_ai_reply_sounds">Son IA</div></div><div class="settings-choice-group" id="ai-sound-toggle"><button type="button" class="settings-choice" data-ai-sound="on" data-i18n="sound_on">Activer</button><button type="button" class="settings-choice" data-ai-sound="off" data-i18n="sound_off">Désactiver</button></div></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="font_label">Police IA</div></div><div class="settings-choice-group"><button type="button" class="settings-choice" data-aifont-value="default" data-i18n="font_default">Par défaut</button><button type="button" class="settings-choice" data-aifont-value="arial" data-i18n="font_arial">Arial</button><button type="button" class="settings-choice" data-aifont-value="opendyslexic" data-i18n="font_opendyslexic">Open Dyslexic</button></div></div></div>
        <div class="thanks-text" id="thanks-text" data-i18n="thanks_message">Merci d'utiliser Le Goat !</div>
      </section>
      <section class="settings-section" data-settings-content="personalization"><div class="settings-block">
        <div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="personalization_name">Prénom</div></div><input class="settings-input" id="user-firstname" data-placeholder-key="placeholder_firstname"></div>
        <div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="personalization_surname">Nom</div></div><input class="settings-input" id="user-lastname" data-placeholder-key="placeholder_lastname"></div>
        <div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="personalization_tone">Ton</div></div><input class="settings-input" id="user-tone" data-placeholder-key="placeholder_tone"></div>
        <div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="personalization_info">Infos</div></div><textarea class="settings-textarea" id="user-info" data-placeholder-key="personalization_placeholder"></textarea></div>
      </div></section>
      <section class="settings-section" data-settings-content="data_security"><div class="settings-block">
        <div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="data_security_memory">Mémoire</div></div><button type="button" class="settings-ghost-button" id="manage-memory-button" data-i18n="data_security_memory"></button></div>
        <div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="data_security_history">Historique</div></div><button type="button" class="settings-ghost-button" id="manage-history-button" data-i18n="data_security_history"></button></div>
        <div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="migrate_data">Migration</div></div><button type="button" class="settings-ghost-button" id="migrate-data-button" data-i18n="migrate_data"></button></div>
      </div></section>
      <section class="settings-section" data-settings-content="optimization">
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="optimization_effects">Effets visuels</div><div class="settings-row-subtitle">Désactive transitions + ombres + blur.</div></div><div class="settings-choice-group"><span class="settings-state" id="effects-state"></span><button type="button" class="settings-ghost-button" id="toggle-effects-button" data-i18n="optimization_effects"></button></div></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="optimization_responses">Réponses</div><div class="settings-row-subtitle">Bloque Creativity / Reflection / Research In Memory.</div></div><div class="settings-choice-group"><span class="settings-state" id="responses-state"></span><button type="button" class="settings-ghost-button" id="toggle-responses-button" data-i18n="optimization_responses"></button></div></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="optimization_ui">Interface</div><div class="settings-row-subtitle">Désactive sons + effets visuels.</div></div><div class="settings-choice-group"><span class="settings-state" id="uiopt-state"></span><button type="button" class="settings-ghost-button" id="toggle-uiopt-button" data-i18n="optimization_ui"></button></div></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="optimization_ram">RAM</div><div class="settings-row-subtitle" data-i18n="optimization_ram_hint"></div></div><button type="button" class="settings-ghost-button" id="release-ram-button" data-i18n="optimization_ram"></button></div></div>
        <div class="settings-block"><div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="overclock_label">Overclocking IA</div><div class="settings-row-subtitle" data-i18n="overclock_subtitle"></div></div><div class="overclock-toggle" id="overclock-toggle"></div></div></div>
      </section>
      <!-- Goat Developer -->
      <section class="settings-section" data-settings-content="goat_dev"><div class="settings-block">
        <div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="goat_dev_news">Nouveautés</div><div class="settings-row-subtitle" data-i18n="goat_dev_news_desc"></div></div><button type="button" class="settings-ghost-button" id="goat-dev-news-btn" data-i18n="goat_dev_news"></button></div>
        <div class="settings-row"><div class="settings-row-stack"><div class="settings-row-title" data-i18n="goat_dev_about">À propos</div><div class="settings-row-subtitle" data-i18n="goat_dev_about_desc"></div></div><button type="button" class="settings-ghost-button" id="goat-dev-about-btn" data-i18n="goat_dev_about"></button></div>
      </div></section>
    </div>
  </div>
</section>
<div class="migrate-backdrop" id="migrate-backdrop"><div class="migrate-modal"><h3><span id="migrate-title"></span><button type="button" id="migrate-close-x">×</button></h3><div class="migrate-step" id="migrate-step1"></div><div class="migrate-prompt-box" id="migrate-prompt-box"></div><button type="button" class="migrate-copy-btn" id="migrate-copy-btn"></button><div class="migrate-step" id="migrate-step2" style="margin-top:8px"></div><textarea class="migrate-textarea" id="migrate-textarea"></textarea><div class="migrate-actions"><button type="button" class="migrate-btn-cancel" id="migrate-cancel-btn"></button><button type="button" class="migrate-btn-add" id="migrate-add-btn" disabled></button></div></div></div>
<div class="sheet-modal-backdrop" id="sheet-modal-backdrop"><div class="sheet-modal"><div class="sheet-modal-header"><h3 id="sheet-modal-title"></h3><span class="sheet-char-counter" id="sheet-char-counter">0 / 14 000</span></div><textarea id="sheet-textarea" placeholder=""></textarea><div class="sheet-modal-actions"><button type="button" class="sheet-btn-cancel" id="sheet-cancel"></button><button type="button" class="sheet-btn-add" id="sheet-add-btn"></button></div></div></div>
<div class="goatistique-badge" id="goatistique-badge"><img id="goatistique-logo" src="%%GOATISTIQUE_LIGHT_URI%%" data-light="%%GOATISTIQUE_LIGHT_URI%%" data-dark="%%GOATISTIQUE_DARK_URI%%" alt="Goatistique"></div>
<div class="overclock-backdrop" id="overclock-backdrop"><div class="overclock-modal"><h3>⚠ Overclocking IA</h3><div class="oc-warning-text" id="oc-warning-text"></div><div class="oc-actions"><button type="button" class="oc-btn-cancel" id="oc-cancel-btn"></button><button type="button" class="oc-btn-confirm" id="oc-confirm-btn"></button></div></div></div>
<div class="tooltip" id="tooltip" hidden></div>
<!-- Éléments dummy cachés pour éléments désactivés (évite crash JS) -->
<div hidden>
  <button id="composer-plus"></button><div id="plus-menu"></div><button id="plus-add-sheet"></button><div id="sheets-row"></div>
</div>
<script>
!function(){"use strict";
const $=i=>document.getElementById(i),$$=s=>Array.from(document.querySelectorAll(s));
const T=%%TRANSLATIONS_JSON%%,WP=%%WELCOME_JSON%%,ST=%%STATUS_JSON%%,MO=%%MODES_JSON%%,DM=%%DISABLED_MODES_JSON%%,titleByLang=%%TITLE_BY_LANG_JSON%%,models=%%MODELS_JSON%%,wStyles=%%WSTYLES_JSON%%,gadgets=%%GADGETS_JSON%%,SP=%%STORAGE_PREFIX_JSON%%,appVersion=%%VERSION_JSON%%,sheetLimits=%%SHEET_LIMITS_JSON%%,migrationPrompt=%%MIGRATION_PROMPT_JSON%%;
const defs={lang:%%DEFAULT_LANG_JSON%%,theme:%%DEFAULT_THEME_JSON%%,effects:%%DEFAULT_EFFECTS_JSON%%,textSize:%%DEFAULT_TEXTSIZE_JSON%%,optResp:%%DEFAULT_OPTRESP_JSON%%,uiOpt:%%DEFAULT_UIOPT_JSON%%,kbSound:%%DEFAULT_KB_SOUND_JSON%%,kbStyle:%%DEFAULT_KB_STYLE_JSON%%,clickSound:%%DEFAULT_CLICK_SOUND_JSON%%,clickStyle:%%DEFAULT_CLICK_STYLE_JSON%%,aiSound:%%DEFAULT_AI_SOUND_JSON%%,mode:%%DEFAULT_MODE_JSON%%,model:%%DEFAULT_MODEL_JSON%%,wstyle:%%DEFAULT_WSTYLE_JSON%%,gadget:%%DEFAULT_GADGET_JSON%%,aifont:'default',overclock:'off'};
const ls=(k,v)=>{if(v!==undefined){localStorage.setItem(SP+'-'+k,v);return v}return localStorage.getItem(SP+'-'+k)};
const shell=$('shell'),msgBox=$('messages'),form=$('chat-form'),ta=$('message-input'),sendBtn=$('send-button'),statusEl=$('status'),welcomeEl=$('welcome-copy'),welcomeDesc=$('welcome-desc'),brandText=$('brand-text');
const controlsRow=$('controls-row'),modePanel=$('mode-panel');
const modeTrigger=$('mode-trigger'),modeMenu=$('mode-menu'),modeLbl=$('selected-mode-label'),modeIcn=$('mode-icon'),modeAnn=$('mode-announcement');
const styleTrigger=$('style-trigger'),styleMenu=$('style-menu'),styleLbl=$('selected-style-label'),styleIcn=$('style-icon');
/* Gadgets desactive pour le moment
const gadgetTrigger=$('gadget-trigger'),gadgetMenu=$('gadget-menu'),gadgetLbl=$('selected-gadget-label'),gadgetIcn=$('gadget-icon');
*/
const modelTriggerBtn=$('model-trigger-btn'),modelDDMenu=$('model-dd-menu'),modelCurrentLabel=$('model-current-label');
const tabChat=$('tab-chat'),tabCoworking=$('tab-coworking');
const privateChatBtn=$('private-chat-btn');
const composerPlus=$('composer-plus'),plusMenu=$('plus-menu'),plusAddSheet=$('plus-add-sheet'),sheetsRow=$('sheets-row');
const sheetBackdrop=$('sheet-modal-backdrop'),sheetTA=$('sheet-textarea'),sheetAddBtn=$('sheet-add-btn'),sheetCancelBtn=$('sheet-cancel'),sheetTitle=$('sheet-modal-title');
const sheetCharCounter=$('sheet-char-counter');
const migrateBackdrop=$('migrate-backdrop'),migrateTA=$('migrate-textarea'),migrateAddBtn=$('migrate-add-btn'),migrateCancelBtn=$('migrate-cancel-btn'),migrateTitle=$('migrate-title'),migratePromptBox=$('migrate-prompt-box'),migrateStep1=$('migrate-step1'),migrateStep2=$('migrate-step2'),migrateCloseX=$('migrate-close-x');
const modal=$('settings-modal'),backdrop=$('settings-backdrop'),dragH=$('settings-drag-handle'),tooltipEl=$('tooltip');
const charCounterEl=$('char-counter'),charCounterText=$('char-counter-text'),charCounterTip=$('char-counter-tip');
const stopBtn=$('stop-button');
const contractionTag=$('contraction-tag'),contractionTip=$('contraction-tip');
const overclockToggle=$('overclock-toggle'),ocBackdrop=$('overclock-backdrop'),ocWarningText=$('oc-warning-text'),ocConfirmBtn=$('oc-confirm-btn'),ocCancelBtn=$('oc-cancel-btn');
let S={lang:ls('lang')||defs.lang,theme:ls('theme')||defs.theme,effects:ls('effects')||defs.effects,textSize:ls('textsize')||defs.textSize,optResp:ls('optresp')||defs.optResp,uiOpt:ls('uiopt')||defs.uiOpt,kbSound:ls('kb-sound')||defs.kbSound,kbStyle:ls('kb-style')||defs.kbStyle,clickSound:ls('click-sound')||defs.clickSound,clickStyle:ls('click-style')||defs.clickStyle,aiSound:ls('ai-sound')||defs.aiSound,mode:ls('mode')||defs.mode,model:ls('model')||defs.model,wstyle:ls('wstyle')||defs.wstyle,gadget:ls('gadget')||defs.gadget,privateChat:false,aifont:ls('aifont')||defs.aifont,overclock:ls('overclock')||defs.overclock};
let messages=%%MESSAGES_JSON%%,settingsOpen=false,dragging=false,dragSX=0,dragSY=0,mSL=0,mST=0,audioCtx=null,ttTimer=null;
let sheets=[];
let isGenerating=false;
let abortController=null;
let activeTab='chat';
const coworkingContent={
  fr:{
    placeholder:"Décrivez votre idée et l'IA la réalisera",
    status:"Le Goat Coworking peut uniquement vous concevoir des applications qui nécessitent du code.",
    messages:[
      "Commencez à créer vos projets avec des IA en local, sans aucune limite.",
      "Décrivez votre application et Le Goat Coworking posera la base technique.",
      "Passez d'une idée brute à une application codée avec une direction claire."
    ],
    desc:""
  },
  en:{
    placeholder:"Describe your idea and the AI will build it",
    status:"The Goat Coworking can only design applications that require code.",
    messages:[
      "Start building your projects with local AI, without limits.",
      "Describe your app and Goat Coworking will shape the technical base.",
      "Move from a raw idea to a coded application with a clear direction."
    ],
    desc:""
  },
  es:{
    placeholder:"Describa su idea y la IA la realizará",
    status:"Goat Coworking solo puede diseñar aplicaciones que requieran código.",
    messages:[
      "Empiece a crear sus proyectos con IA local, sin límites.",
      "Describa su aplicación y Goat Coworking definirá la base técnica.",
      "Pase de una idea inicial a una aplicación codificada con una dirección clara."
    ],
    desc:""
  }
};
function t(k){return(T[S.lang]||T[defs.lang]||{})[k]||(T[defs.lang]||{})[k]||k}
function appTitle(){return titleByLang[S.lang]||titleByLang[defs.lang]}
function esc(s){return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#039;')}
// Audio
function ensureAudio(){if(audioCtx)return audioCtx;const A=window.AudioContext||window.webkitAudioContext;if(!A)return null;audioCtx=new A();return audioCtx}
function tone(f,d,type,g,det){const c=ensureAudio();if(!c)return;if(c.state==='suspended')c.resume().catch(()=>{});const o=c.createOscillator(),a=c.createGain();o.type=type||'sine';o.frequency.value=f;o.detune.value=det||0;const n=c.currentTime;a.gain.setValueAtTime(.0001,n);a.gain.exponentialRampToValueAtTime(g||.1,n+.01);a.gain.exponentialRampToValueAtTime(.0001,n+d);o.connect(a);a.connect(c.destination);o.start(n);o.stop(n+d+.01)}
function playClick(){if(S.clickSound!=='on')return;if(S.clickStyle==='nebrise'){tone(260,.055,'sawtooth',.07);setTimeout(()=>tone(340,.045,'triangle',.05),22);return}tone(420,.06,'triangle',.08)}
function playSend(){if(S.clickSound!=='on')return;tone(600,.045,'sine',.10);setTimeout(()=>tone(820,.055,'sine',.08),35)}
function playAiReply(){if(S.aiSound!=='on')return;tone(520,.06,'sine',.085);setTimeout(()=>tone(680,.05,'sine',.07),40)}
let lastKS=0;function playKey(){if(S.kbSound!=='on')return;const n=performance.now();if(n-lastKS<22)return;lastKS=n;if(S.kbStyle==='aurela'){tone(320,.03,'triangle',.06);return}if(S.kbStyle==='verdrock'){tone(180,.025,'square',.045);return}if(S.kbStyle==='feryn'){tone(520,.02,'sine',.06,-12);setTimeout(()=>tone(520,.02,'sine',.05,14),18);return}tone(560,.02,'sine',.05)}
// Tooltips
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

// ── Model dropdown (ChatGPT style) ──
function renderModelDD(){
  modelCurrentLabel.textContent=t(models.find(m=>m.id===S.model).label_key);
  modelDDMenu.innerHTML='<div class="model-dd-header">'+esc(t('model_recent'))+'</div>'+models.map(m=>'<button type="button" class="model-dd-item'+(m.id===S.model?' selected':'')+'" data-model="'+esc(m.id)+'" role="menuitemradio"><div class="m-info"><span class="m-name">'+esc(t(m.label_key))+'</span><span class="m-desc">'+esc(t(m.desc_key))+'</span></div><span class="m-check">✓</span></button>').join('')+'<div class="model-dd-sep"></div>';
  modelDDMenu.querySelectorAll('[data-model]').forEach(b=>b.addEventListener('click',()=>{playClick();S.model=b.dataset.model;ls('model',S.model);enforceMode();renderModelDD();renderModes();updateModeUI();renderStyles();updateStyleUI();renderGadgets();updateGadgetUI();closeModelDD()}));
}
function openModelDD(){modelDDMenu.classList.add('open');modelTriggerBtn.setAttribute('aria-expanded','true');var tc=$('tab-chat');if(tc)tc.setAttribute('aria-expanded','true')}
function closeModelDD(){modelDDMenu.classList.remove('open');modelTriggerBtn.setAttribute('aria-expanded','false');var tc=$('tab-chat');if(tc)tc.setAttribute('aria-expanded','false')}
modelTriggerBtn.addEventListener('click',()=>{playClick();modelDDMenu.classList.contains('open')?closeModelDD():openModelDD()});

// ── Private Chat (mode incognito) ──
let themeBeforePrivate=null;
function enterPrivateChat(){S.privateChat=true;privateChatBtn.classList.add('active');themeBeforePrivate=S.theme;document.body.dataset.theme='dark';S.theme='dark';$$('[data-theme-value]').forEach(b=>b.classList.toggle('active',b.dataset.themeValue==='dark'));updateThemedLogos();messages=[];renderMessages();welcomeEl.textContent=t('private_chat_welcome');welcomeDesc.textContent=t('private_chat_welcome_desc');ta.value='';autoResize();statusEl.textContent=ST[S.lang]||ST[defs.lang];fetch('/api/new_chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})}).catch(()=>{})}
function exitPrivateChat(){S.privateChat=false;privateChatBtn.classList.remove('active');const restore=themeBeforePrivate||defs.theme;themeBeforePrivate=null;applyTheme(restore,false);refreshWelcomeContent()}
privateChatBtn.addEventListener('click',()=>{playClick();S.privateChat?exitPrivateChat():enterPrivateChat()});
function updatePrivateChatLabels(){$('pc-title').textContent=t('private_chat');$('pc-desc').textContent=t('private_chat_desc')}

// ── Modes ──
function isModeOff(id){if(S.model==='goat_code')return true;return S.optResp==='on'&&DM.includes(id)}
function isStyleOff(){return S.model==='goat_code'}
function enforceMode(){if(S.mode&&isModeOff(S.mode)){S.mode=S.model==='goat_code'?'':'fast';ls('mode',S.mode)}if(S.wstyle&&isStyleOff()){S.wstyle='';ls('wstyle',S.wstyle)}}
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
function renderMessages(){const last=messages.length-1;const dotsHtml='<div class="typing-dots"><span></span><span></span><span></span></div>';const isCode=S.model==='goat_code';msgBox.innerHTML=messages.map(([s,txt],i)=>{const e=esc(txt);const isLoading=txt==='\u2026';if(s!=='Vous'){let acts='';if(i===last&&!isLoading){acts='<div class="bubble-actions"><button type="button" class="bubble-action" data-action="regenerate" data-tooltip-key="tooltip_regenerate">'+esc(t('regenerate'))+'</button>';if(isCode){acts+='<button type="button" class="bubble-action" data-action="review">'+esc(t('review_code'))+'</button>';acts+='<button type="button" class="bubble-action" data-action="analyze">'+esc(t('analyze_code'))+'</button>';acts+='<button type="button" class="bubble-action" data-action="execute" data-tooltip-key="tooltip_execute_code">'+esc(t('execute_code'))+'</button>'}acts+='</div>'}return'<div class="message-row assistant"><div class="bubble">'+(isLoading?dotsHtml:e)+'</div>'+acts+'</div>'}return'<div class="message-row user"><div class="bubble">'+e+'</div></div>'}).join('');shell.classList.toggle('has-messages',messages.length>0);msgBox.scrollTop=msgBox.scrollHeight;msgBox.querySelectorAll('[data-action="regenerate"]').forEach(b=>{bindTip(b,'tooltip_regenerate');b.addEventListener('click',async()=>{playClick();statusEl.textContent='...';showStopBtn();abortController=new AbortController();try{const p=await apiRegen(abortController.signal);messages=p.messages;renderMessages();statusEl.textContent=ST[S.lang]||ST[defs.lang];playAiReply()}catch(e){if(e.name!=='AbortError')statusEl.textContent=e.message}finally{hideStopBtn()}})});msgBox.querySelectorAll('[data-action="review"]').forEach(b=>b.addEventListener('click',async()=>{playClick();statusEl.textContent='...';try{const p=await apiSend('Relis et vérifie le code que tu viens de générer.');messages=p.messages;renderMessages();statusEl.textContent=ST[S.lang]||ST[defs.lang];playAiReply()}catch(e){statusEl.textContent=e.message}}));msgBox.querySelectorAll('[data-action="analyze"]').forEach(b=>b.addEventListener('click',async()=>{playClick();statusEl.textContent='...';try{const p=await apiSend('Analyse en détail le code que tu viens de générer : structure, complexité, points forts et points faibles.');messages=p.messages;renderMessages();statusEl.textContent=ST[S.lang]||ST[defs.lang];playAiReply()}catch(e){statusEl.textContent=e.message}}));msgBox.querySelectorAll('[data-action="execute"]').forEach(b=>{bindTip(b,'tooltip_execute_code');b.addEventListener('click',async()=>{playClick();statusEl.textContent='...';try{const p=await apiSend('Exécute en simulation le code que tu viens de générer et dis-moi si il devrait fonctionner correctement.');messages=p.messages;renderMessages();statusEl.textContent=ST[S.lang]||ST[defs.lang];playAiReply()}catch(e){statusEl.textContent=e.message}})})}
let resizeRAF=null;function autoResize(){if(resizeRAF)cancelAnimationFrame(resizeRAF);resizeRAF=requestAnimationFrame(()=>{ta.style.height='auto';ta.style.height=Math.min(ta.scrollHeight,180)+'px'})}

// ── Settings ──
function resetModal(){modal.style.left='50%';modal.style.top='50%';modal.style.transform='translate(-50%,-50%)'}
function openSettings(){playClick();if(settingsOpen)return;settingsOpen=true;resetModal();backdrop.hidden=false;modal.hidden=false;requestAnimationFrame(()=>{backdrop.classList.add('open');modal.classList.add('open')})}
function closeSettings(){playClick();if(!settingsOpen)return;settingsOpen=false;backdrop.classList.remove('open');modal.classList.remove('open');setTimeout(()=>{if(!settingsOpen){backdrop.hidden=true;modal.hidden=true;resetModal()}},180)}
function showTab(id){$$('[data-settings-tab]').forEach(t=>t.classList.toggle('active',t.dataset.settingsTab===id));$$('[data-settings-content]').forEach(s=>s.classList.toggle('active',s.dataset.settingsContent===id))}
function startDrag(e){if(innerWidth<=900)return;if(e.target.closest('button'))return;const r=modal.getBoundingClientRect();modal.style.left=r.left+'px';modal.style.top=r.top+'px';modal.style.transform='none';dragging=true;dragSX=e.clientX;dragSY=e.clientY;mSL=r.left;mST=r.top;e.preventDefault()}
function onDrag(e){if(!dragging)return;modal.style.left=Math.max(12,mSL+(e.clientX-dragSX))+'px';modal.style.top=Math.max(12,mST+(e.clientY-dragSY))+'px'}

// ── Apply settings (UI opt auto-disable quand on réactive un son) ──
function apply(key,val,lsKey,sound){if(sound!==false)playClick();S[key]=val;ls(lsKey||key,val)}
function checkUiOptOff(){if(S.uiOpt==='on'){S.uiOpt='off';ls('uiopt','off');updatePerf()}}
function applyLang(l,snd){apply('lang',['fr','en','es'].includes(l)?l:defs.lang,'lang',snd);document.documentElement.lang=S.lang;$$('[data-language-value]').forEach(b=>b.classList.toggle('active',b.dataset.languageValue===S.lang));applyTranslations()}
function updateThemedLogos(){const isDark=S.theme==='dark';const mainLogo=$('main-logo');if(mainLogo)mainLogo.src=isDark?mainLogo.dataset.dark:mainLogo.dataset.light;const goatLogo=$('goatistique-logo');if(goatLogo)goatLogo.src=isDark?goatLogo.dataset.dark:goatLogo.dataset.light}
function applyTheme(v,snd){if(S.privateChat)return;apply('theme',v==='dark'?'dark':'light','theme',snd);document.body.dataset.theme=S.theme;$$('[data-theme-value]').forEach(b=>b.classList.toggle('active',b.dataset.themeValue===S.theme));updateThemedLogos()}
function applyEffects(v,snd){apply('effects',v==='off'?'off':'on','effects',snd);document.body.dataset.effects=S.effects;updatePerf()}
function applyTextSize(v,snd){apply('textSize',v==='large'?'large':'default','textsize',snd);document.body.dataset.textsize=S.textSize;$$('[data-textsize-value]').forEach(b=>b.classList.toggle('active',b.dataset.textsizeValue===S.textSize))}
function applyOptResp(v,snd){apply('optResp',v==='on'?'on':'off','optresp',snd);enforceMode();renderModes();updateModeUI();updatePerf()}
function applyUiOpt(v,snd){apply('uiOpt',v==='on'?'on':'off','uiopt',snd);if(S.uiOpt==='on'){applyEffects('off',false);applyKbSound('off',false);applyClickSound('off',false);applyAiSound('off',false)}updatePerf()}
function applyKbSound(v,snd){apply('kbSound',v==='on'?'on':'off','kb-sound',snd);$$('[data-kb-sound]').forEach(b=>b.classList.toggle('active',b.dataset.kbSound===S.kbSound));updateSndVis();if(v==='on')checkUiOptOff()}
function applyKbStyle(v,snd){apply('kbStyle',['bulle','aurela','verdrock','feryn'].includes(v)?v:'bulle','kb-style',snd);$$('[data-kb-style]').forEach(b=>b.classList.toggle('active',b.dataset.kbStyle===S.kbStyle))}
function applyClickSound(v,snd){apply('clickSound',v==='on'?'on':'off','click-sound',snd);$$('[data-click-sound]').forEach(b=>b.classList.toggle('active',b.dataset.clickSound===S.clickSound));updateSndVis();if(v==='on')checkUiOptOff()}
function applyClickStyle(v,snd){apply('clickStyle',['bulle','nebrise'].includes(v)?v:'bulle','click-style',snd);$$('[data-click-style]').forEach(b=>b.classList.toggle('active',b.dataset.clickStyle===S.clickStyle))}
function applyAiSound(v,snd){apply('aiSound',v==='on'?'on':'off','ai-sound',snd);$$('[data-ai-sound]').forEach(b=>b.classList.toggle('active',b.dataset.aiSound===S.aiSound));if(v==='on')checkUiOptOff()}
function updateSndVis(){const kr=$('keyboard-style-row'),cr=$('click-style-row');if(kr)kr.hidden=S.kbSound!=='on';if(cr)cr.hidden=S.clickSound!=='on'}
function updatePerf(){$('effects-state').textContent=S.effects==='off'?t('state_on'):t('state_off');$('responses-state').textContent=S.optResp==='on'?t('state_on'):t('state_off');$('uiopt-state').textContent=S.uiOpt==='on'?t('state_on'):t('state_off')}
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
  refreshWelcomeContent();
}
function setActiveTab(tab,refresh){
  activeTab=tab==='coworking'?'coworking':'chat';
  closeModelDD();
  closeMM();
  closeSM();
  if(refresh!==false)refreshWelcomeContent();
  updateTabUI();
}
function applyTranslations(){$$('[data-i18n]').forEach(n=>n.textContent=t(n.dataset.i18n));$$('[data-placeholder-key]').forEach(n=>n.placeholder=t(n.dataset.placeholderKey));$('settings-button-label').textContent=t('settings_label');$('newchat-button-label').textContent=t('new_chat');$('settings-version-value').textContent=appVersion;brandText.textContent=appTitle();plusAddSheet.textContent='📄 '+t('add_sheet');const mcb=$('migrate-copy-btn');if(mcb)mcb.textContent=t('migrate_copy');updatePrivateChatLabels();updateCharCounter();updateContraction();updatePerf();updateModeUI();renderModes();updateStyleUI();renderStyles();updateGadgetUI();renderGadgets();renderModelDD();updateTabUI();renderMessages()}
function persistPerso(){ls('firstname',$('user-firstname').value);ls('lastname',$('user-lastname').value);ls('tone',$('user-tone').value);ls('info',$('user-info').value)}
function loadPerso(){$('user-firstname').value=ls('firstname')||'';$('user-lastname').value=ls('lastname')||'';$('user-tone').value=ls('tone')||'';$('user-info').value=ls('info')||''}
// API
async function apiSend(msg,signal){const r=await fetch('/api/send',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:msg,mode:S.mode}),signal});const p=await r.json();if(!r.ok||!p.ok)throw new Error(p.error||'Erreur');return p}
async function apiRegen(signal){const r=await fetch('/api/regenerate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:S.mode}),signal});const p=await r.json();if(!r.ok||!p.ok)throw new Error(p.error||'Erreur');return p}
async function apiNewChat(){const r=await fetch('/api/new_chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})});const p=await r.json();if(!r.ok||!p.ok)throw new Error(p.error||'Erreur');return p}
// Events
form.addEventListener('submit',async e=>{e.preventDefault();const v=ta.value.trim();if(!v)return;playSend();statusEl.textContent='...';showStopBtn();abortController=new AbortController();messages.push(['Vous',v],[appTitle(),'…']);renderMessages();ta.value='';autoResize();updateCharCounter();try{const p=await apiSend(v,abortController.signal);messages=p.messages;renderMessages();statusEl.textContent=ST[S.lang]||ST[defs.lang];playAiReply()}catch(err){if(err.name==='AbortError'){if(messages.length&&messages[messages.length-1][1]==='…')messages.pop();renderMessages()}else{if(messages.length&&messages[messages.length-1][0]!=='Vous')messages[messages.length-1]=[appTitle(),'Erreur : '+err.message];renderMessages();statusEl.textContent=err.message}}finally{hideStopBtn();ta.focus()}});
modeTrigger.addEventListener('click',()=>{playClick();modeMenu.classList.contains('open')?closeMM():openMM()});
styleTrigger.addEventListener('click',()=>{playClick();styleMenu.classList.contains('open')?closeSM():openSM()});
/* gadgetTrigger.addEventListener('click',()=>{playClick();gadgetMenu.classList.contains('open')?closeGM():openGM()}); // desactive */
$('settings-button').addEventListener('click',openSettings);$('settings-close').addEventListener('click',closeSettings);backdrop.addEventListener('click',closeSettings);
dragH.addEventListener('mousedown',startDrag);document.addEventListener('mousemove',onDrag);document.addEventListener('mouseup',()=>{dragging=false});
$('newchat-button').addEventListener('click',async()=>{playClick();if(!confirm(t('new_chat_confirm')))return;statusEl.textContent='...';try{const p=await apiNewChat();messages=p.messages;refreshWelcomeContent();renderMessages();statusEl.textContent=activeTab==='coworking'?getCoworkingContent().status:(ST[S.lang]||ST[defs.lang]);ta.value='';autoResize();ta.focus()}catch(e){statusEl.textContent=e.message}});
$$('[data-settings-tab]').forEach(t=>t.addEventListener('click',()=>{playClick();showTab(t.dataset.settingsTab||'general')}));
$$('[data-language-value]').forEach(b=>b.addEventListener('click',()=>applyLang(b.dataset.languageValue)));
$$('[data-theme-value]').forEach(b=>b.addEventListener('click',()=>applyTheme(b.dataset.themeValue)));
$$('[data-textsize-value]').forEach(b=>b.addEventListener('click',()=>applyTextSize(b.dataset.textsizeValue)));
$$('[data-kb-sound]').forEach(b=>b.addEventListener('click',()=>applyKbSound(b.dataset.kbSound)));
$$('[data-kb-style]').forEach(b=>b.addEventListener('click',()=>applyKbStyle(b.dataset.kbStyle)));
$$('[data-click-sound]').forEach(b=>b.addEventListener('click',()=>applyClickSound(b.dataset.clickSound)));
$$('[data-click-style]').forEach(b=>b.addEventListener('click',()=>applyClickStyle(b.dataset.clickStyle)));
$$('[data-ai-sound]').forEach(b=>b.addEventListener('click',()=>applyAiSound(b.dataset.aiSound)));
$$('[data-aifont-value]').forEach(b=>b.addEventListener('click',()=>applyAiFont(b.dataset.aifontValue)));
$('toggle-effects-button').addEventListener('click',()=>applyEffects(S.effects==='on'?'off':'on'));
$('toggle-responses-button').addEventListener('click',()=>applyOptResp(S.optResp==='on'?'off':'on'));
$('toggle-uiopt-button').addEventListener('click',()=>applyUiOpt(S.uiOpt==='on'?'off':'on'));
['user-firstname','user-lastname','user-tone','user-info'].forEach(id=>$(id).addEventListener('input',persistPerso));
$('manage-memory-button').addEventListener('click',()=>{playClick();alert(t('soon'))});
$('manage-history-button').addEventListener('click',()=>{playClick();alert(t('soon'))});
$('release-ram-button').addEventListener('click',()=>{playClick();alert(t('soon'))});
$('update-info-button').addEventListener('click',()=>{playClick();alert(t('soon'))});
$('goat-dev-news-btn').addEventListener('click',()=>{playClick();alert(t('soon'))});
$('goat-dev-about-btn').addEventListener('click',()=>{playClick();alert(t('soon'))});
$('migrate-data-button').addEventListener('click',()=>{playClick();closeSettings();setTimeout(openMigrate,200)});
document.addEventListener('click',e=>{if(!(e.target instanceof Element))return;if(!modeMenu.contains(e.target)&&!modeTrigger.contains(e.target))closeMM();if(!styleMenu.contains(e.target)&&!styleTrigger.contains(e.target))closeSM();if(!gadgetMenu.contains(e.target)&&!gadgetTrigger.contains(e.target))closeGM();if(!modelDDMenu.contains(e.target)&&!modelTriggerBtn.contains(e.target))closeModelDD();if(!plusMenu.contains(e.target)&&!composerPlus.contains(e.target))plusMenu.classList.remove('open')});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeMM();closeSM();closeGM();closeModelDD();closeSettings();closeMigrate();closeOverclockModal();hideTip()}});
ta.addEventListener('input',()=>{autoResize();enforceCharLimit();updateCharCounter()});
ta.addEventListener('keydown',e=>{const ign=new Set(['Shift','Control','Alt','Meta','CapsLock','Tab','ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Escape']);if(!ign.has(e.key)&&e.key!=='Enter')playKey();if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();form.requestSubmit()}});
$$('[data-tooltip-key]').forEach(el=>bindTip(el,el.dataset.tooltipKey));
// Init
loadPerso();showTab('general');
document.body.dataset.theme=S.theme;document.body.dataset.effects=S.effects;document.body.dataset.textsize=S.textSize;document.body.dataset.aifont=S.aifont;
applyLang(S.lang,false);applyTheme(S.theme,false);applyEffects(S.effects,false);applyTextSize(S.textSize,false);
applyOptResp(S.optResp,false);applyUiOpt(S.uiOpt,false);
applyKbSound(S.kbSound,false);applyKbStyle(S.kbStyle,false);applyClickSound(S.clickSound,false);applyClickStyle(S.clickStyle,false);applyAiSound(S.aiSound,false);
updateSndVis();enforceMode();renderModes();updateModeUI();renderStyles();updateStyleUI();renderGadgets();updateGadgetUI();renderModelDD();updatePrivateChatLabels();updateThemedLogos();autoResize();renderMessages();renderSheets();updatePerf();
applyAiFont(S.aifont,false);updateOverclockUI();updateCharCounter();
setActiveTab(activeTab,false);ta.focus();

// ── Top Tab Bar (Chat / Goat Coworking) ──
if(tabChat){
  tabChat.addEventListener('click',()=>{
    playClick();
    if(activeTab!=='chat'){
      setActiveTab('chat',true);
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
    setActiveTab('coworking',true);
  });
}
// Fermer le model dropdown quand on clique ailleurs
document.addEventListener('click',function(e){if(tabChat&&modelDDMenu&&!tabChat.contains(e.target)&&!modelDDMenu.contains(e.target)){modelDDMenu.classList.remove('open');tabChat.setAttribute('aria-expanded','false')}});

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
        "%%MIGRATION_PROMPT_JSON%%": json.dumps(cfg.MIGRATION_PROMPT, ensure_ascii=False),
        "%%SHEET_LIMITS_JSON%%": json.dumps(cfg.SHEET_LIMITS, ensure_ascii=False),
        "%%STORAGE_PREFIX_JSON%%": json.dumps(cfg.STORAGE_PREFIX),
        "%%MESSAGES_JSON%%": json.dumps(list(messages), ensure_ascii=False),
    }
    for k, v in replacements.items():
        tpl = tpl.replace(k, v)
    return tpl


# ============================================================
# Serveur HTTP
# ============================================================

class GoatWebApp:
    def __init__(self) -> None:
        self.session = ChatSession()
        self.logo_uri = LogoLoader.get_data_uri()
        self.themed_logos = LogoLoader.get_themed_logos()

    def render_index(self) -> str:
        return build_index_html(self.logo_uri, self.session.messages, self.themed_logos)

    def submit_message(self, message: str, mode: str = "") -> dict:
        reply = self.session.submit(message, mode)
        if not reply:
            return {"ok": False, "error": "Veuillez saisir un message."}
        return {"ok": True, "reply": reply, "messages": self.session.messages}

    def regenerate(self, mode: str = "") -> dict:
        reply = self.session.regenerate(mode)
        if not reply:
            return {"ok": False, "error": "Aucun message à relancer."}
        return {"ok": True, "reply": reply, "messages": self.session.messages}

    def new_chat(self) -> dict:
        self.session.reset()
        return {"ok": True, "messages": self.session.messages}


class GoatHTTPServer(ThreadingHTTPServer):
    def __init__(self, addr, handler_cls, app: GoatWebApp):
        super().__init__(addr, handler_cls)
        self.app = app


class GoatRequestHandler(BaseHTTPRequestHandler):
    server: GoatHTTPServer

    def log_message(self, fmt, *args): pass

    def _send(self, body: str, status: int = 200, ct: str = "text/html; charset=utf-8") -> None:
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ct)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, payload: dict, status: int = 200) -> None:
        self._send(json.dumps(payload, ensure_ascii=False), status, "application/json; charset=utf-8")

    def do_GET(self) -> None:
        if self.path == "/":
            self._send(self.server.app.render_index())
        elif self.path == "/api/history":
            self._json({"ok": True, "messages": self.server.app.session.messages})
        elif self.path in {"/favicon.ico", "/favicon.png"}:
            self.send_response(204); self.end_headers()
        else:
            self._json({"ok": False, "error": "Not found."}, 404)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
            if not isinstance(payload, dict): payload = {}
        except json.JSONDecodeError:
            self._json({"ok": False, "error": "JSON invalide."}, 400); return
        handlers = {
            "/api/send": lambda: self.server.app.submit_message(str(payload.get("message", "")), str(payload.get("mode", ""))),
            "/api/regenerate": lambda: self.server.app.regenerate(str(payload.get("mode", ""))),
            "/api/new_chat": lambda: self.server.app.new_chat(),
        }
        fn = handlers.get(self.path)
        if fn:
            result = fn()
            self._json(result, 200 if result.get("ok") else 400)
        else:
            self._json({"ok": False, "error": "Not found."}, 404)


# ============================================================
# Tests
# ============================================================

class TestChatSession(unittest.TestCase):
    def test_normalize(self):
        s = ChatSession()
        s.submit("  Bonjour   Le Goat  ")
        self.assertEqual(s.messages[0], ("Vous", "Bonjour Le Goat"))

    def test_empty_ignored(self):
        s = ChatSession()
        self.assertEqual(s.submit("   "), "")


class TestLogo(unittest.TestCase):
    def test_fallback(self):
        uri = LogoLoader.get_data_uri([Path("/no/such/file")])
        self.assertTrue(uri.startswith("data:image/svg+xml,"))


def run_tests() -> None:
    suite = unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestChatSession))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(TestLogo))
    r = unittest.TextTestRunner(verbosity=2).run(suite)
    if not r.wasSuccessful():
        raise SystemExit(1)


# ============================================================
# Main
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Le Goat — Interface desktop native")
    parser.add_argument("--host", default=AppConfig.HOST)
    parser.add_argument("--port", type=int, default=AppConfig.PORT)
    parser.add_argument("--no-browser", action="store_true", help="Mode serveur pur (pas de fenêtre)")
    parser.add_argument("--browser", action="store_true", help="Ouvrir dans le navigateur au lieu de la fenêtre native")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()
    if args.test:
        run_tests()
        return
    app = GoatWebApp()
    server = GoatHTTPServer((args.host, args.port), GoatRequestHandler, app)
    url = f"http://{args.host}:{args.port}"
    print(f"Le Goat lancé sur {url}")

    # Lancer le serveur HTTP dans un thread daemon
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    if args.no_browser:
        # Mode serveur pur — on bloque sur le thread principal
        try:
            server_thread.join()
        except KeyboardInterrupt:
            print("Arrêt du serveur Le Goat.")
        finally:
            server.server_close()
    elif args.browser or webview is None:
        # Fallback navigateur si pywebview absent ou demandé
        import webbrowser
        if webview is None:
            print("⚠ pywebview non installé — ouverture dans le navigateur.")
            print("  Pour la fenêtre native : pip install pywebview")
        webbrowser.open(url)
        try:
            server_thread.join()
        except KeyboardInterrupt:
            print("Arrêt du serveur Le Goat.")
        finally:
            server.server_close()
    else:
        # Mode desktop natif avec pywebview
        window = webview.create_window(
            AppConfig.DEFAULT_TITLE,
            url,
            width=1280,
            height=820,
            min_size=(800, 500),
            resizable=True,
            text_select=True,
        )
        # webview.start() bloque le thread principal jusqu'à fermeture de la fenêtre
        try:
            webview.start(debug=False)
        except KeyboardInterrupt:
            pass
        finally:
            print("Arrêt du serveur Le Goat.")
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()