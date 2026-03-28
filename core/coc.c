#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <curl/curl.h>

struct conv
{
    char request[2048];
};

#define OLLAMA_URL  "http://localhost:11434/api/generate"
#define SYSTEM_PROMPT \
"Résume en français à la 1re personne (je). Format EXACT en 4 lignes:\n" \
"Theme: ...\n" \
"These: ...\n" \
"Appuis: ...\n" \
"Donnees: ...\n" \
"Max 220 mots. Ignore les exemples. N'invente rien."
#define MODEL_NAME  "qwen2.5:1.5b"

/* Buffer pour récupérer la réponse HTTP */
typedef struct {
    char *data;
    size_t size;
} Buffer;

static size_t write_cb(void *contents, size_t size, size_t nmemb, void *userp)
{
    size_t realsize = size * nmemb;
    Buffer *mem = (Buffer *)userp;

    char *ptr = realloc(mem->data, mem->size + realsize + 1);
    if (!ptr) return 0;

    mem->data = ptr;
    memcpy(&(mem->data[mem->size]), contents, realsize);
    mem->size += realsize;
    mem->data[mem->size] = '\0';
    return realsize;
}

/* Échappement JSON minimal */
static char *json_escape(const char *s)
{
    size_t len = 0;
    for (const char *p = s; *p; p++) {
        switch (*p) {
            case '\"': case '\\': case '\n': case '\r': case '\t':
                len += 2; break;
            default:
                len += 1; break;
        }
    }
    char *out = malloc(len + 1);
    if (!out) return NULL;

    char *w = out;
    for (const char *p = s; *p; p++) {
        switch (*p) {
            case '\"': *w++='\\'; *w++='\"'; break;
            case '\\': *w++='\\'; *w++='\\'; break;
            case '\n': *w++='\\'; *w++='n'; break;
            case '\r': *w++='\\'; *w++='r'; break;
            case '\t': *w++='\\'; *w++='t'; break;
            default:   *w++=*p; break;
        }
    }
    *w = '\0';
    return out;
}

/* Extraction SIMPLE du champ "response" (OK si stream=false) */
static char *extract_response_field(const char *json)
{
    const char *key = "\"response\":\"";
    const char *p = strstr(json, key);
    if (!p) return NULL;
    p += strlen(key);

    char *out = malloc(strlen(p) + 1);
    if (!out) return NULL;

    size_t i = 0;
    int esc = 0;
    while (*p) {
        if (!esc && *p == '\"') break;
        if (!esc && *p == '\\') { esc = 1; p++; continue; }
        esc = 0;
        out[i++] = *p++;
    }
    out[i] = '\0';
    return out;
}

static char *ollama_generate(const char *prompt)
{
    CURL *curl = curl_easy_init();
    if (!curl) return NULL;

    Buffer buf = {0};
    buf.data = malloc(1);
    buf.size = 0;

    char *escaped = json_escape(prompt);
    if (!escaped) { curl_easy_cleanup(curl); free(buf.data); return NULL; }

    char *sys_escaped = json_escape(SYSTEM_PROMPT);
    if (!sys_escaped) { curl_easy_cleanup(curl); free(buf.data); free(escaped); return NULL; }

    /* IMPORTANT: stream=false => 1 seule réponse JSON */
    char payload[8192];
    snprintf(payload, sizeof(payload),
    "{"
    "\"model\":\"%s\","
    "\"system\":\"%s\","
    "\"prompt\":\"%s\","
    "\"stream\":false,"
    "\"options\":{"
        "\"temperature\":0,"
        "\"seed\":42,"
        "\"top_p\":0.2,"
        "\"num_predict\":320"
    "}"
    "}",
    MODEL_NAME, sys_escaped, escaped
    );

    struct curl_slist *headers = NULL;
    headers = curl_slist_append(headers, "Content-Type: application/json");

    curl_easy_setopt(curl, CURLOPT_URL, OLLAMA_URL);
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, payload);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_cb);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, (void *)&buf);

    CURLcode res = curl_easy_perform(curl);

    curl_slist_free_all(headers);
    curl_easy_cleanup(curl);
    free(escaped);
    free(sys_escaped);

    if (res != CURLE_OK) {
        free(buf.data);
        return NULL;
    }

    return buf.data; /* à free() par l'appelant */
}

/* Fonction "1 ligne" pour appeler le LLM et afficher la réponse */
static void ask_ollama_and_print(const char *prompt)
{
    char *json = ollama_generate(prompt);
    if (!json) {
        puts("\n[Ollama] Erreur: API inaccessible (ollama serve lancé ?)\n");
        return;
    }

    char *answer = extract_response_field(json);
    if (answer) {
        printf("\nIA > %s\n", answer);
        free(answer);
    } else {
        /* fallback */
        printf("\nIA (raw JSON) > %s\n", json);
    }

    free(json);
}

void request_manual(struct conv *coc)
{
    puts("Entrez la requette");
    scanf("%s",coc->request);   //pose problmème
    printf("la requette est : %s",coc->request);
}

void read_file(struct conv *coc , FILE *collector)
{
    fgets(coc->request, sizeof coc->request, collector);      //compte les espace
    fclose(collector);
    printf("\n--content file : %s --\n",coc->request);
}

void ruling(struct conv *coc , int *choice ,FILE *collector)
{
    printf("%s\n-%s\n-%s\n%s","Entrez votre choix pour tester la machine"," 1) Entree manuelle"," 2) Entree via un ficher","Choisisez le chiffre : ");
    scanf("%i",&*choice);
    switch(*choice)
    {
        case 1:
        puts("Entrée Manuelle");
        request_manual(coc);
        ask_ollama_and_print(coc->request);
        break;

        case 2:
        puts("Entére Via Ficher");
        read_file(coc,collector);
        ask_ollama_and_print(coc->request);
        break;

        default:
        puts("Tu es Hors Sujet !");
        break;
    }
}

int main(void)
{
    int choice ;
    FILE *collector = fopen("collector.txt","r");
    struct conv *coc = malloc(sizeof (struct conv) * 1);
    curl_global_init(CURL_GLOBAL_ALL);
    for(;;)
    {
        ruling(coc,&choice,collector);
    }
    free(coc);
    return 0;
}