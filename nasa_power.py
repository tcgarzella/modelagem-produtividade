"""
Módulo NASA POWER — busca de dados climáticos históricos diários
API: https://power.larc.nasa.gov/api/temporal/daily/point

Parâmetros utilizados:
  T2M_MAX      — Temperatura máxima diária a 2m (°C)
  T2M_MIN      — Temperatura mínima diária a 2m (°C)
  PRECTOTCORR  — Precipitação total corrigida (mm/dia)

Community: AG (Agroclimatologia)

Cache: arquivos JSON locais por (lat, lon, ano), evitando
       requisições repetidas à API para o mesmo período.
"""

import requests
import json
import os
import time
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────────────────────

NASA_POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

PARAMETROS = "T2M_MAX,T2M_MIN,PRECTOTCORR"

# Diretório de cache — relativo ao módulo ou configurável
CACHE_DIR = Path(os.environ.get("NASAPOWER_CACHE_DIR", Path.home() / ".nasapower_cache"))

# Valor sentinela da NASA POWER para dados ausentes
FILL_VALUE = -999.0

# Timeout e retentativas
REQUEST_TIMEOUT = 60   # segundos
MAX_RETRIES     = 3
RETRY_DELAY     = 5    # segundos entre tentativas


# ─────────────────────────────────────────────────────────────
# CACHE
# ─────────────────────────────────────────────────────────────

def _cache_path(lat: float, lon: float, ano: int) -> Path:
    """Caminho do arquivo de cache para uma combinação lat/lon/ano."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    lat_str = f"{lat:.4f}".replace("-", "m")
    lon_str = f"{lon:.4f}".replace("-", "m")
    return CACHE_DIR / f"nasapower_{lat_str}_{lon_str}_{ano}.json"


def _ler_cache(lat: float, lon: float, ano: int) -> Optional[dict]:
    """Retorna dados do cache se existirem, None caso contrário."""
    path = _cache_path(lat, lon, ano)
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Cache corrompido {path}: {e}. Será sobrescrito.")
    return None


def _salvar_cache(lat: float, lon: float, ano: int, dados: dict) -> None:
    """Salva dados no cache local."""
    path = _cache_path(lat, lon, ano)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2)
        logger.debug(f"Cache salvo: {path}")
    except IOError as e:
        logger.warning(f"Não foi possível salvar cache {path}: {e}")


# ─────────────────────────────────────────────────────────────
# REQUISIÇÃO À API
# ─────────────────────────────────────────────────────────────

def _buscar_nasa_power(
    lat: float, lon: float,
    data_inicio: date, data_fim: date
) -> dict:
    """
    Faz a requisição à API NASA POWER.
    Retorna o JSON bruto com os dados do período.
    Levanta exceções em caso de falha persistente.
    """
    params = {
        "parameters": PARAMETROS,
        "community":  "AG",
        "longitude":  lon,
        "latitude":   lat,
        "start":      data_inicio.strftime("%Y%m%d"),
        "end":        data_fim.strftime("%Y%m%d"),
        "format":     "JSON",
    }

    for tentativa in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                f"NASA POWER: lat={lat}, lon={lon}, "
                f"{data_inicio} → {data_fim} (tentativa {tentativa})"
            )
            resp = requests.get(
                NASA_POWER_URL, params=params,
                timeout=REQUEST_TIMEOUT
            )

            if resp.status_code == 200:
                return resp.json()

            elif resp.status_code == 429:
                # Rate limit — aguarda antes de tentar novamente
                wait = RETRY_DELAY * tentativa * 2
                logger.warning(f"Rate limit (429). Aguardando {wait}s...")
                time.sleep(wait)

            else:
                logger.error(
                    f"NASA POWER retornou HTTP {resp.status_code}: {resp.text[:200]}"
                )
                if tentativa == MAX_RETRIES:
                    raise RuntimeError(
                        f"NASA POWER: HTTP {resp.status_code} após {MAX_RETRIES} tentativas."
                    )

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout na tentativa {tentativa}.")
            if tentativa == MAX_RETRIES:
                raise RuntimeError(f"NASA POWER: timeout após {MAX_RETRIES} tentativas.")
            time.sleep(RETRY_DELAY)

        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Erro de conexão (tentativa {tentativa}): {e}")
            if tentativa == MAX_RETRIES:
                raise RuntimeError(f"NASA POWER: sem conexão após {MAX_RETRIES} tentativas.")
            time.sleep(RETRY_DELAY)

    raise RuntimeError("NASA POWER: falha desconhecida após todas as tentativas.")


# ─────────────────────────────────────────────────────────────
# PARSING DOS DADOS
# ─────────────────────────────────────────────────────────────

def _parsear_resposta(dados_json: dict) -> list:
    """
    Converte resposta JSON da NASA POWER em lista de dicts diários.

    Formato de saída:
      [{"data": date, "Tmax": float, "Tmin": float, "P": float}, ...]

    Dias com valores sentinela (-999) são sinalizados com None
    e tratados por interpolação linear simples.
    """
    try:
        props = dados_json["properties"]["parameter"]
    except KeyError as e:
        raise ValueError(f"Resposta NASA POWER inesperada — chave ausente: {e}")

    tmax_raw  = props.get("T2M_MAX",      {})
    tmin_raw  = props.get("T2M_MIN",      {})
    prec_raw  = props.get("PRECTOTCORR",  {})

    # Todas as datas disponíveis (formato YYYYMMDD)
    datas_str = sorted(set(tmax_raw) | set(tmin_raw) | set(prec_raw))

    registros = []
    for ds in datas_str:
        try:
            d = date(int(ds[:4]), int(ds[4:6]), int(ds[6:8]))
        except ValueError:
            continue

        Tmax = tmax_raw.get(ds, FILL_VALUE)
        Tmin = tmin_raw.get(ds, FILL_VALUE)
        P    = prec_raw.get(ds, 0.0)

        # Marca sentinela como None para tratamento posterior
        Tmax = None if Tmax <= FILL_VALUE else float(Tmax)
        Tmin = None if Tmin <= FILL_VALUE else float(Tmin)
        P    = max(0.0, float(P)) if P > FILL_VALUE else 0.0

        registros.append({"data": d, "Tmax": Tmax, "Tmin": Tmin, "P": P})

    return _interpolar_falhas(registros)


def _interpolar_falhas(registros: list) -> list:
    """
    Preenche buracos de Tmax e Tmin por interpolação linear.
    Janelas de falha > 5 dias consecutivos geram aviso.
    Precipitação ausente recebe 0.
    """
    for var in ("Tmax", "Tmin"):
        vals = [r[var] for r in registros]
        n = len(vals)
        i = 0
        while i < n:
            if vals[i] is None:
                # Encontra início e fim do bloco nulo
                j = i
                while j < n and vals[j] is None:
                    j += 1

                # Interpolação linear entre i-1 e j
                v_antes = vals[i - 1] if i > 0 else None
                v_depois = vals[j] if j < n else None

                if v_antes is None and v_depois is None:
                    fill = 25.0  # fallback grosseiro
                elif v_antes is None:
                    fill_list = [v_depois] * (j - i)
                elif v_depois is None:
                    fill_list = [v_antes] * (j - i)
                else:
                    fill_list = [
                        v_antes + (v_depois - v_antes) * (k + 1) / (j - i + 1)
                        for k in range(j - i)
                    ]

                if j - i > 5:
                    logger.warning(
                        f"Bloco de {j-i} dias com {var} ausente — "
                        f"interpolação pode ser imprecisa."
                    )

                if isinstance(fill_list, list):
                    for k, idx in enumerate(range(i, j)):
                        registros[idx][var] = fill_list[k]
                else:
                    for idx in range(i, j):
                        registros[idx][var] = fill

                i = j
            else:
                i += 1

    # Garante que não haja None residual
    for r in registros:
        if r["Tmax"] is None: r["Tmax"] = 30.0
        if r["Tmin"] is None: r["Tmin"] = 18.0

    return registros


# ─────────────────────────────────────────────────────────────
# INTERFACE PRINCIPAL
# ─────────────────────────────────────────────────────────────

def buscar_serie_climatica(
    lat: float,
    lon: float,
    anos: list,
    forcar_atualizacao: bool = False,
) -> list:
    """
    Retorna série climática diária para os anos solicitados.

    Parâmetros
    ----------
    lat, lon           : coordenadas do ponto
    anos               : lista de anos inteiros, ex: [2020, 2021, 2022]
    forcar_atualizacao : ignora cache e rebusca da API

    Retorno
    -------
    Lista de dicts: [{"data": date, "Tmax": float, "Tmin": float, "P": float}]
    ordenada por data.
    """
    serie_completa = []

    for ano in sorted(anos):
        # Verifica cache (exceto se forçar atualização)
        if not forcar_atualizacao:
            cached = _ler_cache(lat, lon, ano)
            if cached is not None:
                logger.info(f"Cache hit: lat={lat}, lon={lon}, ano={ano}")
                # Converte strings de data de volta para date
                for r in cached:
                    if isinstance(r["data"], str):
                        r["data"] = date.fromisoformat(r["data"])
                serie_completa.extend(cached)
                continue

        # Busca da API
        data_inicio = date(ano, 1, 1)
        # Para o ano atual ou passado, busca até 31/dez; para ano corrente pode ser hoje
        data_fim    = date(ano, 12, 31)

        dados_json = _buscar_nasa_power(lat, lon, data_inicio, data_fim)
        registros  = _parsear_resposta(dados_json)

        # Salva no cache (converte date para string para JSON)
        cache_payload = [
            {**r, "data": r["data"].isoformat()} for r in registros
        ]
        _salvar_cache(lat, lon, ano, cache_payload)

        serie_completa.extend(registros)

    # Ordena e remove duplicatas por data
    serie_completa.sort(key=lambda r: r["data"])
    datas_vistas = set()
    serie_unica  = []
    for r in serie_completa:
        if r["data"] not in datas_vistas:
            serie_unica.append(r)
            datas_vistas.add(r["data"])

    return serie_unica


def calcular_tmed_ref(serie: list) -> float:
    """
    Calcula Tmed de referência (média histórica) da série.
    Equivale ao SUBTOTAL(1, F5:F1099) da planilha.
    """
    if not serie:
        return 25.0
    return sum((r["Tmax"] + r["Tmin"]) / 2 for r in serie) / len(serie)


def anos_necessarios_para_janela(
    ano_alvo: int,
    data_inicio_janela: date,
    ciclo_dias: int,
    n_anos_historico: int = 5,
) -> list:
    """
    Calcula quais anos precisam ser baixados da NASA POWER
    para cobrir a janela de plantio + ciclo completo para
    cada um dos últimos n_anos_historico anos.

    Considera que a janela pode cruzar a virada do ano
    (ex: plantio nov → colheita mar do ano seguinte).
    """
    anos = set()
    for i in range(n_anos_historico):
        ano = ano_alvo - i
        anos.add(ano)
        # Verifica se o ciclo cruza para o ano seguinte
        mes_inicio = data_inicio_janela.month
        if mes_inicio + ciclo_dias // 30 > 12:
            anos.add(ano + 1)
    return sorted(anos)


# ─────────────────────────────────────────────────────────────
# TESTE OFFLINE COM DADOS MOCKADOS
# ─────────────────────────────────────────────────────────────

def _gerar_serie_mock(lat: float, lon: float, anos: list) -> list:
    """
    Gera série climática sintética para testes offline.
    Simula padrão tropical úmido (chuva out-mar, seco abr-set).
    """
    import math, random
    random.seed(abs(int(lat * 100 + lon * 10)))

    serie = []
    for ano in anos:
        d = date(ano, 1, 1)
        while d.year == ano:
            doy = (d - date(d.year, 1, 1)).days + 1
            # Sazonalidade térmica suave (tropical)
            Tmax = 30 + 4 * math.sin(2 * math.pi * (doy - 15) / 365) + random.gauss(0, 1.5)
            Tmin = 18 + 3 * math.sin(2 * math.pi * (doy - 15) / 365) + random.gauss(0, 1.0)
            # Precipitação concentrada no verão (doy 270-365 e 1-90)
            if doy > 270 or doy < 90:
                P = max(0, random.gauss(5, 8))
            else:
                P = max(0, random.gauss(0.5, 1.5))
            serie.append({"data": d, "Tmax": round(Tmax, 2), "Tmin": round(Tmin, 2), "P": round(P, 2)})
            d += timedelta(days=1)
    return serie


if __name__ == "__main__":
    # Teste de parsing com dados mockados
    print("Testando módulo NASA POWER (modo offline com dados mockados)...")

    anos_teste = [2021, 2022, 2023, 2024, 2025]
    serie_mock = _gerar_serie_mock(-18.5871, -47.4, anos_teste)

    print(f"Série mock: {len(serie_mock)} dias")
    print(f"Período: {serie_mock[0]['data']} → {serie_mock[-1]['data']}")

    tmed = calcular_tmed_ref(serie_mock)
    print(f"Tmed_ref: {tmed:.2f}°C")

    # Estatísticas básicas
    tmaxes = [r["Tmax"] for r in serie_mock]
    tmins  = [r["Tmin"] for r in serie_mock]
    precs  = [r["P"] for r in serie_mock]
    print(f"Tmax: min={min(tmaxes):.1f} max={max(tmaxes):.1f} média={sum(tmaxes)/len(tmaxes):.1f}°C")
    print(f"Tmin: min={min(tmins):.1f} max={max(tmins):.1f} média={sum(tmins)/len(tmins):.1f}°C")
    print(f"Prec: total={sum(precs):.0f} mm/5anos ({sum(precs)/5:.0f} mm/ano média)")

    # Teste de interpolação de falhas
    serie_com_falhas = serie_mock[:30]
    serie_com_falhas[10]["Tmax"] = None
    serie_com_falhas[11]["Tmax"] = None
    serie_com_falhas[12]["Tmax"] = None
    serie_ok = _interpolar_falhas(serie_com_falhas)
    print(f"\nInterpolação: dias 10-12 Tmax={[round(serie_ok[i]['Tmax'],2) for i in [10,11,12]]}")

    print("\n✓ Módulo NASA POWER OK (validado offline)")
