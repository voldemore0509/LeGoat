# -*- coding: utf-8 -*-
"""Verification de securite des images de profil.

⚠️ CHANGEMENT DE POLITIQUE (voir bloc commenté plus bas) :
   - L'ancien vérificateur de contenu *sexuel adulte* (NSFW) a été
     DÉSACTIVÉ (mis en commentaire, conservé pour référence).
   - Il est remplacé par un détecteur de contenu *pédocriminel* (CSAM) :
     images mettant en scène des mineurs nus ou sexualisés.

   À LIRE — détection CSAM fiable :
   La détection sérieuse de CSAM ne se fait PAS avec un classifieur
   « nudité d'enfant » maison : (1) les données d'entraînement sont
   illégales à détenir, (2) un tel modèle est massivement faillible
   (faux positifs/négatifs). L'état de l'art repose sur le HASH-MATCHING
   contre des bases de hash de CSAM connus, opérées par des tiers vérifiés :
       • Microsoft PhotoDNA            (https://www.microsoft.com/photodna)
       • Google CSAI Match / Content Safety API
       • Thorn — Safer                 (https://safer.io)
       • Cloudflare CSAM Scanning Tool
       • NCMEC (signalement obligatoire aux US ; en France : Pharos /
         point-contact.net).
   Ce module délègue donc la décision à un service externe configuré via
   les variables d'environnement GOAT_CSAM_API_URL / GOAT_CSAM_API_KEY.

   ⚖️ OBLIGATION LÉGALE : si un contenu est détecté comme CSAM avéré,
   l'hébergeur a, dans la plupart des juridictions, l'obligation de le
   signaler aux autorités compétentes (NCMEC / Pharos) et de conserver
   les éléments selon la procédure légale — pas seulement de refuser
   l'upload. Voir _report_csam_hook() ci-dessous.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re

try:
    from PIL import Image
except Exception:
    Image = None

try:
    import urllib.request
    import urllib.error
except Exception:  # pragma: no cover
    urllib = None  # type: ignore

# ============================================================
# Messages utilisateur
# ============================================================

PROFILE_IMAGE_REJECTION_MESSAGE = "Désolé, nous ne pouvons pas mettre votre photo de profil en raison de nos règles d'utilisation."

# ============================================================
# 1) Pré-filtre sur le NOM DE FICHIER
# ============================================================

# ── Tokens CSAM (TOLÉRANCE ZÉRO) — ACTIFS ──
# Tout fichier contenant l'un de ces tokens dans son nom est rejeté
# AVANT toute analyse d'image. C'est la première ligne de défense.
CSAM_NAME_TOKENS = {
    'loli', 'lolicon', 'shotacon', 'shota', 'pedo', 'pedophil',
    'pedoporno', 'pedopornograph', 'childporn', 'child_porn',
    'childabuse', 'child_abuse', 'childsex', 'child_sex',
    'cp', 'jailbait', 'underage', 'preteen', 'minors', 'minor_nude',
    'kidporn', 'kidsex', 'infantil',
}

CSAM_NAME_PATTERNS = [
    re.compile(
        r'\b(?:loli|lolicon|shotacon|shota|pedo|pedophil|pedoporno'
        r'|child\s*porn|child\s*abuse|child\s*sex|kid\s*porn|cp'
        r'|jailbait|underage|preteen|infantil'
        r'|(?:minor|child|kid|enfant|gamin)s?\s*(?:sex|nude|naked|porn|nu|nue))\b',
        re.I,
    ),
]

# ── Tokens violence / haine — conservés ACTIFS ──
# (Hors périmètre du « vérificateur sexuel » : on ne les retire pas.)
VIOLENCE_HATE_NAME_TOKENS = {
    'gore', 'guro', 'snuff', 'beheading', 'decapitat', 'torture',
    'mutilat', 'dismember', 'massacre', 'execution',
    'nazi', 'whitepower', 'white_power', 'kkk', 'supremacist', 'terroris',
}

VIOLENCE_HATE_NAME_PATTERNS = [
    re.compile(
        r'\b(?:gore|guro|snuff|beheading|decapitat|torture|mutilat'
        r'|dismember|massacre|execution'
        r'|nazi|white\s*power|kkk|supremacist|terroris)\b',
        re.I,
    ),
]

# ============================================================
# 2) Détection VISUELLE de CSAM (déléguée à un service externe)
# ============================================================

CSAM_API_URL_ENV = 'GOAT_CSAM_API_URL'
CSAM_API_KEY_ENV = 'GOAT_CSAM_API_KEY'
# Si "1", on REFUSE l'image quand aucun service CSAM n'est joignable
# (fail-closed). Par défaut "0" : on laisse passer la couche visuelle mais
# le pré-filtre par nom de fichier reste actif.
CSAM_FAIL_CLOSED_ENV = 'GOAT_CSAM_FAIL_CLOSED'


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


def _report_csam_hook(filename: str, verdict: dict) -> None:
    """Point d'extension pour le signalement légal d'un CSAM avéré.

    À implémenter selon la juridiction de l'hébergeur (NCMEC CyberTipline
    aux US, Pharos / point-contact.net en France). On NE journalise PAS
    l'image elle-même ici ; on délègue au service conforme. Laisser un
    no-op silencieux par défaut pour ne pas bloquer le flux applicatif.
    """
    # Exemple (à activer en production avec un canal conforme) :
    #   _forward_to_ncmec(filename, verdict)
    return None


def _csam_detection_check(filename: str, data_url: str) -> tuple[bool, bool]:
    """Interroge un service externe de détection CSAM (hash-matching).

    Retour : (is_csam, verified)
      - is_csam  True  → contenu identifié comme CSAM → REJET.
      - verified True  → un service a réellement statué.
                  False → aucun service configuré/joignable : on n'a PAS pu
                          statuer (la décision revient au mode fail-closed).

    Contrat attendu de l'API (JSON) :
        POST {url}
        Header  Authorization: Bearer {key}
        Body    {"image_b64": "<base64 brut, sans préfixe data:>"}
        Réponse {"is_csam": true|false, ...}
    """
    url = os.getenv(CSAM_API_URL_ENV, '').strip()
    key = os.getenv(CSAM_API_KEY_ENV, '').strip()
    if not url or urllib is None:
        return False, False
    try:
        raw = _decode_data_url(data_url)
        payload = json.dumps({
            'image_b64': base64.b64encode(raw).decode('ascii'),
            'filename': filename or '',
        }).encode('utf-8')
        req = urllib.request.Request(url, data=payload, method='POST')
        req.add_header('Content-Type', 'application/json')
        if key:
            req.add_header('Authorization', 'Bearer ' + key)
        with urllib.request.urlopen(req, timeout=8) as resp:
            body = resp.read().decode('utf-8', 'replace')
        data = json.loads(body or '{}')
        is_csam = bool(data.get('is_csam') or data.get('match') or data.get('flagged'))
        if is_csam:
            _report_csam_hook(filename, data if isinstance(data, dict) else {})
        return is_csam, True
    except Exception:
        # Service injoignable / réponse invalide : impossible de statuer.
        return False, False


def _local_image_safety_check(filename: str, data_url: str) -> tuple[bool, str]:
    """Vérifie une image de profil.

    Politique actuelle :
      1. Rejet immédiat si le nom de fichier contient un token CSAM
         ou violence/haine.
      2. Détection visuelle CSAM via service externe (hash-matching).
      3. Le contenu *sexuel adulte* n'est PLUS bloqué (détecteur NSFW
         désactivé — voir bloc commenté en fin de fichier).
    """
    lower_name = (filename or '').lower()

    # 1) Pré-filtre nom de fichier — CSAM (tolérance zéro)
    if any(token in lower_name for token in CSAM_NAME_TOKENS):
        return False, PROFILE_IMAGE_REJECTION_MESSAGE
    for pattern in CSAM_NAME_PATTERNS:
        if pattern.search(lower_name):
            return False, PROFILE_IMAGE_REJECTION_MESSAGE

    # 1bis) Pré-filtre nom de fichier — violence / haine (conservé)
    if any(token in lower_name for token in VIOLENCE_HATE_NAME_TOKENS):
        return False, PROFILE_IMAGE_REJECTION_MESSAGE
    for pattern in VIOLENCE_HATE_NAME_PATTERNS:
        if pattern.search(lower_name):
            return False, PROFILE_IMAGE_REJECTION_MESSAGE

    if Image is None:
        return False, "Pillow est requis pour l'analyse locale des images."

    # 2) Détection visuelle CSAM
    try:
        image = _image_from_data_url(data_url).convert('RGB')
        if image.width < 64 or image.height < 64:
            return False, 'Image trop petite ou invalide.'
    except Exception:
        return False, 'Image invalide ou non lisible.'

    is_csam, verified = _csam_detection_check(filename, data_url)
    if is_csam:
        return False, PROFILE_IMAGE_REJECTION_MESSAGE
    if not verified and os.getenv(CSAM_FAIL_CLOSED_ENV, '0').strip() == '1':
        # Aucun service CSAM joignable et politique stricte demandée.
        return False, "Vérification de sécurité indisponible pour le moment."

    return True, ''


# ============================================================================
# ============================================================================
#   ANCIEN VÉRIFICATEUR DE CONTENU SEXUEL (NSFW) — DÉSACTIVÉ
#   Conservé en commentaire à la demande. Pour le réactiver, décommenter
#   ce bloc et rebrancher _classify_with_local_model / _fallback_visual_nsfw_score
#   dans _local_image_safety_check.
# ============================================================================
# ============================================================================
#
# # ── Tokens de noms de fichiers sexuels (adulte) ──
# RISKY_IMAGE_NAME_TOKENS = {
#     'porn', 'porno', 'pornography', 'pornographique', 'nsfw',
#     'sex', 'sexe', 'sexual', 'sexuel', 'sexuelle',
#     'nude', 'nudity', 'nudes', 'naked', 'nu', 'nue',
#     'xxx', 'hentai', 'rule34', 'r34', 'onlyfans', 'fansly',
#     'lewd', 'explicit', 'fetish', 'fetiche', 'orgasm', 'orgasme',
#     'erotic', 'erotique', 'masturbat', 'ejaculat', 'penetrat',
#     'gangbang', 'blowjob', 'handjob', 'creampie', 'cumshot',
#     'stripteuse', 'stripper', 'escort', 'prostitut',
# }
#
# RISKY_IMAGE_TEXT_PATTERNS = [
#     re.compile(
#         r'\b(?:porn|porno|pornograph|nsfw|nude|nudity|nudes|naked|xxx|hentai'
#         r'|rule\s*34|r34|onlyfans|fansly|lewd|explicit|fetish|fetiche'
#         r'|erotic|erotique|orgasm|masturbat|ejaculat|penetrat'
#         r'|gangbang|blowjob|handjob|creampie|cumshot|stripteuse|stripper'
#         r'|escort|prostitut)\b', re.I
#     ),
# ]
#
# _NSFW_MODEL_CACHE = None
# _NSFW_MODEL_CACHE_FAILED = False
#
# HARD_NSFW_LABEL_TOKENS = (
#     'nsfw', 'explicit', 'sexual', 'porn', 'pornography', 'nudity', 'nude',
#     'hentai', 'xxx', 'graphic nudity', 'graphic sexual', 'adult content',
#     'exposed genitalia', 'exposed breast', 'full nudity',
#     'gore', 'violence', 'blood', 'disturbing',
# )
#
# SOFT_NSFW_LABEL_TOKENS = (
#     'sexy', 'suggestive', 'adult', 'erotic', 'lingerie',
#     'provocative', 'seductive', 'risque', 'racy',
# )
#
# TOLERATED_LABEL_TOKENS = (
#     'bikini', 'swimsuit', 'swimwear', 'maillot', 'bathing suit',
#     'beachwear', 'beach', 'pool', 'swimming',
# )
#
# def _normalize_label(label: str) -> str:
#     value = re.sub(r'[^a-z0-9]+', ' ', str(label or '').lower()).strip()
#     return re.sub(r'\s+', ' ', value)
#
# def _get_local_nsfw_classifier():
#     global _NSFW_MODEL_CACHE, _NSFW_MODEL_CACHE_FAILED
#     if _NSFW_MODEL_CACHE is not None:
#         return _NSFW_MODEL_CACHE
#     if _NSFW_MODEL_CACHE_FAILED:
#         return None
#     model_path = os.getenv('GOAT_NSFW_MODEL_PATH', '').strip()
#     if not model_path:
#         _NSFW_MODEL_CACHE_FAILED = True
#         return None
#     try:
#         from transformers import pipeline  # type: ignore
#         _NSFW_MODEL_CACHE = pipeline(
#             'image-classification',
#             model=model_path,
#             image_processor=model_path,
#             local_files_only=True,
#         )
#         return _NSFW_MODEL_CACHE
#     except Exception:
#         _NSFW_MODEL_CACHE_FAILED = True
#         return None
#
# def _classify_with_local_model(image):
#     classifier = _get_local_nsfw_classifier()
#     if classifier is None:
#         return None
#     try:
#         results = classifier(image)
#     except Exception:
#         return None
#     hard_risk = 0.0
#     soft_risk = 0.0
#     tolerated_score = 0.0
#     for item in results or []:
#         label = _normalize_label(item.get('label'))
#         score = float(item.get('score', 0.0) or 0.0)
#         if any(token in label for token in HARD_NSFW_LABEL_TOKENS):
#             hard_risk = max(hard_risk, score)
#         elif any(token in label for token in SOFT_NSFW_LABEL_TOKENS):
#             soft_risk = max(soft_risk, score)
#         if any(token in label for token in TOLERATED_LABEL_TOKENS):
#             tolerated_score = max(tolerated_score, score)
#     if tolerated_score > 0.5 and hard_risk < 0.30:
#         return True, max(hard_risk, soft_risk)
#     safe = hard_risk < 0.45 and soft_risk < 0.80
#     return safe, max(hard_risk, soft_risk)
#
# def _fallback_visual_nsfw_score(image) -> float:
#     """Heuristique couleur (peau/rouge/sombre) — désactivée.
#     Repérage NSFW adulte uniquement ; sans valeur pour la détection CSAM."""
#     sample = image.copy().convert('RGB')
#     sample.thumbnail((256, 256))
#     pixels = sample.load()
#     total = max(1, sample.width * sample.height)
#     skin_like = 0
#     for y in range(sample.height):
#         for x in range(sample.width):
#             r, g, b = pixels[x, y]
#             is_skin = (r > 100 and g > 50 and b > 20
#                        and r > g and r > b
#                        and (r - g) > 25 and (r - b) > 35
#                        and (r + g + b) < 650)
#             if is_skin:
#                 skin_like += 1
#     skin_ratio = skin_like / total
#     return max(0.0, min(1.0, (skin_ratio - 0.42) * 1.2 if skin_ratio > 0.42 else 0.0))
#
# ============================================================================
#   FIN DU BLOC DÉSACTIVÉ
# ============================================================================
