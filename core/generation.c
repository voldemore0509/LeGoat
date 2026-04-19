//Code for generating the response
#include <stdio.h>
#include <curl/curl.h>

struct variable_generation
{
        char json_data[512];  // le buffer
}

void generation_prompt(struct model_config *models)
{
    //initialisation
    CURL *curl = curl_easy_init(); //appel la fonction
    if(curl == NULL)
    {
        printf("Error Serve");
    }
    else
    {
        struct variable_generation *generation = malloc(sizeof(struct variable_generation)); //alloue de la mémoire pour stoquer et libérer à la fin
        //permet de stoquer les paramètre JSON
        snprintf(generation->json_data, sizeof(generation->json_data), 
        "{\"model\":\"%s\", \"prompt\": \"%s\", \"stream\": false}", 
        models->model, models->prompt);
        free(generation);
    }

}