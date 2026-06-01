.PHONY: run test clean

run:
	python3 -m src.aussie_ecolens.server

test:
	python3 -m unittest discover -s tests

clean:
	rm -rf var

cloud-config-local:
	python3 scripts/render_web_config.py local "" "" "" "" ""
