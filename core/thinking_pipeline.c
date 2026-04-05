#include <stdio.h>    
#include <stdlib.h>   
#include <string.h>
#include "../models/local_models.h"
struct thinking_variable
{
    char reponse[1000] ;
    char recommandation[500];
    int incrementation_recommandation;
    int return_recommandation;
};
void response_generation(char* requete)
{
    struct model_config *config = init_goat();
    // logique ici
    free(config);
}

void response_regeneration(struct thinking_variable *p)
{
    //code pour regénré en fonction des recommandation
}
int consistency_check(struct thinking_variable *p)
{
    //code pour vérfier la cohérence avec la requette de l'utilisateur
};

char* run_thinking(char *requete)
{
    struct thinking_variable *thinking = malloc(sizeof(struct thinking_variable));
    thinking->incrementation_recommandation = 0; 
    //appeler la varaible contraction pour contracter la demande de l'utilisateur
    response_generation(requete);    //appel le code de génération
    thinking->return_recommandation = consistency_check(thinking); //appel le code de vérifaction de cohérance 
    do
    {
        response_regeneration(thinking);
        thinking->return_recommandation = consistency_check(thinking);
        thinking->incrementation_recommandation ++;
    }while(thinking->return_recommandation != 1 && thinking->incrementation_recommandation < 3);
    char *resultat = malloc(strlen(thinking->reponse) + 1);  // +1 pour le '\0'
    strcpy(resultat, thinking->reponse);
    free(thinking);
    return resultat;
}