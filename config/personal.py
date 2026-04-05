#Code permettant d'entrez ses informations personnel pour permettre à l'ia d'en apprendre plus sur nous

class Personal_information:

    def identity_first_name():
        first_name = input("please enter your first name for AI : ")
        print("the AI adress to you with ",first_name,"\n")
        return first_name
    
    def identity_name():
        name = input("please enter your name for AI : ")
        print("the AI adress to you with ",name,"\n")
        return name

    def identity_age():
        age = input("please enter your age for AI : ")
        print("your age is ",age," years old , the AI adress to you in fonction do you age\n")
        return age
  
    def identity_information():
        information = input("please the information about you beacause to help the AI : ")
        print("the information is sauvegarded and private\n")
        return information

#OBJECT
personal = Personal_information
i = 0
while(i < 1):
    print("SETTING -> PERSONAL\n1)First Name\n2)Name\n3)Information\n")
    choice = int(input("enter your choice : "))
    if choice == 1:
        first_name = personal.identity_first_name()
        with open("backup_personal_first_name.txt", "w", encoding="utf-8") as f:
            f.write(first_name)
    elif choice == 2:
        name = personal.identity_name()
        with open("backup_personal_name.txt", "w", encoding="utf-8") as f:
            f.write(name)
    elif choice == 3:
        information = personal.identity_information()
        with open("backup_personal_information.txt", "w", encoding="utf-8") as f:
            f.write(information)   
    else:
        print("le choix entrée est non valide")




    


