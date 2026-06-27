# -*- coding: utf-8 -*-
"""Assemblage du template HTML (front charge depuis goat/web/)."""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Dict, Iterable, Optional

from .config import AppConfig
from .translations import TranslationManager
from .chat import Message
from .assets import LogoLoader


# ============================================================
# Template HTML — assemblage du front (HTML + CSS + JS)
# ============================================================

_WEB = Path(__file__).resolve().parent / "web"


def _load_html_template() -> str:
    """
    Reconstruit le template HTML complet a partir des fichiers du dossier
    ``goat/web/`` :

      * ``index.html`` — squelette HTML, contient les marqueurs ``%%STYLES%%``
        et ``%%SCRIPT%%`` (et tous les ``%%...%%`` remplaces par build_index_html).
      * ``styles.css`` — feuille de style complete (injectee dans <style>).
      * ``app.js``     — logique UI vanilla JS (injectee dans <script>).

    Le resultat est identique a l'ancienne chaine monolithique : les marqueurs
    ``%%NOM%%`` restent intacts et sont resolus ensuite par build_index_html().
    """
    html_shell = (_WEB / "index.html").read_text(encoding="utf-8")
    css = (_WEB / "styles.css").read_text(encoding="utf-8")
    js = (_WEB / "app.js").read_text(encoding="utf-8")
    return html_shell.replace("%%STYLES%%", css).replace("%%SCRIPT%%", js)




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
        "%%DEFAULT_UI_STYLE_JSON%%": json.dumps(cfg.DEFAULT_UI_STYLE),
        "%%DEFAULT_GLASS_TRANSPARENCY_JSON%%": json.dumps(cfg.DEFAULT_GLASS_TRANSPARENCY),
        "%%DEFAULT_GLASS_TINT_JSON%%": json.dumps(cfg.DEFAULT_GLASS_TINT),
        "%%DEFAULT_PIXEL_BUTTONS_JSON%%": json.dumps(cfg.DEFAULT_PIXEL_BUTTONS),
        "%%DEFAULT_AI_TYPING_EFFECT_JSON%%": json.dumps(cfg.DEFAULT_AI_TYPING_EFFECT),
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
        "%%DEFAULT_UI_STYLE_JSON%%":         json.dumps(cfg.DEFAULT_UI_STYLE),
        "%%DEFAULT_GLASS_TRANSPARENCY_JSON%%": json.dumps(cfg.DEFAULT_GLASS_TRANSPARENCY),
        "%%DEFAULT_GLASS_TINT_JSON%%":       json.dumps(cfg.DEFAULT_GLASS_TINT),
        "%%DEFAULT_PIXEL_BUTTONS_JSON%%":    json.dumps(cfg.DEFAULT_PIXEL_BUTTONS),
        "%%DEFAULT_AI_TYPING_EFFECT_JSON%%": json.dumps(cfg.DEFAULT_AI_TYPING_EFFECT),
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



