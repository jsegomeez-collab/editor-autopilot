"""Detecta la cara en la copia normalizada (sección 6.3).

Detector: YuNet de OpenCV (cv2.FaceDetectorYN, modelo en pipeline/modelos/).
MediaPipe 1.0.1 se descartó porque en macOS aborta al iniciar Metal incluso con
delegado CPU. YuNet da caja + ojos, que es lo que necesita el encuadre.

Muestrea ~4 fps sobre la línea de tiempo de la FUENTE y guarda caras.json:
  {"ancho", "alto", "fps_muestreo", "muestras": [{"t", "caja": [x,y,w,h], "ojos": [[x,y],[x,y]], "score"} | {"t", "caja": null}]}

Uso:
  python pipeline/detectar_cara.py <src.mp4> -o caras.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2

MODELO = Path(__file__).resolve().parent / "modelos" / "face_detection_yunet_2023mar.onnx"
FPS_MUESTREO = 4
ESCALA = 0.5  # se detecta a media resolución: suficiente y 4 veces más rápido
UMBRAL = 0.8


def detectar(video: Path, fps_muestreo: float = FPS_MUESTREO) -> dict:
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS)
    ancho = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    alto = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    paso = max(1, round(fps / fps_muestreo))
    tam = (int(ancho * ESCALA), int(alto * ESCALA))
    det = cv2.FaceDetectorYN.create(str(MODELO), "", tam, UMBRAL)

    muestras, n = [], 0
    while True:
        if not cap.grab():
            break
        if n % paso == 0:
            _, frame = cap.retrieve()
            _, caras = det.detect(cv2.resize(frame, tam))
            t = round(n / fps, 3)
            if caras is None:
                muestras.append({"t": t, "caja": None})
            else:
                c = max(caras, key=lambda f: f[2] * f[3]) / ESCALA  # la cara más grande
                muestras.append({
                    "t": t,
                    "caja": [round(float(v)) for v in c[:4]],
                    "ojos": [[round(float(c[4])), round(float(c[5]))], [round(float(c[6])), round(float(c[7]))]],
                    "score": round(float(c[-1] * ESCALA), 3),  # el score no se escala
                })
        n += 1
    cap.release()
    return {"ancho": ancho, "alto": alto, "fps_muestreo": round(fps / paso, 3), "muestras": muestras}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", type=Path)
    ap.add_argument("-o", "--salida", type=Path, required=True)
    args = ap.parse_args()
    datos = detectar(args.video)
    args.salida.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    con_cara = sum(1 for m in datos["muestras"] if m["caja"])
    print(f"guardado: {args.salida} — {con_cara}/{len(datos['muestras'])} muestras con cara")


if __name__ == "__main__":
    main()
