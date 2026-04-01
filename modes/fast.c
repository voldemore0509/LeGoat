#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct mode_config
{
    float temp;
    int max_tokens;
    char prompt_systeme[1000]; 
};
struct mode_config* init_fast_mode()
{
    struct mode_config *config = malloc(sizeof (struct mode_config));   //allocaiton de la mémoire pour 1 élément
    strcpy(config->prompt_systeme,"Prioritize speed of response without compromising the quality and coherence of the answers; be the fastest.");
    config->temp = 0.1;
    config->max_tokens = 600;
    return config;
}