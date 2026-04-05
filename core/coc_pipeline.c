#include <stdio.h>    
#include <stdlib.h>   
#include <string.h>
#include "../models/optimisationModelsLLM.h"  // ← accès à tout

void initialisation_coc() 
{
    struct model_config *config = init_contraction_of_chat();
    free(config);  // ← manque
}

int contraction_percent(int number_caracter)
{
    if(number_caracter <= 5000)
    {
        return 255;
    }
    else if(number_caracter <= 10000)
    {
        return 500;
    }
    else
    {
       return 800; 
    }
}

char* run_coc(char* reponse,int number_caracter)
{
    int result = contraction_percent(number_caracter);
    //on envoie à l'ia avec le prompt pour pouvoir contracter la demande de l'utilisateur
    //elle renvoie sa réponse dans un ficher ou autre
    //ATTENTION A BIEN RETURN LES VARIABLE  
}