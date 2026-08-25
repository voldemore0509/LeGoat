#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <curl/curl.h>
#include <cjson/cJSON.h>

struct MemoryStruct 
{
    char *memory;
    size_t size;
};

size_t callback(void *contents, size_t size, size_t nmemb, void *userp)
{

}


int generation_prompt(const char *prompt, const char *model, char *output, size_t output_size)
{
    CURL *curl = curl_easy_init();
    if(curl == NULL)    //verifie si le Handle est nul ou pas 
    {
        printf("handle is NULL");
        return 1; 
    }
    return 0;
}