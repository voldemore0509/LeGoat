#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct mode_config
{
    float temp;
    int max_tokens;
    char prompt_systeme[1000]; 
};
struct mode_config* init_thinking_mode()
{
    struct mode_config *config = malloc(sizeof (struct mode_config));   //allocaiton de la mémoire pour 1 élément
    strcpy(config->prompt_systeme,"Answer thoughtfully, produce answers with virtually no errors to the question, and review your answers to ensure you are addressing the question correctly.");
    config->temp = 0.3;
    config->max_tokens = 2000;
    return config;
}