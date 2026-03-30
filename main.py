# main.py# Import necessary libraries
from langchain_core.messages import HumanMessage, AIMessage # Importing necessary classes for message handling
from langchain_classic.memory import ConversationBufferMemory
from langchain_ollama import OllamaLLM  # Importing the Ollama LLM for language model functionality
from langchain_core.prompts import ChatPromptTemplate # Importing prompt templates for structured conversation
import time #librebrie pour le temps
import sys  # (AJOUT) Besoin d'écrire/vider explicitement la sortie standard

# --- Config & utils RAG ------------------------------------------------------

from langchain_core.messages import HumanMessage, AIMessage
from langchain_classic.memory import ConversationBufferMemory
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
import time
import sys

class Minou_Setup:
    def __init__(self):
        self.degre = 0.1
        self.tokens = 600
        self.max_history_messages = 4  # garde seulement les 2 derniers échanges
        self.memory = ConversationBufferMemory(return_messages=True)
        self.prompt = ChatPromptTemplate.from_template("""
        You are The Goat.
        Answer briefly and directly by default.

        Conversation history:
        {history}

        User: {input}
        """)
        self.build_model()
        self.numberOfInteraction = 0
        self.displayInformation = 0

    def build_model(self):
        self.model = OllamaLLM(
            model="mistral-small:latest",
            model_kwargs={
                "temperature": self.degre,
                "top_p": 0.6,
                "num_predict": self.tokens,
                "num_ctx": 2048,
                "repeat_penalty": 1.0
            }
        )
        self.chain = self.prompt | self.model

    def reflection_mode(self):
        self.degre = 0.2
        self.tokens = 1024
        self.build_model()
        print("Mode Thinking activé — Réflexion plus longue, 1024 tokens.")

    def fast_mode(self):
        self.degre = 0.1
        self.tokens = 256
        self.build_model()
        print("Mode Fast activé — Réponses rapides, 256 tokens.")

    def maestro_mode(self):
        self.degre = 0.5
        self.tokens = 2048
        self.model = OllamaLLM(
            model="qwen3:30b",
            model_kwargs={
                "temperature": self.degre,
                "top_p": 0.7,
                "num_predict": self.tokens,
                "repeat_penalty": 1.1
            }
        )
        self.chain = self.prompt | self.model
        print("Mode Maestro activé — Gemma 3 27B, 2048 tokens.")

    def goat_code(self):
        self.degre = 0.3
        self.tokens = 1024
        self.model = OllamaLLM(
            model="qwen2.5-coder:14b",
            model_kwargs={
                "temperature": self.degre,
                "top_p": 0.7,
                "num_predict": self.tokens,
                "repeat_penalty": 1.1
            }
        )
        self.chain = self.prompt | self.model
        print("Mode Goat Code activé — qwen2.5-coder:14b.")

minou_setup = Minou_Setup()

class Cmd:

    def display_listOfCommande(self):   # Method to display the list of available commands
        print("List Commande :\n","clear = stop chat\n","degree = modify creativity level\n","info = display information about the AI\n","clear memory = Declining memory\n","display memory = Displays current memory\n","interaction = displays the number of interaction\n","korkmou --version = display the version of the AI")

    def displayInformationIA(self): # Method to display information about the AI
        print("Information sur l'IA :")
        print("degree : ",minou_setup.degre)
        print("Model : ",minou_setup.model)
        print("Memory : ",minou_setup.memory)
        print("Memory : ",minou_setup.memory)

    def clearMemory(self):
        minou_setup.memory.clear()

    def displayVersionKrokmou(self):
        print("Krokmou 1.0")  #Important permet de signialer si l'ain est bien récente

    def verify_ListOfCommande(self, commande):  # Method to verify and execute commands
        if commande == "exit":
            minou_setup.numberOfInteraction += 1
            return False
        elif commande == "list":
            self.display_listOfCommande()
            minou_setup.numberOfInteraction += 1
            return True
        elif commande == "info":
            self.displayInformationIA()
            minou_setup.numberOfInteraction += 1
            return True
        elif commande == "clear memory":
            if self.displayInformation == 0 :
                self.displayInformation = int(input("Voulez vous voir les information ? Y(1)/No(2) ? : "))
            if(self.displayInformation == 1):
                print("Memoire actuelle : ",self.memory)
                self.clearMemory()
                print("Memoire apres nettoyage : ",self.memory)
            else:
                self.clearMemory()
                print("Memoire Effacée")
            self.numberOfInteraction += 1
            return True
        elif commande == "display memory":
            print("Memoire actuelle : ",self.memory)
            self.displayInformation = 0
            minou_setup.numberOfInteraction += 1
            return True
        elif commande == "interaction":
            print("Nombre d'interactions : ", minou_setup.numberOfInteraction)
            minou_setup.numberOfInteraction += 1
            return True
        elif commande == "minou --version":
            self.displayVersionKrokmou()
            return True
        elif commande == "imaginator":
            choice = input("activation/désactivation du mode créatif ?\nOui/Non\n")
            return True
        elif commande == "thinking":
            minou_setup.thinking_mode()
            return True
        elif commande == "fast":
            minou_setup.fast_mode()
            return True
        elif commande == "maestro -mode-":
            minou_setup.maestro_mode()
            return True
        elif commande == "goat code":
            minou_setup.goat_code()
            return True


order = Cmd()

class ChatAgent:
    def __init__(self):
        self.numberOfInteraction = 0
        self.caracter_max = 1000

    def detection_coc(self,requete):
        if(len(requete) > self.caracter_max):
            print("contraction chat activate")
        else:
            print("contraction non activer")
    
    def chatBot(self):
        requete = input("You: ").strip()
        self.detection_coc(requete)
        cmd = order.verify_ListOfCommande(requete)
        if cmd is False:
            return False
        if cmd is True:
            return True

        # Charger l'historique depuis la mémoire LangChain
        history = minou_setup.memory.load_memory_variables({}).get("history", [])

        # Appel de la chain correctement (prompt attend: history + input)
        response = minou_setup.chain.invoke({"history": history, "input": requete})

        print("Goat :", response)

        # Sauvegarde dans la mémoire
        minou_setup.memory.save_context({"input": requete}, {"output": response})

        self.numberOfInteraction += 1
        return True



# CLASS RETURN
ai = ChatAgent()
while True: # Main loop for the chat agent
    cmd = ai.chatBot()
    if cmd == False:
        print("Exiting chat. Goodbye!")
        print("Total interactions:", ai.numberOfInteraction)
        break