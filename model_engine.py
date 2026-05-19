"""
Motor de modelagem de produtividade agrícola
Reimplementação fiel da planilha modelagem.xlsm
Versão: 1.0 — validada numericamente
"""

import math
from datetime import date, timedelta
from dataclasses import dataclass
from typing import Optional

CULTURAS = {
    "Milho":   {"Tb_inf": 10, "Tb_sup": 32, "ciclo": 120, "ST_ciclo": 2170, "ST_floresc": 900,  "iem_coef": 3.81},
    "Feijão":  {"Tb_inf": 10, "Tb_sup": 35, "ciclo": 90,  "ST_ciclo": 1480, "ST_floresc": 720,  "iem_coef": 0.93},
    "Soja":    {"Tb_inf": 13, "Tb_sup": 40, "ciclo": 115, "ST_ciclo": 1700, "ST_floresc": 560,  "iem_coef": 1.97},
    "Algodão": {"Tb_inf": 13, "Tb_sup": 33, "ciclo": 200, "ST_ciclo": 2760, "ST_floresc": 680,  "iem_coef": 2.88},
    "Arroz":   {"Tb_inf": 10, "Tb_sup": 30, "ciclo": 110, "ST_ciclo": 1450, "ST_floresc": 970,  "iem_coef": 2.52},
    "Cana":    {"Tb_inf": 16, "Tb_sup": 35, "ciclo": 365, "ST_ciclo": 4000, "ST_floresc": 2000, "iem_coef": 2.50},
    "Trigo":   {"Tb_inf": 0,  "Tb_sup": 26, "ciclo": 120, "ST_ciclo": 1800, "ST_floresc": 900,  "iem_coef": 1.50},
}


def calcular_cad(argila_pct: float, z_cm: float) -> float:
    return round((argila_pct * 3.4611 + 41.036) / 100 * z_cm, 0)


def classificar_textura(argila_pct: float) -> str:
    if argila_pct < 15:       return "Textura arenosa"
    elif argila_pct <= 35:    return "Textura média"
    elif argila_pct <= 60:    return "Textura argilosa"
    else:                     return "Textura muito argilosa"


def calcular_iem(cultura: str, tmed_ref: float) -> float:
    return CULTURAS[cultura]["iem_coef"] * (-0.0381 * tmed_ref + 2.0252)


def calcular_astronomia(doy: int, latitude_graus: float) -> dict:
    lat_r = math.radians(latitude_graus)
    decl  = math.radians(23.45 * math.sin(math.radians((doy - 80) * 360 / 365)))
    arg   = max(-1.0, min(1.0, -math.tan(lat_r) * math.tan(decl)))
    hn    = math.acos(arg)
    N     = 2 / 15 * math.degrees(hn)
    drts  = 1 + 0.033 * math.cos(math.radians(doy * 360 / 365))
    Qo    = (24*60/math.pi * 0.082 * drts
             * (hn*math.sin(lat_r)*math.sin(decl)
                + math.cos(lat_r)*math.cos(decl)*math.sin(hn))) * 0.408
    return {"decl": decl, "hn": hn, "N": N, "drts": drts, "Qo": Qo}


def calcular_etp(Qo: float, Tmed: float) -> float:
    return 0.01 * Qo * Tmed


def calcular_gd_dufault(Tmax: float, Tmin: float, Tb_inf: float, Tb_sup: float) -> float:
    if Tmax <= Tb_sup:
        return (Tmax + Tmin) / 2 - Tb_inf
    else:
        return ((2 * Tb_sup - Tmax + Tmin) / 2) - Tb_inf


def calcular_gd_arnould(Tmax: float, Tmin: float, Tb_inf: float) -> float:
    return (Tmax + Tmin) / 2 - Tb_inf


def calcular_kc(cultura: str, d_ciclo: int, ciclo: int) -> float:
    pct = d_ciclo * 100 / ciclo
    if cultura == "Algodão":
        return -2e-6*pct**3 + 1e-4*pct**2 + 0.0119*pct + 0.3989
    elif cultura == "Arroz":
        if pct < 21: return 0.5
        return 5.3e-8*pct**4 - 1.72e-5*pct**3 + 1.516e-3*pct**2 - 0.0305*pct + 0.619
    elif cultura == "Cana":
        return 2e-6*pct**3 - 5e-4*pct**2 + 0.0373*pct + 0.3945
    elif cultura == "Feijão":
        if pct < 18: return 0.5
        return 1.3e-7*pct**4 - 2.92e-5*pct**3 + 1.916e-3*pct**2 - 0.031*pct + 0.604
    elif cultura == "Milho":
        return -2.62e-4*pct**2 + 0.0305*pct + 0.403
    elif cultura == "Soja":
        if pct < 18: return 0.5
        return 1.1e-7*pct**4 - 2.69e-5*pct**3 + 1.914e-3*pct**2 - 0.0327*pct + 0.6114
    elif cultura == "Trigo":
        if pct < 11: return 0.5
        return 8e-8*pct**4 - 1.93e-5*pct**3 + 1.29e-3*pct**2 - 0.0124*pct + 0.5117
    return 0.5


def calcular_ky(cultura: str, d_ciclo: int, ciclo: int) -> float:
    pct = d_ciclo * 100 / ciclo
    if cultura == "Algodão":
        if pct < 5:  return 0.0
        if pct < 24: return 0.2
        if pct < 63: return 0.5
        return 0.25
    elif cultura == "Arroz":
        if pct < 9:  return 0.0
        if pct < 37: return 0.2
        if pct < 50: return 0.6
        if pct < 82: return 0.5
        return 0.0
    elif cultura == "Cana":
        if pct < 8:  return 0.0
        if pct < 38: return 0.75
        if pct < 81: return 0.5
        return 0.1
    elif cultura == "Feijão":
        if pct < 10: return 0.0
        if pct < 50: return 0.2
        if pct < 70: return 1.1
        if pct < 90: return 0.75
        return 0.2
    elif cultura == "Milho":
        if pct < 9:  return 0.0
        if pct < 48: return 0.4
        if pct < 58: return 1.25
        if pct < 86: return 0.5
        return 0.2
    elif cultura == "Soja":
        if pct < 8:  return 0.0
        if pct < 38: return 0.2
        if pct < 62: return 0.8
        if pct < 88: return 1.0
        return 0.0
    elif cultura == "Trigo":
        if pct < 8:  return 0.0
        if pct < 58: return 0.2
        if pct < 66: return 0.6
        if pct < 76: return 0.5
        return 0.0
    return 0.0


@dataclass
class EstadoHidrico:
    arm: Optional[float] = None
    neg_acum: float = 0.0
    def_acum: float = 0.0


def calcular_balanco_hidrico(P: float, ETc: float, CAD: float, estado: EstadoHidrico) -> dict:
    P_ETc = P - ETc
    arm_ant = estado.arm

    if arm_ant is None:
        # Primeiro dia: inicializa
        if P_ETc >= 0:
            arm = CAD
            neg_acum = 0.0
        else:
            neg_acum = P_ETc
            arm = CAD * math.exp(neg_acum / CAD)
        arm_ant = arm
    else:
        if P_ETc < 0:
            neg_acum = P_ETc + estado.neg_acum
            arm = CAD * math.exp(neg_acum / CAD)
        else:
            arm = min(arm_ant + P_ETc, CAD)
            neg_acum = CAD * math.log(max(arm, 1e-9) / CAD)

    alt  = arm - arm_ant
    afd  = math.exp(-0.109 * ETc) * CAD

    if P_ETc > 0 or arm > (CAD - alt):
        ETr = ETc
    elif arm <= (CAD - afd) and alt < 0:
        ETr = P + abs(alt)
    else:
        ETr = ETc
    ETr = max(0.0, min(ETr, ETc))

    Def     = max(0.0, ETc - ETr)
    Exc     = max(0.0, P_ETc - alt) if arm >= CAD else 0.0
    ETr_ETc = ETr / ETc if ETc > 0 else 1.0

    estado.arm      = arm
    estado.neg_acum = neg_acum
    estado.def_acum += Def

    return {
        "P_ETc": P_ETc, "neg_acum": neg_acum, "arm": arm,
        "afd": afd, "alt": alt, "ETr": ETr, "Def": Def,
        "def_acum": estado.def_acum, "Exc": Exc, "ETr_ETc": ETr_ETc,
    }


def calcular_perda_hidrica(ky: float, ETr_ETc: float, ciclo: int, perda_acum_ant: float) -> dict:
    perda_dia  = (100 / ciclo * 3.2) * ky * (1 - ETr_ETc)
    perda_acum = perda_acum_ant + perda_dia
    prod_pct   = max(0.0, 100.0 - perda_acum)
    return {"perda_dia": perda_dia, "perda_acum": perda_acum, "prod_atingivel_pct": prod_pct}


def calcular_ppb(Qo: float, Tmed: float) -> dict:
    cTc  = -0.0425 + 0.035*Tmed + 0.00325*Tmed**2 - 0.0000925*Tmed**3
    cTn  =  0.583  + 0.014*Tmed + 0.0013 *Tmed**2 - 0.000037 *Tmed**3
    PPBc = (107.2 + 0.36  * Qo) * cTc * 0.5
    PPBn = (31.7  + 0.219 * Qo) * cTn * 0.5
    return {"cTc": cTc, "cTn": cTn, "PPBc": PPBc, "PPBn": PPBn, "PPBp": PPBc + PPBn}


def calcular_iaf_ciaf(GDA: float) -> dict:
    try:
        iaf_raw = math.exp(-14.9457) * (GDA ** 3.0187) * math.exp(-0.00439 * GDA)
    except (ValueError, OverflowError):
        iaf_raw = 0.0
    IAF  = min(5.0, max(0.0, iaf_raw))
    CIAF = 0.0093 + 0.185 * IAF - 0.0175 * IAF**2
    return {"IAF": IAF, "CIAF": CIAF}


def calcular_cr(Tmed: float) -> float:
    return 0.5 if Tmed >= 20 else 0.6


def simular_ciclo(
    cultura: str,
    data_plantio: date,
    serie_climatica: list,
    latitude: float,
    argila_pct: float,
    z_cm: float,
    tmed_ref: float,
) -> dict:
    p      = CULTURAS[cultura]
    Tb_inf = p["Tb_inf"]
    Tb_sup = p["Tb_sup"]
    ciclo  = p["ciclo"]

    CAD = calcular_cad(argila_pct, z_cm)
    Iem = calcular_iem(cultura, tmed_ref)

    data_fim_busca = data_plantio + timedelta(days=ciclo + 30)
    serie = [d for d in serie_climatica
             if data_plantio <= d["data"] <= data_fim_busca]

    estado     = EstadoHidrico()
    GDA_acum   = 0.0
    d_ciclo    = 0
    perda_acum = 0.0
    PPR_acum   = 0.0
    serie_diaria = []

    for dia in serie:
        if d_ciclo >= ciclo:
            break

        data = dia["data"]
        Tmax = float(dia["Tmax"])
        Tmin = float(dia["Tmin"])
        P    = float(dia.get("P", 0.0))
        Tmed = (Tmax + Tmin) / 2

        doy   = (data - date(data.year, 1, 1)).days + 1
        astro = calcular_astronomia(doy, latitude)
        Qo    = astro["Qo"]
        ETP   = calcular_etp(Qo, Tmed)

        GD = calcular_gd_dufault(Tmax, Tmin, Tb_inf, Tb_sup)
        GDA_acum += max(0.0, GD)

        d_ciclo += 1
        Kc  = calcular_kc(cultura, d_ciclo, ciclo)
        Ky  = calcular_ky(cultura, d_ciclo, ciclo)
        ETc = ETP * Kc

        bh = calcular_balanco_hidrico(P, ETc, CAD, estado)

        ph = calcular_perda_hidrica(Ky, bh["ETr_ETc"], ciclo, perda_acum)
        perda_acum = ph["perda_acum"]

        ppb     = calcular_ppb(Qo, Tmed)
        iaf_res = calcular_iaf_ciaf(GDA_acum)
        CR      = calcular_cr(Tmed)
        PPR_dia = ppb["PPBp"] * iaf_res["CIAF"] * CR * Iem
        PPR_acum += PPR_dia

        prod_ating = PPR_acum * ph["prod_atingivel_pct"] / 100

        serie_diaria.append({
            "data": data, "d_ciclo": d_ciclo, "GDA": GDA_acum,
            "Tmax": Tmax, "Tmin": Tmin, "Tmed": Tmed, "P": P,
            "Qo": Qo, "ETP": ETP, "Kc": Kc, "ETc": ETc,
            "arm": bh["arm"], "ETr": bh["ETr"],
            "Def": bh["Def"], "def_acum": bh["def_acum"],
            "ETr_ETc": bh["ETr_ETc"], "Ky": Ky,
            "perda_dia": ph["perda_dia"], "perda_acum": ph["perda_acum"],
            "prod_atingivel_pct": ph["prod_atingivel_pct"],
            "IAF": iaf_res["IAF"], "CIAF": iaf_res["CIAF"],
            "PPBp": ppb["PPBp"], "PPR_dia": PPR_dia,
            "PPR_acum": PPR_acum, "prod_atingivel_kgha": prod_ating,
        })

    if serie_diaria:
        u = serie_diaria[-1]
        return {
            "cultura": cultura, "data_plantio": data_plantio,
            "latitude": latitude, "argila_pct": argila_pct,
            "z_cm": z_cm, "CAD": CAD, "Iem": Iem,
            "ciclo_dias": u["d_ciclo"],
            "deficit_total_mm": u["def_acum"],
            "prod_atingivel_pct": u["prod_atingivel_pct"],
            "prod_atingivel_kgha": u["prod_atingivel_kgha"],
            "serie_diaria": serie_diaria,
        }
    return {
        "cultura": cultura, "data_plantio": data_plantio,
        "ciclo_dias": 0, "deficit_total_mm": 0.0,
        "prod_atingivel_pct": 0.0, "prod_atingivel_kgha": 0.0,
        "serie_diaria": [],
    }


def simular_janela(
    cultura: str,
    ano: int,
    data_inicio_janela: date,
    data_fim_janela: date,
    passo_dias: int,
    serie_climatica: list,
    latitude: float,
    argila_pct: float,
    z_cm: float,
    tmed_ref: float,
) -> dict:
    resultados = []
    delta = (data_fim_janela - data_inicio_janela).days

    for offset in range(0, delta + 1, passo_dias):
        ref = data_inicio_janela + timedelta(days=offset)
        try:
            dp = date(ano, ref.month, ref.day)
        except ValueError:
            continue

        res = simular_ciclo(
            cultura=cultura, data_plantio=dp,
            serie_climatica=serie_climatica, latitude=latitude,
            argila_pct=argila_pct, z_cm=z_cm, tmed_ref=tmed_ref,
        )
        if res["ciclo_dias"] == 0:
            continue

        resultados.append({
            "data_plantio": dp,
            "prod_atingivel_kgha": res["prod_atingivel_kgha"],
            "prod_atingivel_pct":  res["prod_atingivel_pct"],
            "deficit_total_mm":    res["deficit_total_mm"],
        })

    if not resultados:
        return {"ano": ano, "valido": False}

    import numpy as np

    vals = [r["prod_atingivel_kgha"] for r in resultados]

    # Percentis estatísticos — linha central = P70 (consistente com planilha)
    p10 = float(np.percentile(vals, 10))
    p30 = float(np.percentile(vals, 30))
    p50 = float(np.percentile(vals, 50))
    p70 = float(np.percentile(vals, 70))
    p90 = float(np.percentile(vals, 90))

    # Déficit e % atingível do dia central (referência interna)
    idx_mid = len(resultados) // 2
    rm      = resultados[idx_mid]

    return {
        "ano": ano, "valido": True,
        "n_simulacoes":       len(resultados),
        "prod_ating_p10":     p10,
        "prod_ating_p30":     p30,
        "prod_ating_p50":     p50,
        "prod_ating_p70":     p70,   # linha central do gráfico
        "prod_ating_p90":     p90,
        "prod_ating_min":     float(np.min(vals)),
        "prod_ating_max":     float(np.max(vals)),
        "prod_ating_medio":   p50,   # retrocompatibilidade — agora = P70
        "prod_ating_pct":     rm["prod_atingivel_pct"],
        "deficit_medio_mm":   rm["deficit_total_mm"],
        "data_plantio_medio": rm["data_plantio"],
        "resultados_detalhados": resultados,
    }
