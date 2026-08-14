#include <stdio.h>
#include <stdlib.h>

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

int writing(int sizeofcaractermax)
{
    char *writing = malloc(sizeof (char) * sizeofcaractermax);
    puts("writing a texte : ");
    scanf("%s",writing);
    int size_of_request = pdlc(writing);
    char *optimized_writing = realloc(writing, size_of_request);  //re alloue corretement de la mémoire
    if (optimized_writing != NULL)
    {
        writing = optimized_writing;
        printf("%s",writing);
        free(writing);
        return 0;   //pas de problème
    }
    free(writing);   // realloc a échoué, le bloc d'origine est encore valide
    return 1;        //problème
}

int main(void)
{
    int result = writing(10000);
    return 0;
}