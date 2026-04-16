#include <stdio.h>    
#include <stdlib.h>   
#include <string.h>
#include "../models/local_models.h"
struct thinking_variable
{
    char reponse[1000] ;
    char recommandation[500];
    int incrementation_recommandation;
    int return_recommandation;
};
void response_generation(char* requete)
{
    struct model_config *config = init_goat();
    // logique ici
    free(config);
}

void response_regeneration(struct thinking_variable *p)
{
    //code pour regénré en fonction des recommandation
}
int consistency_check(struct thinking_variable *p)
{
    //code pour vérfier la cohérence avec la requette de l'utilisateur
};

char* generation_reponse(const char *question_utilisateur)
{
    /*
        1) Vérification de sécurité :
        si la question n'existe pas ou qu'elle est vide,
        on retourne directement un message d'erreur.
    */
    if (question_utilisateur == NULL || question_utilisateur[0] == '\0')
    {
        char *erreur = malloc(50 * sizeof(char));
        if (erreur != NULL)
        {
            strcpy(erreur, "Erreur : question utilisateur vide.");
        }
        return erreur;
    }

    /*
        2) On initialise la configuration du modèle COC.
        Cette fonction vient de votre fichier optimisationModelsLLM.c
        et renvoie un struct model_config*.
    */
    struct model_config *config = init_contraction_of_chat();

    /*
        Si l'initialisation échoue, on retourne une erreur.
    */
    if (config == NULL)
    {
        char *erreur = malloc(70 * sizeof(char));
        if (erreur != NULL)
        {
            strcpy(erreur, "Erreur : impossible d'initialiser le modele COC.");
        }
        return erreur;
    }

    /*
        3) On calcule le nombre de caractères de la question.
        Cela va servir à savoir quel niveau de contraction appliquer.
    */
    int nombre_caracteres = strlen(question_utilisateur);

    /*
        4) On récupère le "niveau de contraction" à partir de votre fonction.
        Dans votre code actuel :
        - <= 5000  -> 255
        - <= 10000 -> 500
        - sinon    -> 800
    */
    int niveau_contraction = contraction_percent(nombre_caracteres);

    /*
        5) Comme vous ne voulez pas utiliser snprintf,
        on va éviter de construire une phrase avec un entier dedans.
        À la place, on transforme le niveau en texte simple.
    */
    char niveau_texte[30];

    if (niveau_contraction == 255)
    {
        strcpy(niveau_texte, "contraction_legere");
    }
    else if (niveau_contraction == 500)
    {
        strcpy(niveau_texte, "contraction_moyenne");
    }
    else
    {
        strcpy(niveau_texte, "contraction_forte");
    }

    /*
        6) On prépare le prompt système.
        Ce prompt dit au modèle ce qu'il doit faire.

        Ici, le but n'est PAS de répondre à l'utilisateur.
        Le but est de CONTRACTER son message.
    */
    char prompt_systeme[500];

    strcpy(prompt_systeme,
        "Tu dois contracter le message utilisateur. "
        "Tu conserves uniquement l'objectif, les contraintes, "
        "le contexte important et les informations utiles. "
        "Tu ne reponds pas a la question. "
        "Tu produis une version plus courte, claire et exploitable.");

    /*
        7) Maintenant, on doit fabriquer le prompt final envoyé au modèle.

        Comme on utilise strcpy/strcat, il faut réserver assez de mémoire.
        On additionne la taille :
        - du prompt système
        - du niveau de contraction
        - de la question utilisateur
        - de quelques textes fixes
        - +1 pour le caractère de fin '\0'
    */
    int taille_prompt =
        strlen(prompt_systeme)
        + strlen(niveau_texte)
        + strlen(question_utilisateur)
        + 200;

    char *prompt_final = malloc((taille_prompt + 1) * sizeof(char));

    /*
        Si malloc échoue, on libère config avant de quitter.
    */
    if (prompt_final == NULL)
    {
        free(config);
        return NULL;
    }

    /*
        8) On construit le prompt morceau par morceau.

        D'abord, on met une chaîne vide pour partir proprement.
    */
    prompt_final[0] = '\0';

    /*
        Puis on ajoute les différentes parties.
    */
    strcat(prompt_final, prompt_systeme);
    strcat(prompt_final, "\n\n");
    strcat(prompt_final, "Niveau de contraction : ");
    strcat(prompt_final, niveau_texte);
    strcat(prompt_final, "\n\n");
    strcat(prompt_final, "Message utilisateur :\n");
    strcat(prompt_final, question_utilisateur);
    strcat(prompt_final, "\n\n");
    strcat(prompt_final, "Contraction :\n");

    /*
        9) À CET ENDROIT, plus tard, vous remplacerez le "mock"
        par le vrai appel au modèle local.

        Par exemple :
        - appel HTTP vers Ollama
        - appel via subprocess
        - appel via une fonction core/llm_client.c

        Pour l'instant, on simule juste une réponse
        afin de tester si le pipeline fonctionne.
    */

    /*
        10) On prépare la réponse de test.
        Ici, on retourne quelque chose de visible dans la console
        pour vérifier que le pipeline marche.
    */
    int taille_reponse =
        strlen(prompt_final)
        + strlen(config->model)
        + 100;

    char *reponse = malloc((taille_reponse + 1) * sizeof(char));

    if (reponse == NULL)
    {
        free(prompt_final);
        free(config);
        return NULL;
    }

    /*
        On construit la réponse de test.
    */
    reponse[0] = '\0';
    strcat(reponse, "[MOCK COC]\n");
    strcat(reponse, "Modele utilise : ");
    strcat(reponse, config->model);
    strcat(reponse, "\n\n");
    strcat(reponse, "Prompt envoye au modele :\n");
    strcat(reponse, prompt_final);

    /*
        11) Nettoyage mémoire :
        - prompt_final n'est plus nécessaire
        - config non plus
    */
    free(prompt_final);
    free(config);

    /*
        12) On retourne la réponse.
        Le code qui appelle cette fonction devra faire free(reponse).
    */
    return reponse;
}

char* run_thinking(char *requete)
{
    struct thinking_variable *thinking = malloc(sizeof(struct thinking_variable));
    thinking->incrementation_recommandation = 0; 
    //appeler la varaible contraction pour contracter la demande de l'utilisateur
    response_generation(requete);    //appel le code de génération
    thinking->return_recommandation = consistency_check(thinking); //appel le code de vérifaction de cohérance 
    do
    {
        response_regeneration(thinking);
        thinking->return_recommandation = consistency_check(thinking);
        thinking->incrementation_recommandation ++;
    }while(thinking->return_recommandation != 1 && thinking->incrementation_recommandation < 3);
    char *resultat = malloc(strlen(thinking->reponse) + 1);  // +1 pour le '\0'
    strcpy(resultat, thinking->reponse);
    free(thinking);
    return resultat;
}