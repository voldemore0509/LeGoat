#ifndef LOCAL_MODELS_H
#define LOCAL_MODELS_H

struct model_config
{
    char model[50];
    float temp;
    int max_tokens;
    char prompt_systeme[1000]; 
};

struct model_config* init_goat();
struct model_config* init_maestro();
struct model_config* init_goat_code();
void free_mode_models(struct model_config *config);

#endif