# main.py
import json
import urllib.error
import urllib.request
from threading import Lock

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "mistral"


class MinouSetup:
    def __init__(self):
        self._lock = Lock()
        self.history: list[tuple[str, str]] = []
        self.degre = 0.5
        self.tokens = 500

    def apply_mode(self, mode: str = "none") -> None:
        presets = {
            "none": (0.5, 500),
            "fast": (0.2, 180),
            "reflection": (0.35, 900),
            "research_in_data": (0.3, 1100),
            "research_in_memory": (0.4, 1200),
            "creativity": (1.0, 1200),
        }
        self.degre, self.tokens = presets.get(mode, presets["none"])

    def _mode_instruction(self, mode: str) -> str:
        instructions = {
            "none": "Mode standard.",
            "fast": "Répondez vite, de façon directe et compacte.",
            "reflection": "Prenez un peu plus de recul et structurez la réponse.",
            "research_in_data": "Utilisez un style analytique, comme si vous exploitiez des documents internes.",
            "research_in_memory": "Tenez compte davantage du contexte conversationnel précédent.",
            "creativity": "Répondez avec plus de créativité tout en restant utile et cohérent.",
        }
        return instructions.get(mode, instructions["none"])

    def _build_prompt(self, user_message: str, mode: str) -> str:
        history_text = ""
        for user_text, assistant_text in self.history[-8:]:
            history_text += f"Human: {user_text}\nAI: {assistant_text}\n"

        system_block = (
            "You are Goat, a helpful AI assistant.\n"
            "Answer in the same language as the user.\n"
            "Be useful, clear, and well-structured.\n"
            f"{self._mode_instruction(mode)}\n"
        )

        return f"{system_block}\n{history_text}Human: {user_message}\nAI:"

    def _call_ollama(self, prompt: str) -> str:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.degre,
                "top_p": min(1.0, self.degre + 0.3),
                "num_predict": self.tokens,
            },
        }

        request = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw)
        except urllib.error.HTTPError as exc:
            try:
                details = exc.read().decode("utf-8", errors="ignore")
            except Exception:
                details = ""
            raise RuntimeError(
                f"Erreur HTTP Ollama {exc.code}. Détails: {details or exc.reason}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                "Impossible de joindre Ollama sur http://127.0.0.1:11434. "
                "Vérifiez qu'Ollama est bien lancé localement."
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"Erreur inattendue côté backend Ollama : {exc}") from exc

        reply = str(data.get("response", "")).strip()
        if not reply:
            raise RuntimeError("Ollama a répondu, mais le texte retourné est vide.")
        return reply

    def generate_reply(self, user_message: str, mode: str = "none") -> str:
        cleaned = " ".join(str(user_message).strip().split())
        if not cleaned:
            return ""

        with self._lock:
            self.apply_mode(mode)
            prompt = self._build_prompt(cleaned, mode)
            reply = self._call_ollama(prompt)
            self.history.append((cleaned, reply))
            return reply

    def clear_memory(self) -> None:
        with self._lock:
            self.history.clear()


backend = MinouSetup()



def generate_reply(user_message: str, mode: str = "none") -> str:
    return backend.generate_reply(user_message, mode)


def clear_memory() -> None:
    backend.clear_memory()


if __name__ == "__main__":
    print("Minou CLI lancé. Tapez 'exit' pour quitter.")
    while True:
        user_message = input("Vous : ").strip()
        if user_message.lower() == "exit":
            print("Fermeture.")
            break

        try:
            reply = generate_reply(user_message)
            print("Minou :", reply)
        except Exception as exc:
            print("Erreur :", exc)