# Le Goat — Architecture du code

L'application était auparavant contenue dans un unique `ui.py` (~6100 lignes).
Elle est désormais découpée en un package `goat/`, avec le front séparé du
backend. **Le comportement est strictement identique à l'original** : le HTML
généré est byte-pour-byte le même (hors les 3 évolutions demandées).

## Lancer l'application

```bash
python ui.py              # fenêtre native (pywebview)
python ui.py --browser    # ouvrir dans le navigateur
python ui.py --no-browser # serveur pur (API uniquement)
python ui.py --test       # lancer la suite de tests
```

## Arborescence

```
ui.py                  Point d'entrée mince (appelle goat.cli.main)
ui_original_backup.py  Sauvegarde de l'ancien fichier monolithique
goat/
  config.py        Configuration centrale (AppConfig)
  translations.py  Traductions fr / en / es (TranslationManager)
  chat.py          Type Message, generate_reply (stub IA), ChatSession
  assets.py        Chargement logos / images (LogoLoader)
  safety.py        Vérification NSFW des images de profil
  pdf_export.py    Génération du PDF de profil
  template.py      Assemblage du HTML + build_index_html
  server.py        Serveur HTTP local (GoatWebApp + handler)
  tests.py         Tests unitaires
  cli.py           main() — analyse des arguments + lancement
  web/
    index.html     Squelette HTML (marqueurs %%STYLES%% / %%SCRIPT%%)
    styles.css     Feuille de style complète
    app.js         Logique UI (vanilla JS)
```

### Comment le front est assemblé

`goat/template.py::_load_html_template()` lit les trois fichiers de `goat/web/`
et réinjecte `styles.css` dans `<style>` et `app.js` dans `<script>`. Les
marqueurs `%%NOM%%` (titre, traductions, valeurs par défaut…) sont ensuite
résolus par `build_index_html()`, exactement comme avant. La page reste servie
en mémoire — aucun fichier statique n'est exposé au client.

## Où modifier quoi

- **Un texte / une traduction** → `goat/translations.py` (3 langues).
- **Le style visuel** → `goat/web/styles.css`.
- **Le comportement de l'interface** → `goat/web/app.js`.
- **La structure HTML** → `goat/web/index.html`.
- **Un mode / modèle / style d'écriture** → `goat/config.py` (+ traductions).
- **Brancher l'IA** → implémenter `generate_reply()` dans `goat/chat.py`.

## Les 3 évolutions de cette révision

1. **Découpage** du fichier unique en package + front séparé (ci-dessus).
2. **« Liquid Glass » renommé en « Lumen Mirror »** dans toute l'interface
   (libellés, traductions, commentaires). L'identifiant technique interne
   reste `glass` pour ne rien casser.
3. **Lumen Reflex Boost** : nouvel interrupteur dans *Paramètres > Apparence*.
   Une fois activé, il coupe toutes les animations, transitions, flous, ombres
   et effets décoratifs (envoi, écriture caractère par caractère) pour
   l'interface la plus fluide possible. Les fonds d'écran sont conservés.
   Réversible : il neutralise les effets sans modifier vos autres réglages —
   il suffit de le désactiver pour tout retrouver à l'identique.
   Implémentation : attribut `data-reflex-boost` sur `<body>`, couche CSS
   dédiée (`styles.css`) et fonctions `applyReflexBoost` / `boostOn` (`app.js`).
