#include <stdio.h>    
#include <stdlib.h>   
#include <string.h>
#include "../models/optimisationModelsLLM.h"  // ← accès à tout

struct coc_pipeline
{
    char *answer;
    int number_caracter;
    int caracter_autorized;

};

void initialisation_coc() 
{
    struct model_config *config = init_contraction_of_chat();
    (void)config; // ← dit explicitement au compilateur "oui je sais, c'est voulu"
}

char* run_coc(char* request)
{
    struct coc_pipeline *coc = malloc(sizeof (struct coc_pipeline));
    initialisation_coc();
    free(coc);
}