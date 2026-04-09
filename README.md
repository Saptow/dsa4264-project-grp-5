# DSA4264 Project

This repository contains our codebase for estimating the effect of being located near a “good” primary school on HDB resale prices.


The repo combines three main pieces of work:

- `data_processing/` for building cleaned and analysis-ready inputs
- `models/` for DiD and RDD notebooks, helpers, and packaged model code
- `backend/` for the FastAPI + OpenAI companion service used by the project chatbot, serviced by OpenWebUI. 

`data/` and `analysis/` are intentionally not documented here as part of the tracked repo structure. They are treated as local/generated working directories rather than core source code.

## Repository Layout

```text
DSA4264-Project/
├── backend/
├── data_processing/
├── docs/
├── models/
│   ├── did/
│   ├── rdd/
│   └── stat.ipynb
├── docker-compose.yaml
├── main.py
├── pyproject.toml
├── uv.lock
└── README.md
```

## Main Components

### `data_processing/`

Notebook and script pipeline for preparing the project inputs.

- `hdb_resale_cleaning.ipynb`: cleans and standardizes resale transactions
- `join_data.ipynb`: adds mall, rail, and school exposure variables
- `school-data.ipynb`: prepares school-level panels and boundary files
- `rail-data.ipynb`: builds the processed MRT/LRT reference table
- `create_clusters.ipynb`: constructs school-level clustering variants
- `mall_get_lat_lon.py`: geocodes malls with OneMap
- `onemapapi_key_generator.py`: fetches a fresh OneMap API token

Main data sources:

- HDB resale transactions from `data.gov.sg`
- MOE school directory from `data.gov.sg`
- URA Master Plan land-use polygons for school boundary matching from `data.gov.sg`
- MRT/LRT station GeoJSON from `data.gov.sg`
- Shopping mall list compiled from Kaggle and Wikipedia
- OneMap API for geocoding flats, schools, and malls

### `models/did/`

Difference-in-differences (DID) notebooks for pooled and unpooled good-school specifications.

- `pooled/`: pooled DiD notebooks
- `unpooled/`: school-level DiD notebooks
- `diffdiff_notebook_helpers.py`: shared DiD notebook helpers

### `models/rdd/`

Regression discontinuity (RDD) code organized around good-school and normal-school specifications.

- `core/`: shared feature engineering and modeling helpers
- `good_schools/`: good-school RDD sample-building code and result tables
- `normal_schools/`: normal-school result tables
- `paths.py`: shared path helpers

### `backend/`

Chatbot service to query model results and run simple tool-assisted analyses.

- `main.py`: API entrypoint
- `helper.py`: request assembly, model config, and tool round-trips
- `tools.py`: backend tools available to the assistant
- `schemas.py`: request/response models

### `docs/`

Project write-up materials, including the report and appendix drafts.

## Setup

This project uses `uv` for Python environment management. See [uv documentation](https://docs.astral.sh/uv/) for installation instructions.

```bash
uv sync
```

The project `pyproject.toml` includes the main research and backend dependencies. Python version set to >=3.11.7.

## Environment Variables

Create a `.env` file in the repository root for secrets used by the backend and OneMap utilities.

Common variables used in this repo:

```env
OPENAI_API_KEY=your_openai_api_key
EMAIL=your_onemap_email
PASSWORD=your_onemap_password
API_KEY=your_onemap_api_key
```

Notes:

- `OPENAI_API_KEY` is required for the chatbot backend
- `EMAIL` and `PASSWORD` are used to refresh a OneMap token
- `API_KEY` is used by notebooks or scripts that call OneMap directly


## Running The Chatbot for queries

The repo includes a FastAPI backend and an Open WebUI frontend via Docker Compose. See Docker and Docker Compose documentation for installation instructions [here](https://docs.docker.com/get-docker/).

```bash
docker compose up --build
```

After startup:

- Open WebUI is available at `http://localhost:3000`
- The FastAPI backend is available at `http://localhost:8000`
- Swagger docs are available at `http://localhost:8000/docs`
