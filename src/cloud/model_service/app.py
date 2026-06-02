from __future__ import annotations

import base64
import json
import os
import site
import sys
import tempfile
import threading
from pathlib import Path
from typing import Dict, List

from flask import Flask, jsonify, request
from google.cloud import storage
from PIL import Image


CLASSES = [
    "Alectura_lathami",
    "Antechinus_agilis",
    "Bos_taurus",
    "Burhinus_grallarius",
    "Canis_familiaris",
    "Chalcophaps_longirostris",
    "Colluricincla_harmonica",
    "Corcorax_melanorhamphos",
    "Dacelo_novaeguineae",
    "Dama_dama",
    "Eopsaltria_australis",
    "Felis_catus",
    "Geopelia_humeralis",
    "Gymnorhina_tibicen",
    "Homo_sapiens",
    "Isoodon_macrourus",
    "Lepus_europaeus",
    "Macropus_giganteus",
    "Menura_novaehollandiae",
    "Mus_musculus",
    "Oryctolagus_cuniculus",
    "Perameles_nasuta",
    "Pitta_versicolor",
    "Rattus",
    "Rattus_fuscipes",
    "Rattus_rattus",
    "Strepera_graculina",
    "Sus_scrofa",
    "Tachyglossus_aculeatus",
    "Thylogale_stigmatica",
    "Trichosurus_caninus",
    "Trichosurus_cunninghami",
    "Trichosurus_vulpecula",
    "Varanus_varius",
    "Vombatus_ursinus",
    "Vulpes_vulpes",
    "Wallabia_bicolor",
    "Canis_dingo",
    "Capra_hircus",
    "Casuarius_casuarius",
    "Heteromyias_cinereifrons",
    "Hypsiprymnodon_moschatus",
    "Megapodius_reinwardt",
    "Notamacropus_rufogriseus",
    "Orthonyx_spaldingii",
    "Uromys_caudimaculatus",
]

MODEL_BUCKET = os.environ.get("MODEL_BUCKET", "")
CLASSIFIER_BLOB = os.environ.get("CLASSIFIER_BLOB", "course-model/model.pt")
DETECTOR_BLOB = os.environ.get("DETECTOR_BLOB", "course-model/mdv5a.pt")
MODEL_SHARED_SECRET = os.environ.get("MODEL_SHARED_SECRET", "")
DETECTION_THRESHOLD = float(os.environ.get("DETECTION_THRESHOLD", "0.05"))
PREDICTION_THRESHOLD = float(os.environ.get("PREDICTION_THRESHOLD", "0.0"))

app = Flask(__name__)
runtime_lock = threading.Lock()
runtime = None


def prepare_imports():
    for site_dir in site.getsitepackages():
        yolov5_dir = Path(site_dir) / "yolov5"
        if yolov5_dir.exists() and str(yolov5_dir) not in sys.path:
            sys.path.insert(0, str(yolov5_dir))
    import numpy as np
    import torch
    import torchvision.transforms as transforms
    from megadetector.detection import run_detector_batch

    return np, torch, transforms, run_detector_batch


def download_model_file(bucket_name: str, blob_name: str, target: Path) -> None:
    if target.exists() and target.stat().st_size > 0:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    storage.Client().bucket(bucket_name).blob(blob_name).download_to_filename(str(target))


def load_runtime():
    global runtime
    if runtime is not None:
        return runtime
    with runtime_lock:
        if runtime is not None:
            return runtime
        if not MODEL_BUCKET:
            raise RuntimeError("MODEL_BUCKET is required")
        np, torch, transforms, run_detector_batch = prepare_imports()
        model_dir = Path("/tmp/course-model")
        classifier_path = model_dir / "model.pt"
        detector_path = model_dir / "mdv5a.pt"
        download_model_file(MODEL_BUCKET, CLASSIFIER_BLOB, classifier_path)
        download_model_file(MODEL_BUCKET, DETECTOR_BLOB, detector_path)
        device = "cuda" if torch.cuda.is_available() else "cpu"
        detector = run_detector_batch.load_detector(str(detector_path), force_cpu=True)
        classifier = torch.load(classifier_path, map_location=device, weights_only=False)
        classifier.eval()
        classifier.to(device)
        transform = transforms.Compose([transforms.Resize((480, 480)), transforms.ToTensor()])
        runtime = {
            "np": np,
            "torch": torch,
            "detector": detector,
            "classifier": classifier,
            "transform": transform,
            "device": device,
        }
        return runtime


def crop_detections(image_path: Path, detections: List[Dict], output_dir: Path) -> List[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    img = Image.open(image_path).convert("RGB")
    width, height = img.size
    crops = []
    for idx, detection in enumerate(detections):
        if detection.get("category") != "1" or float(detection.get("conf", 0)) < DETECTION_THRESHOLD:
            continue
        x, y, w, h = detection["bbox"]
        crop = img.crop((int(x * width), int(y * height), int((x + w) * width), int((y + h) * height)))
        crop = crop.resize((600, 600), Image.BILINEAR)
        target = output_dir / f"{image_path.stem}-{idx}.jpg"
        crop.save(target)
        crops.append(target)
    return crops


def classify_crop(crop: Path, rt: Dict) -> Dict:
    torch = rt["torch"]
    np = rt["np"]
    image = Image.open(crop).convert("RGB")
    tensor = rt["transform"](image).unsqueeze(0).permute(0, 2, 3, 1).to(rt["device"])
    with torch.no_grad():
        logits = rt["classifier"](tensor)
        probs = torch.softmax(logits, dim=1)[0].cpu().numpy()
    best = int(np.argsort(probs)[::-1][0])
    return {"species": CLASSES[best], "confidence": float(probs[best])}


def predict_image(image_path: Path, rt: Dict) -> Dict:
    image = Image.open(image_path).convert("RGB")
    detections = rt["detector"].generate_detections_one_image(
        image,
        str(image_path),
        detection_threshold=DETECTION_THRESHOLD,
    )
    with tempfile.TemporaryDirectory() as tmp:
        crops = crop_detections(image_path, detections.get("detections", []), Path(tmp) / "crops")
        predictions = [classify_crop(crop, rt) for crop in crops]
    return {"filename": image_path.name, "detections": detections.get("detections", []), "predictions": predictions}


def summarise_tags(results: List[Dict]) -> Dict[str, int]:
    tags: Dict[str, int] = {}
    for result in results:
        for prediction in result.get("predictions", []):
            if float(prediction.get("confidence", 0)) < PREDICTION_THRESHOLD:
                continue
            species = prediction.get("species")
            if not species:
                continue
            tag = species.lower()
            tags[tag] = tags.get(tag, 0) + 1
    return tags


def check_secret() -> bool:
    if not MODEL_SHARED_SECRET:
        return True
    return request.headers.get("x-aussie-ecolens-secret") == MODEL_SHARED_SECRET


@app.get("/health")
def health():
    return jsonify(
        {
            "ok": True,
            "runtime_loaded": runtime is not None,
            "classifier_blob": CLASSIFIER_BLOB,
            "detector_blob": DETECTOR_BLOB,
            "detection_threshold": DETECTION_THRESHOLD,
            "prediction_threshold": PREDICTION_THRESHOLD,
        }
    )


@app.post("/predict")
def predict():
    if not check_secret():
        return jsonify({"error": "unauthorized"}), 401
    payload = request.get_json(force=True, silent=True) or {}
    images = payload.get("images") or []
    if not images:
        return jsonify({"error": "images are required"}), 400
    rt = load_runtime()
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for index, item in enumerate(images):
            filename = item.get("filename") or f"image-{index}.jpg"
            data = base64.b64decode(item.get("content_base64") or "")
            image_path = tmp_dir / filename
            image_path.write_bytes(data)
            results.append(predict_image(image_path, rt))
    return jsonify({"ok": True, "tags": summarise_tags(results), "results": results})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
