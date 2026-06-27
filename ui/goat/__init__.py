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

Note de maintenance (2026-06-10) : corrections Lumen Mirror (menus fermés
affichés, position du bouton Chat Privé, jauge de transparence) + effets
d'envoi / micro, style d'écriture "Découverte", accent orange, badge BETA.
"""
