#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct mode_config
{
    float temp;
    int max_tokens;
    char prompt_systeme[1000]; 
};
struct mode_config* init_creativity_mode()
{
    struct mode_config *config = malloc(sizeof (struct mode_config));   //allocaiton de la mémoire pour 1 élément
    strcpy(config->prompt_systeme,"Be creative, imaginative, innovative, formulate hypotheses, demonstrate your hypotheses with examples, be visionary.");
    config->temp = 1.3;
    config->max_tokens = 3000;
    return config;
}