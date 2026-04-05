#ifndef OPTIMISATION_MODELS_H
#define OPTIMISATION_MODELS_H

struct model_config {
    char model[50];
    float temp;
    int max_tokens;
    char prompt_systeme[1000];
};

struct model_config* init_contraction_of_chat();

#endif