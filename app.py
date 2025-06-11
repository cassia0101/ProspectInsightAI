import streamlit as st
import os
import requests
import json
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

# --- Configuração das chaves de API ---
# No Streamlit Cloud, as chaves serão carregadas de .streamlit/secrets.toml
# Para testar localmente, elas serão carregadas do .streamlit/secrets.toml também.
try:
    # Tenta obter a GOOGLE_API_KEY do Streamlit secrets
    google_api_key = st.secrets["GOOGLE_API_KEY"]
except KeyError:
    st.error("A chave 'GOOGLE_API_KEY' não foi encontrada. Por favor, configure-a no .streamlit/secrets.toml ou nas configurações de secrets do Streamlit Cloud.")
    st.stop() # Interrompe a execução do app se a chave não for encontrada

try:
    # Tenta obter a SERPAPI_API_KEY do Streamlit secrets
    serpapi_api_key = st.secrets["SERPAPI_API_KEY"]
except KeyError:
    st.error("A chave 'SERPAPI_API_KEY' não foi encontrada. Por favor, configure-a no .streamlit/secrets.toml ou nas configurações de secrets do Streamlit Cloud.")
    st.stop() # Interrompe a execução do app se a chave não for encontrada

# **** MODELO GEMINI UTILIZADO ****
# Usando o gemini-2.0-flash
GEMINI_API_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# --- Funções de Busca e Geração de Conteúdo ---
@retry(
    wait=wait_exponential(multiplier=1, min=4, max=10),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(requests.exceptions.HTTPError)
)
def generate_content_with_retry_rest(prompt_text: str) -> str:
    """
    Tenta gerar conteúdo com o Gemini via API REST, com retries em caso de erro HTTP.
    """
    headers = {
        "Content-Type": "application/json",
    }
    payload = {
        "contents": [
            {"parts": [{"text": prompt_text}]}
        ]
    }
    response = requests.post(f"{GEMINI_API_ENDPOINT}?key={google_api_key}", headers=headers, json=payload)
    response.raise_for_status() # Levanta um HTTPError para status de erro (4xx ou 5xx)

    if response.status_code == 429: # Verificação explícita para Too Many Requests
        raise requests.exceptions.HTTPError("Too Many Requests (429) received.", response=response)

    response_json = response.json()
    if "candidates" in response_json and response_json["candidates"]:
        return response_json["candidates"][0]["content"]["parts"][0]["text"]
    else:
        st.warning(f"AVISO: Resposta Gemini sem candidatos. Detalhes: {response_json}")
        return "Não foi possível extrair o conteúdo gerado pelo Gemini."

def buscar_links_google(query: str, num_resultados: int = 5, lang: str = "pt") -> list[str]:
    """
    Busca links no Google usando SerpApi.
    """
    st.info(f"Buscando {num_resultados} links no Google para: '{query}' (via SerpApi)...")
    resultados: list[str] = []
try:
----params = { # Alinhe esta linha (e todo o dicionário)
--------"api_key": serpapi_api_key,
--------"q": query,
--------"num": num_resultados,
--------"hl": "lang",
--------"gl": "br"
----}
----url = "https://serpapi.com/search" 
----response = requests.get(url, params=params)
----response.raise_for_status() 
----res = response.json()  

----if "organic_results" in res: 
--------for item in res["organic_results"]: 
------------if "link" in item: 
----------------resultados.append(item["link"]) 
        st.success(f"Links encontrados: {len(resultados)}")
    except Exception as e:
        st.error(f"ERRO ao buscar links no Google via SerpApi para '{query}': {e}")
        st.warning("Verifique se a sua API Key da SerpApi está correta e se você tem créditos.")
    return resultados

def resumir_com_gemini(links: list[str]) -> str:
    """
    Gera um resumo analítico com o Gemini a partir de uma lista de links.
    """
    if not links:
        st.warning("AVISO: Nenhum link válido fornecido para resumo.")
        return "Não foi possível gerar um resumo, pois nenhum link relevante foi fornecido ou encontrado."

    links_formatados = "\n- ".join(links)

    prompt = f"""
Como um analista de negócios e inteligência de mercado sênior, analise o conteúdo dos links fornecidos.
Seu resumo deve ser conciso, acionável e focar em insights estratégicos sobre a empresa ou tópico central para prospecção comercial.

Pontos-chave a serem abordados no resumo:
-   Desafios Atuais: Obstáculos, problemas de mercado ou dores que a empresa enfrenta.
-   Oportunidades de Mercado: Onde a empresa pode crescer ou inovar?
-   Iniciativas Estratégicas: Projetos, parcerias, aquisições ou lançamentos recentes.
-   Pontos de Dor Relevantes: Problemas específicos que nossos produtos/serviços podem resolver.
-   Proposições de Valor: Como nossos produtos/serviços se alinham aos objetivos da empresa e que ganhos oferecemos.

Diretrizes:
-   Priorize as informações mais recentes e as mais impactantes para vendas.
-   Mencione explicitamente se houver informações conflitantes ou falta de dados.
-   Apresente o resumo de forma estruturada, usando títulos e marcadores.
-   Mantenha um tom profissional e analítico.

---
Links para análise (priorize a leitura e compreensão do conteúdo):
{links_formatados}

---
Resumo Analítico para Prospecção:
"""

    st.info("Iniciando a geração do resumo detalhado com o Gemini...")
    try:
        resumo_final = generate_content_with_retry_rest(prompt)
        return resumo_final
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            st.error(f"ERRO DE COTA: Você excedeu seu limite de requisições ao Gemini. Tente novamente mais tarde ou verifique sua cota da API.")
            return "Não foi possível gerar o resumo devido ao limite de requisições da API. Tente novamente mais tarde ou verifique sua cota."
        else:
            st.error(f"ERRO HTTP inesperado ao gerar o resumo: {e}. Status: {e.response.status_code}")
            return f"Ocorreu um erro HTTP ao gerar o resumo: {e}. Status: {e.response.status_code}"
    except Exception as e:
        st.error(f"ERRO INESPERADO ao gerar o resumo: {e}")
        return f"Ocorreu um erro desconhecido durante a geração do resumo: {type(e).__name__}: {e}"


# --- Interface Streamlit (Parte principal do aplicativo web) ---
st.set_page_config(page_title="ProspectInsightia", layout="wide")
st.title("💡 ProspectInsightia: Inteligência de Mercado para Prospecção")

st.markdown("""
Esta ferramenta busca informações sobre uma empresa no Google e gera um resumo analítico
usando a IA do Gemini, focando em insights para prospecção comercial.
""")

with st.expander("Sobre esta ferramenta"):
    st.write(f"""
    1.  **Busca no Google**: Utiliza a SerpApi para encontrar os 5 principais links relevantes.
    2.  **Resumo com Gemini**: Envia o conteúdo dos links para o modelo `{GEMINI_API_ENDPOINT.split('/')[-1].split(':')[0]}` para gerar um resumo focado em desafios, oportunidades e dores de mercado.
    3.  **Segurança**: Suas chaves de API são armazenadas de forma segura e não são expostas no código.
    """)

st.header("Dados da Empresa para Análise")

# Campos de entrada de texto e slider para o usuário
nome_empresa_input = st.text_input("Nome da Empresa", "Totvs")
setor_input = st.text_input("Setor da Empresa", "Software de gestão empresarial")
palavras_chave_input = st.text_input("Palavras-chave Adicionais (separadas por vírgula)", "expansão, crescimento, transformação digital, resultados financeiros")
num_resultados_input = st.slider("Número de Links para Buscar (via SerpApi)", 1, 10, 5)

# Botão para iniciar o processo
if st.button("Gerar Resumo de Prospecção"):
    if not nome_empresa_input:
        st.warning("Por favor, insira o nome da empresa.")
        st.stop() # Para a execução aqui se o nome da empresa estiver vazio

    # Prepara a query de pesquisa para o Google
    palavras_chave_formatadas = palavras_chave_input.replace(",", " ")
    query_pesquisa = f"{nome_empresa_input} {setor_input} {palavras_chave_formatadas}"

    st.subheader("Etapa 1: Busca no Google")
    with st.spinner("Buscando links relevantes no Google..."):
        links_encontrados = buscar_links_google(query_pesquisa, num_resultados=num_resultados_input)

    if links_encontrados:
        st.write("Links encontrados para análise:")
        for idx, link in enumerate(links_encontrados):
            st.markdown(f"- [{idx + 1}. {link}]({link})") # Exibe os links como hyperlinks

        st.subheader("Etapa 2: Geração do Resumo com Gemini")
        with st.spinner("Gerando resumo analítico com Gemini. Isso pode levar alguns segundos..."):
            resumo_final = resumir_com_gemini(links_encontrados)

        st.subheader("Resumo Analítico para Prospecção")
        # Exibe o resumo gerado pelo Gemini
        st.markdown(resumo_final)
    else:
        st.warning("Nenhum link foi encontrado para a query especificada. Não é possível gerar um resumo.")

st.markdown("---")
st.caption("Desenvolvido para inteligência de mercado.")
