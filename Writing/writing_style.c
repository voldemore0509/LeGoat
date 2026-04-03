#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct writing_style
{
    char prompt_systeme[2000]; 
};
struct writing_style* init_learning_mode()
{
    struct writing_style *config = malloc(sizeof (struct writing_style));   //allocaiton de la mémoire pour 1 élément
    strcpy(config->prompt_systeme,"Adapt an explanatory writing style designed for learning, explain each concept with examples, and be as clear as possible.");
    return config;
}

struct writing_style* init_explanatory_mode()
{
    struct writing_style *config = malloc(sizeof (struct writing_style));   //allocaiton de la mémoire pour 1 élément
    strcpy(config->prompt_systeme,"Provide a structured and detailed answer, explaining your point as clearly as possible for optimal understanding.");
    return config;
}

void free_mode_config(struct writing_style *config) {
    free(config);
    config = NULL;
}