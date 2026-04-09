#include <stdio.h>
#include <string.h>

void written_commande() // fonction pour initier la demande de l'utilisateur
{
    char commande[256];

    printf("Ecrivez votre commande : ");

    if (fgets(commande, sizeof(commande), stdin) != NULL)
    {
        // retire le retour à la ligne ajouté par fgets
        commande[strcspn(commande, "\n")] = '\0';

        printf("Commande recue : %s\n", commande);
    }
}

int main(void)
{
    written_commande();
    return 0;
}