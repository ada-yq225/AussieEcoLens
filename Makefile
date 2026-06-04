.PHONY: run test clean package prepare-models

run:
	python3 -m src.aussie_ecolens.server

test:
	python3 -m unittest discover -s tests

clean:
	rm -rf var

cloud-config-local:
	python3 scripts/render_web_config.py local "" "" "" "" ""

prepare-models:
	@if [ -z "$(MODEL_SOURCE_DIR)" ]; then \
		echo "Set MODEL_SOURCE_DIR=/path/to/AussieEcoLense"; \
		exit 2; \
	fi
	scripts/prepare_course_models.sh "$(MODEL_SOURCE_DIR)"

package:
	scripts/package_submission.sh
