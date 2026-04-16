#Code permettant de definir les caracteristique de l'ia
class Characteristic:

    def characteristic_tone():
        tone = input("please enter the tone of AI (e.g., friendly, formal, humorous): ")
        print("the AI will respond in a", tone, "tone.\n")
        return tone
    
characteristic = Characteristic
i = 0
while(i < 1):
    tone = characteristic.characteristic_tone()
    with open("backup_tone.txt", "w", encoding="utf-8") as f:
        f.write(tone)