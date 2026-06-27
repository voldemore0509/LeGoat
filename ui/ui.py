# -*- coding: utf-8 -*-
"""
Le Goat — point d'entree de l'application.

L'application est desormais organisee en package ``goat/`` :

    goat/
      config.py       Configuration centrale (AppConfig)
      translations.py Traductions fr/en/es (TranslationManager)
      chat.py         Type Message, generate_reply, ChatSession
      assets.py       Chargement logos/images (LogoLoader)
      safety.py       Verification NSFW des images de profil
      pdf_export.py   Generation du PDF de profil
      template.py     Assemblage du HTML + build_index_html
      server.py       Serveur HTTP local (GoatWebApp / handler)
      tests.py        Tests unitaires
      cli.py          main() — analyse CLI + lancement
      web/            Front separe : index.html, styles.css, app.js

Lancement :
    python ui.py                fenetre native (pywebview)
    python ui.py --browser      ouvrir dans le navigateur
    python ui.py --no-browser   serveur pur (API uniquement)
    python ui.py --test         lancer la suite de tests
"""
from goat.cli import main

if __name__ == "__main__":
    main()
