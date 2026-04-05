#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "optimisationModelsLLM.h"

struct model_config* init_contraction_of_chat()
{
    struct model_config *config = malloc(sizeof (struct model_config));   //allocaiton de la mémoire pour 1 élément
    strcpy(config->model,"nomic-embed-text:latest");
    config->temp = 0.7;
    config->max_tokens = 2048;
    return config;
}