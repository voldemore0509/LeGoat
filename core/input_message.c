#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "im.h"

int pdlc(char *writing)
{
    int i = 0;
    while(writing[i] != '\0')   //permet de savoir combien de caracter total
    {
        i ++;
    }
    i ++;
    return i;
}

char *writing(int sizeofcaractermax)
{
    char *writing = malloc(sizeof (char) * sizeofcaractermax);
    puts("writing a texte : ");
    fgets(writing, sizeofcaractermax, stdin);
    int longueur = strlen(writing);
    if (longueur > 0 && writing[longueur - 1] == '\n')
    {
        writing[longueur - 1] = '\0';
    }
    int size_of_request = pdlc(writing);
    char *optimized_writing = realloc(writing, size_of_request);  //re alloue corretement de la mémoire
    if (optimized_writing != NULL)
    {
        writing = optimized_writing;
        return writing;   // pas de problème : on retourne le pointeur valide, on ne le libère pas ici
    }
    free(writing);         // realloc a échoué : on libère l'original avant d'abandonner
    return NULL;            // signale clairement l'échec à l'appelant
       //problème
}

void clear_cache_memory(char *write)
{
    free(write);
}