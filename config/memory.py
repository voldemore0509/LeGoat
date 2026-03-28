#code permettant de gérer la mémoire de l'IA
class Memory:

    def element_save():
        with open("backup_memory_elements.txt", "r", encoding="utf-8") as f:
            contained_memory_elements = f.read()
            print("Saved elements :\n", contained_memory_elements)

    def recorded_discussion():
        with open("backup_recorded_discussion.txt", "r", encoding="utf-8") as f:
            contained_recorded_discussion = f.read()
            print("Recorded discussion saved : \n", contained_recorded_discussion)

memory = Memory
i = 0
while(i < 1):
    choice = int(input("enter your choice : "))
    if choice == 1:
        memory.element_save()
    elif choice == 2:
        memory.recorded_discussion()
    else:
        print("le choix entrée est non valide")
