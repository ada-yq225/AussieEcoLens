# Final Report Build Notes

Generated PDF:

```text
reports/FIT5225_A2_Aussie_EcoLens_Team_Report.pdf
```

LaTeX source:

```text
reports/final_report/main.tex
```

The architecture diagram embeds a small subset of official icon PNGs:

- AWS icons from the official AWS Architecture Icons package: https://aws.amazon.com/architecture/icons/
- Google Cloud icons from the official Google Cloud Icons library: https://cloud.google.com/icons

Before Moodle submission, replace the `TBD` entries in the Team Contributions table with real names, student IDs, contribution percentages, and contribution summaries.

To rebuild the PDF, install a LaTeX engine such as Tectonic, then run from the repository root:

```bash
tectonic -X compile reports/final_report/main.tex --outdir reports/final_report/build
cp reports/final_report/build/main.pdf reports/FIT5225_A2_Aussie_EcoLens_Team_Report.pdf
```

