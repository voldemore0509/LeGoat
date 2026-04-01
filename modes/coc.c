#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct mode_config
{
    float temp;
    int max_tokens;
    char prompt_systeme[1000]; 
};
struct mode_config* init_contraction_of_chat_mode()
{
    struct mode_config *config = malloc(sizeof (struct mode_config));   //allocaiton de la mémoire pour 1 élément
    strcpy(config->prompt_systeme,"Summarize what you've been told by stating the thesis presented, the additional data cited, and the context. Do not include examples or other unnecessary text in your response.");
    config->temp = 0.1;
    config->max_tokens = 250;
    return config;
}