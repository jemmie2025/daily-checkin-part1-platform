.PHONY: bootstrap validate contracts gateway vault n8n superset hardening secrets test manifest render-apisix render-vault render-n8n render-superset manifest-write release

bootstrap:
	python3 -m pip install -r requirements-dev.txt

validate: contracts gateway vault n8n superset hardening secrets test manifest

contracts:
	python3 scripts/validate_contracts.py

gateway:
	python3 scripts/render_apisix.py --config config/apisix.gateway.example.yaml --check

vault:
	python3 scripts/render_vault.py --config config/vault.security.example.yaml --check

n8n:
	python3 scripts/render_n8n.py --check

superset:
	python3 scripts/package_superset.py --check

hardening:
	python3 scripts/validate_hardening.py

secrets:
	python3 scripts/scan_secrets.py --history

render-apisix:
	python3 scripts/render_apisix.py --config config/apisix.gateway.example.yaml --output build/apisix-resources.json

render-vault:
	python3 scripts/render_vault.py --config config/vault.security.example.yaml --output-dir vault

render-n8n:
	python3 scripts/render_n8n.py

render-superset:
	python3 scripts/package_superset.py

manifest:
	python3 scripts/release_manifest.py

manifest-write:
	python3 scripts/release_manifest.py --write

release: validate
	python3 scripts/build_release.py --output ../Daily-Checkin-Part1-Phase1-4-v0.4.0.zip

test:
	python3 -m unittest discover -s tests -p 'test_*.py' -v
