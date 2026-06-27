# -*- coding: utf-8 -*-
"""Point d'entree CLI : analyse des arguments et lancement."""
from __future__ import annotations

import argparse
import threading
from pathlib import Path

try:
    import webview
except ImportError:
    webview = None

try:
    from PIL import Image
except Exception:
    Image = None

from .config import AppConfig
from .assets import LogoLoader
from .server import GoatWebApp, GoatHTTPServer, GoatRequestHandler
from .tests import run_tests

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

