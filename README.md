[README.md](https://github.com/user-attachments/files/27905707/README.md)
# Sistema de Modelagem de Produtividade Agrícola

## Estrutura

```
model_engine.py   # Motor de cálculo (reimplementação da planilha)
nasa_power.py     # Módulo de acesso à API NASA POWER com cache
app.py            # Interface web Streamlit
requirements.txt  # Dependências Python
```

## Instalação

```bash
pip install -r requirements.txt
```

## Execução

```bash
streamlit run app.py
```

Acesse: http://localhost:8501

## Cache NASA POWER

Os dados climáticos são armazenados em `~/.nasapower_cache/`.
Para alterar o diretório:
```bash
export NASAPOWER_CACHE_DIR=/seu/diretorio
streamlit run app.py
```

## Modo offline (testes)

Ative "Usar dados simulados" na interface para testar
sem acesso à internet. A série é sintética mas
reproduz o padrão tropical úmido com sazonalidade realista.

## Parâmetros editáveis (model_engine.py → dicionário CULTURAS)

Cada cultura possui:
- Tb_inf / Tb_sup : temperaturas base inferior e superior (°C)
- ciclo           : duração do ciclo em dias
- ST_ciclo        : soma térmica do ciclo (graus-dia)
- iem_coef        : coeficiente de produtividade potencial

Estes valores correspondem à aba `constantes` da planilha original.
