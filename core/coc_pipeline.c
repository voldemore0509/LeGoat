#include <stdio.h>    
#include <stdlib.h>   
#include <string.h>
#include "../models/optimisationModelsLLM.h"  // ← accès à tout

struct coc_pipeline
{
    char *answer;
    int number_caracter;
    int caracter_autorized;

};

/*
    count_characters() — parcourt la requête de l'utilisateur
    caractère par caractère et stocke le total dans le struct.

    On évite strlen() volontairement ici : vous voyez exactement
    ce qui se passe en mémoire. La boucle avance case par case
    dans le tableau jusqu'à tomber sur '\0', le marqueur de fin
    de chaîne en C.

    Paramètre : struct coc_pipeline *coc — le contexte du pipeline
                char *request            — la requête à analyser
*/
void count_characters(struct coc_pipeline *coc, char *request)
{
    // Sécurité : si l'un des deux pointeurs est NULL,
    // on initialise number_caracter à 0 et on sort proprement.
    if (coc == NULL || request == NULL)
    {
        if (coc != NULL)
            coc->number_caracter = 0;
        return;
    }

    // On initialise le compteur avant de parcourir
    coc->number_caracter = 0;

    // On parcourt le tableau caractère par caractère.
    // request[i] != '\0' : tant qu'on n'a pas atteint la fin
    // de la chaîne, on continue d'avancer.
    int i = 0;
    while (request[i] != '\0')
    {
        coc->number_caracter++;
        i++;
    }
}

void initialisation_coc() 
{
    struct model_config *config = init_contraction_of_chat();
    (void)config; // ← dit explicitement au compilateur "oui je sais, c'est voulu"
}

void contraction_percent(struct coc_pipeline *coc)
{
    if(coc->number_caracter <= 5000)
    {
        coc->caracter_autorized = 255;
    }
    else if(coc->number_caracter <= 10000)
    {
        coc->caracter_autorized = 500;
    }
    else
    {
       coc->caracter_autorized = 800; 
    }
}

/*
    generation_reponse_coc() — génère la réponse contractée de l'IA.

    Cette fonction fait trois choses dans l'ordre :
    1) Elle alloue la bonne quantité de mémoire pour coc->answer
       en fonction de coc->caracter_autorized (255, 500 ou 800).
    2) Elle construit le prompt système en y incluant la contrainte
       de caractères, pour que l'IA sache exactement jusqu'où elle
       peut aller.
    3) Elle place le résultat dans coc->answer.
       (Pour l'instant en mode MOCK — le vrai appel Ollama viendra ici.)

    Paramètres : struct coc_pipeline *coc — le contexte complet du pipeline
                 char *request            — la requête originale de l'utilisateur
*/
void generation_reponse_coc(struct coc_pipeline *coc, char *request)
{
    /*
        Sécurité d'entrée : si l'un des pointeurs est invalide,
        on sort immédiatement sans rien faire.
    */
    if (coc == NULL || request == NULL)
    {
        return;
    }

    /*
        ÉTAPE 1 — Allocation mémoire de coc->answer.

        On alloue exactement coc->caracter_autorized + 1 octets.
        Le +1 est obligatoire en C pour le caractère '\0' de fin de chaîne.
        Sans lui, on déborde en mémoire et le comportement est indéfini.

        Selon ce que contraction_percent() a calculé :
        - 255  → on alloue 256 octets  (réponse légère)
        - 500  → on alloue 501 octets  (réponse moyenne)
        - 800  → on alloue 801 octets  (réponse longue)

        L'IA ne pourra physiquement pas écrire au-delà de cette limite
        puisque c'est tout ce qu'on lui donne comme espace.
    */
    coc->answer = malloc((coc->caracter_autorized + 1) * sizeof(char));

    if (coc->answer == NULL)
    {
        /*
            Si malloc échoue (mémoire insuffisante), on sort proprement.
            Aucun crash, aucune donnée corrompue.
        */
        return;
    }

    /*
        On initialise le tableau avec '\0' sur toute sa longueur.
        C'est une bonne pratique : ça garantit qu'aucun octet résiduel
        en mémoire ne vient polluer la chaîne si l'IA ne remplit pas tout.
    */
    memset(coc->answer, '\0', coc->caracter_autorized + 1);

    /*
        ÉTAPE 2 — Construction du prompt système.

        On transforme coc->caracter_autorized en texte lisible
        pour l'intégrer dans le prompt sans utiliser snprintf.
        On couvre les trois cas possibles issus de contraction_percent().
    */
    char limite_texte[10];

    if (coc->caracter_autorized == 255)
    {
        strcpy(limite_texte, "255");
    }
    else if (coc->caracter_autorized == 500)
    {
        strcpy(limite_texte, "500");
    }
    else
    {
        strcpy(limite_texte, "800");
    }

    /*
        On calcule la taille totale du prompt avant de l'allouer.
        C'est important : un malloc trop petit → buffer overflow,
        un malloc trop grand → gaspillage. On additionne tout
        ce qu'on va coller ensemble via strcat().
    */
    int taille_prompt =
        strlen(request)
        + strlen(limite_texte)
        + 300; /* marge pour les textes fixes du prompt */

    char *prompt = malloc((taille_prompt + 1) * sizeof(char));

    if (prompt == NULL)
    {
        /*
            Si malloc du prompt échoue, on libère answer
            pour ne pas laisser de fuite mémoire et on sort.
        */
        free(coc->answer);
        coc->answer = NULL;
        return;
    }

    /*
        On construit le prompt morceau par morceau.

        L'idée ici c'est que l'IA reçoit deux informations claires :
        - la contrainte de caractères (elle sait jusqu'où aller)
        - la requête originale de l'utilisateur (ce qu'elle doit contracter)

        Ce prompt sera remplacé par le vrai appel HTTP vers Ollama
        une fois que le pipeline de communication sera en place.
    */
    prompt[0] = '\0';
    strcat(prompt, "Tu es un assistant de contraction de texte. ");
    strcat(prompt, "Tu dois resumer la requete suivante en ");
    strcat(prompt, limite_texte);
    strcat(prompt, " caracteres maximum. ");
    strcat(prompt, "Tu ne depasses jamais cette limite. ");
    strcat(prompt, "Tu conserves l'objectif, les contraintes et le contexte essentiel.\n\n");
    strcat(prompt, "Requete :\n");
    strcat(prompt, request);
    strcat(prompt, "\n\nContraction :\n");

    /*
        ÉTAPE 3 — Appel au modèle (MOCK pour l'instant).

        Ici viendra le vrai appel à Ollama via HTTP ou subprocess.
        Pour le moment on copie le prompt dans answer pour vérifier
        que le pipeline entier fonctionne de bout en bout.

        ATTENTION : on ne copie que caracter_autorized caractères max.
        strncpy garantit qu'on ne déborde jamais dans coc->answer,
        quelle que soit la longueur du prompt.
    */
    strncpy(coc->answer, prompt, coc->caracter_autorized);

    /*
        strncpy ne garantit pas le '\0' final si la source est plus longue
        que la destination. On le force manuellement pour être safe.
    */
    coc->answer[coc->caracter_autorized] = '\0';

    /*
        Nettoyage : le prompt a servi, il n'a plus sa place en mémoire.
        coc->answer lui, reste alloué — c'est le caller qui le libérera.
    */
    free(prompt);
}

char* run_coc(char* request)
{
    struct coc_pipeline *coc = malloc(sizeof (struct coc_pipeline));
    initialisation_coc();
    count_characters(coc, request);
    contraction_percent(coc);
    generation_reponse_coc(coc, request);
    char *resultat = coc->answer;
    free(coc);
    return resultat;
}