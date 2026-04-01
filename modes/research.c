#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct mode_config
{
    float temp;
    int max_tokens;
    char prompt_systeme[1000]; 
};
struct mode_config* init_research_mode()
{
    struct mode_config *config = malloc(sizeof (struct mode_config));   //allocaiton de la mémoire pour 1 élément
    strcpy(config->prompt_systeme,"Provide a structured response, detail your sources, and be as precise as possible.");
    config->temp = 0.1;
    config->max_tokens = 3000;
    return config;
}