"""Analyse d'une photo de lésion cutanée.

Le modèle est un composant remplaçable : pour en brancher un autre, écrire une classe
qui respecte `SkinClassifier`, l'ajouter à `CLASSIFIERS`, puis la sélectionner avec la
variable d'environnement SKIN_MODEL. Le reste de l'application ne change pas.
"""

import os
from functools import lru_cache
from typing import Protocol

from PIL import Image
from pydantic import BaseModel

SKIN_MODEL = os.getenv("SKIN_MODEL", "ham10000-efficientnet-b0")


class ClassScore(BaseModel):
    code: str
    label: str
    probability: float
    malignant: bool


class SkinAnalysis(BaseModel):
    model: str
    malignant_probability: float
    classes: list[ClassScore]


class SkinClassifier(Protocol):
    def analyze(self, image: Image.Image) -> SkinAnalysis: ...


class Ham10000EfficientNet:
    """EfficientNet-B0 affiné sur HAM10000 (images de dermatoscope, 7 types de lésion).

    Projet éducatif sous licence MIT, non validé cliniquement : rappel du mélanome
    de 0,58 sur son propre jeu de test.
    """

    REPO = "pthennakoon25/skinvision-ai-model"
    # Révision figée : les poids ne changent pas sans modification explicite ici.
    REVISION = "9429e5a4ef81bb90064d8cdacc5895c4fc442cf7"
    FILENAME = "best_model.pth"
    IMAGE_SIZE = 224
    MEAN = (0.485, 0.456, 0.406)
    STD = (0.229, 0.224, 0.225)

    # Dans l'ordre des sorties du modèle. La probabilité de malignité est la somme
    # des classes marquées True : mélanome, carcinome basocellulaire, et kératose
    # actinique / carcinome intra-épithélial (lésion précancéreuse ou in situ).
    CLASSES = (
        ("akiec", "Kératose actinique / carcinome intra-épithélial", True),
        ("bcc", "Carcinome basocellulaire", True),
        ("bkl", "Kératose bénigne", False),
        ("df", "Dermatofibrome", False),
        ("mel", "Mélanome", True),
        ("nv", "Nævus mélanocytaire", False),
        ("vasc", "Lésion vasculaire", False),
    )

    def __init__(self) -> None:
        # Imports différés, comme pour Whisper : PyTorch est lourd à charger.
        import timm
        import torch
        from huggingface_hub import hf_hub_download

        self._torch = torch
        path = hf_hub_download(self.REPO, self.FILENAME, revision=self.REVISION)
        # weights_only : le fichier vient d'un tiers, on n'en charge que des tenseurs.
        state = torch.load(path, map_location="cpu", weights_only=True)
        # Les auteurs enveloppent le réseau timm dans un module `backbone`.
        state = state.get("model_state_dict", state)
        state = {key.removeprefix("backbone."): value for key, value in state.items()}
        self._net = timm.create_model(
            "efficientnet_b0", pretrained=False, num_classes=len(self.CLASSES)
        )
        self._net.load_state_dict(state)
        self._net.eval()

    def analyze(self, image: Image.Image) -> SkinAnalysis:
        import numpy as np

        torch = self._torch
        resized = image.convert("RGB").resize(
            (self.IMAGE_SIZE, self.IMAGE_SIZE), Image.Resampling.BILINEAR
        )
        pixels = np.asarray(resized, dtype=np.float32) / 255.0
        pixels = (pixels - np.array(self.MEAN, dtype=np.float32)) / np.array(
            self.STD, dtype=np.float32
        )
        batch = torch.from_numpy(pixels.transpose(2, 0, 1)).unsqueeze(0)
        with torch.inference_mode():
            probabilities = torch.softmax(self._net(batch), dim=1)[0].tolist()

        classes = [
            ClassScore(code=code, label=label, probability=p, malignant=malignant)
            for (code, label, malignant), p in zip(self.CLASSES, probabilities)
        ]
        return SkinAnalysis(
            model=f"{self.REPO} (EfficientNet-B0, HAM10000)",
            malignant_probability=sum(c.probability for c in classes if c.malignant),
            classes=sorted(classes, key=lambda c: c.probability, reverse=True),
        )


CLASSIFIERS: dict[str, type[SkinClassifier]] = {
    "ham10000-efficientnet-b0": Ham10000EfficientNet,
}


@lru_cache(maxsize=1)
def get_classifier() -> SkinClassifier:
    return CLASSIFIERS[SKIN_MODEL]()
