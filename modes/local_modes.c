#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct mode_config
{
    float temp;
    int max_tokens;
    char prompt_systeme[2000]; 
};
struct mode_config* init_fast_mode()
{
    struct mode_config *config = malloc(sizeof (struct mode_config));   //allocaiton de la mémoire pour 1 élément
    strcpy(config->prompt_systeme,"Prioritize speed of response without compromising the quality and coherence of the answers; be the fastest.");
    config->temp = 0.1;
    config->max_tokens = 600;
    return config;
}

struct mode_config* init_research_mode()
{
    struct mode_config *config = malloc(sizeof (struct mode_config));   //allocaiton de la mémoire pour 1 élément
    strcpy(config->prompt_systeme,"Provide a structured response, detail your sources, and be as precise as possible.");
    config->temp = 0.1;
    config->max_tokens = 5000;
    return config;
}

struct mode_config* init_creativity_mode()
{
    struct mode_config *config = malloc(sizeof (struct mode_config));   //allocaiton de la mémoire pour 1 élément
    strcpy(config->prompt_systeme,"Be creative, imaginative, innovative, formulate hypotheses, demonstrate your hypotheses with examples, be visionary.");
    config->temp = 1.3;
    config->max_tokens = 3000;
    return config;
}

struct mode_config* init_thinking_mode()
{
    struct mode_config *config = malloc(sizeof (struct mode_config));   //allocaiton de la mémoire pour 1 élément
    strcpy(config->prompt_systeme,"Answer thoughtfully, produce answers with virtually no errors to the question, and review your answers to ensure you are addressing the question correctly.");
    config->temp = 0.3;
    config->max_tokens = 2000;
    return config;
}

void free_mode_config(struct mode_config *config) {
    free(config);
    config = NULL;
}