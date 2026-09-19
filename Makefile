.PHONY: rebuild update export-wasm serve-wasm

# Reconstruire la base DuckDB de zéro
rebuild:
	uv run python -m siba.db rebuild

# Mise à jour incrémentale de la base
update:
	uv run python -m siba.db update

# Régénérer le notebook autonome + l'export HTML WASM interactif
export-wasm:
	uv run python scripts/export_wasm.py

# Servir l'export en local pour le tester dans un navigateur
serve-wasm:
	python -m http.server --directory results/wasm
