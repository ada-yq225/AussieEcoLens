# Course Model Assets

Place the supplied course model files here when creating a complete local demo or submission zip:

```text
course_models/model.pt
course_models/mdv5a.pt
course_models/labels.txt
course_models/config.yaml
```

The large model binaries are intentionally ignored by Git because they are hundreds of MB. Use:

```bash
scripts/prepare_course_models.sh /path/to/AussieEcoLense
```

or set `MODEL_SOURCE_DIR` before running the deployment/package scripts.
