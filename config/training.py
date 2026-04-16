#Code permettant de voir et enntrainer l'ia avec des donnée de training

class Training:

    def view_training_data():
        with open("backup_training_data.txt", "r", encoding="utf-8") as f:
            contained_training = f.read()
            print("Recorded discussion saved : \n", contained_training)

training = Training
training.view_training_data()