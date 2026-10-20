.PHONY: test rebuild refresh update versions snapshot restore prune export-wasm serve-wasm

# Lancer la suite de tests
test:
	uv run pytest

# Reconstruire la base DuckDB de zéro
rebuild:
	uv run python -m siba.data rebuild

# Reconstruire la base en retéléchargeant toutes les sources
refresh:
	uv run python -m siba.data rebuild --refresh

# Mise à jour incrémentale de la base
update:
	uv run python -m siba.data update

# Lister les versions de la base (la courante est marquée *)
versions:
	uv run python -m siba.data versions

# Copier la version courante avant une modification manuelle
snapshot:
	uv run python -m siba.data snapshot

# Revenir à une version : make restore V=<nom>
restore:
	uv run python -m siba.data restore $(V)

# Supprimer les anciennes versions : make prune (garde 5) ou make prune N=3
prune:
	uv run python -m siba.data prune $(if $(N),--keep $(N))

# Régénérer le notebook autonome + l'export HTML WASM interactif
export-wasm:
	uv run python scripts/export_wasm.py

# Servir l'export en local pour le tester dans un navigateur
serve-wasm:
	python -m http.server --directory results/wasm
