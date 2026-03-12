import os
import json
from openai import OpenAI

_client = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY"),
            base_url=os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL"),
        )
    return _client


SYSTEM_PROMPT = """Você é um analista de vendas sênior da Vértice Agência Digital, \
agência brasileira especializada em sites de alta performance e presença digital \
para pequenas e médias empresas.

Avalie se o lead local é um bom fit para contratar a Vértice. \
O fit ideal é uma empresa que:
- Não tem site ou tem site ruim/desatualizado
- Não aparece bem no Google Maps ou não tem perfil completo
- Atua em nicho onde a presença digital gera diferencial real (salões, clínicas, \
restaurantes, academias, barbearias, pet shops, etc)
- Tem potencial de ticket médio relevante para a agência

Retorne SOMENTE um JSON válido, sem markdown, sem explicações adicionais:
{
  "score": <inteiro 0 a 10>,
  "pain_point": "<dor principal em 1 frase objetiva, máx 15 palavras, pt-BR>",
  "pitch_hook": "<frase de abertura para WhatsApp: tom leve, direto e personalizado, máx 35 palavras, pt-BR>"
}

Critérios para o score:
- 9-10: Nicho premium (salão, clínica, barbearia), sem site, sem telefone online → altíssima oportunidade
- 7-8: Bom nicho, perfil incompleto, algumas lacunas digitais
- 5-6: Nicho médio ou já tem alguma presença digital
- 3-4: Nicho commodity ou perfil razoavelmente completo
- 0-2: Já possui presença digital forte, pouco espaço para agregar valor"""


def score_lead(
    empresa: str,
    segmento: str,
    tem_site: bool,
    tem_telefone: bool,
    endereco: str = "",
    score_vertice: int = 0,
) -> dict:
    user_content = f"""Lead para análise:
- Empresa: {empresa}
- Segmento: {segmento or "Não informado"}
- Tem site: {"Sim" if tem_site else "Não — invisível no Google"}
- Tem telefone online: {"Sim" if tem_telefone else "Não — perfil incompleto"}
- Endereço: {endereco or "Não informado"}
- Score Vértice (qualificação OSM): {score_vertice}/100"""

    client = get_client()
    response = client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    )

    raw = response.choices[0].message.content.strip()

    raw = raw.strip("` \n")
    if raw.startswith("json"):
        raw = raw[4:].strip()

    result = json.loads(raw)

    return {
        "score": max(0, min(10, int(result.get("score", 5)))),
        "pain_point": str(result.get("pain_point", "")).strip()[:500],
        "pitch_hook": str(result.get("pitch_hook", "")).strip()[:1000],
    }
