#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "local_models.h"

struct model_config* init_goat()
{
    struct model_config *config = malloc(sizeof (struct model_config));   //allocaiton de la mémoire pour 1 élément
    strcpy(config->model,"mistral-small3.2:24b");
    config->temp = 0.7;
    config->max_tokens = 2048;
    return config;
}

struct model_config* init_maestro()
{
    struct model_config *config = malloc(sizeof (struct model_config));   //allocaiton de la mémoire pour 1 élément
    strcpy(config->model,"magistral:24b");
    config->temp = 0.7;
    config->max_tokens = 2048;
    return config;
}

struct model_config* init_goat_code()
{
    struct model_config *config = malloc(sizeof (struct model_config));   //allocaiton de la mémoire pour 1 élément
    strcpy(config->model,"devstral-small-2:latest");
    config->temp = 0.7;
    config->max_tokens = 2048;
    return config;
}

void free_mode_models(struct model_config *config) {
    free(config);
    config = NULL;
}