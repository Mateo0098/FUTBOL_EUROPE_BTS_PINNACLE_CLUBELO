# Apuestas Fixtures Pipeline

Pipeline para:
1. actualizar cuotas,
2. calcular picks por partido,
3. armar combo,
4. enviar mensajes a Telegram.

## Estructura

- `src/main_fixtures.py`: cruza `Fixtures.csv` con cuotas y genera probabilidades.
- `test_html_odds`: scraper de cuotas de Pinnacle.
- `combo_selector_fixtures.py`: construye el combo desde picks high-probability.
- `telegram_test_fixtures.py`: envía picks individuales a Telegram.
- `combo_telegram_fixtures.py`: envía el combo a Telegram.
- `src/config.py`: parámetros del modelo y filtros.
- `data/raw/`: entradas (`Fixtures.csv`, `pinnacle_urls_per_ligue.txt`, etc.).
- `data/processed/`: salidas generadas por el pipeline.

## Requisitos

- Python 3.12+
- Chrome instalado
- ChromeDriver compatible (Selenium lo usa al correr `test_html_odds`)

Instalación:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Ejecución (orden recomendado)

Desde la raíz del repo:

```powershell
python src/main_fixtures.py
python combo_selector_fixtures.py
python telegram_test_fixtures.py
python combo_telegram_fixtures.py
```

## Archivos de entrada mínimos

- `data/raw/Fixtures.csv`
- `data/raw/pinnacle_urls_per_ligue.txt`
- `bankroll.csv`

## Salidas principales

- `data/processed/matches_probs_fixtures.csv`
- `data/processed/matches_probs_fixtures_high.csv`
- `data/processed/combo_picks_fixtures.csv`
- `data/processed/cuotas_pinnacle_filtradas.csv`

## Notas

- Los scripts de Telegram hoy tienen token/chat hardcodeados. Para publicar en GitHub, conviene moverlos a variables de entorno antes de hacer público el repo.
