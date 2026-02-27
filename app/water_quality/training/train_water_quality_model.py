import argparse
from pathlib import Path
from typing import Dict, List

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = ["ph", "turbidity", "tds", "temperature", "dissolved_oxygen"]
TARGET = "water_quality_status"
CLASSES = ["SAFE", "MODERATE", "CONTAMINATED", "DANGEROUS"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Train Random Forest model for water quality classification."
    )
    parser.add_argument(
        "--input-csv",
        type=str,
        default="",
        help="Optional input CSV with feature columns and water_quality_status label.",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=4000,
        help="Synthetic sample count when --input-csv is not provided.",
    )
    parser.add_argument(
        "--output-model",
        type=str,
        default="app/water_quality/artifacts/water_quality_rf.joblib",
        help="Output path for trained model artifact.",
    )
    parser.add_argument(
        "--test-size",
        type=float,
        default=0.2,
        help="Test split size.",
    )
    parser.add_argument(
        "--random-state",
        type=int,
        default=42,
        help="Random seed.",
    )
    return parser.parse_args()


def _class_profile_ranges() -> Dict[str, Dict[str, tuple[float, float]]]:
    return {
        "SAFE": {
            "ph": (6.8, 8.2),
            "turbidity": (0.2, 5.0),
            "tds": (70.0, 300.0),
            "temperature": (15.0, 30.0),
            "dissolved_oxygen": (6.0, 10.0),
        },
        "MODERATE": {
            "ph": (6.1, 9.0),
            "turbidity": (4.0, 15.0),
            "tds": (250.0, 650.0),
            "temperature": (10.0, 35.0),
            "dissolved_oxygen": (4.0, 6.5),
        },
        "CONTAMINATED": {
            "ph": (5.0, 10.0),
            "turbidity": (15.0, 50.0),
            "tds": (600.0, 1400.0),
            "temperature": (5.0, 40.0),
            "dissolved_oxygen": (2.0, 4.2),
        },
        "DANGEROUS": {
            "ph": (3.8, 11.8),
            "turbidity": (50.0, 180.0),
            "tds": (1200.0, 3000.0),
            "temperature": (0.0, 50.0),
            "dissolved_oxygen": (0.1, 2.2),
        },
    }


def generate_synthetic_dataset(samples: int, random_state: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed=random_state)
    per_class = max(samples // len(CLASSES), 1)
    profiles = _class_profile_ranges()

    rows: List[dict] = []
    for cls in CLASSES:
        profile = profiles[cls]
        for _ in range(per_class):
            rows.append(
                {
                    "ph": rng.uniform(*profile["ph"]),
                    "turbidity": rng.uniform(*profile["turbidity"]),
                    "tds": rng.uniform(*profile["tds"]),
                    "temperature": rng.uniform(*profile["temperature"]),
                    "dissolved_oxygen": rng.uniform(*profile["dissolved_oxygen"]),
                    TARGET: cls,
                }
            )

    df = pd.DataFrame(rows)
    if len(df) > samples:
        df = df.iloc[:samples].copy()
    if len(df) < samples:
        extra = df.sample(n=samples - len(df), replace=True, random_state=random_state)
        df = pd.concat([df, extra], ignore_index=True)
    return df.sample(frac=1.0, random_state=random_state).reset_index(drop=True)


def load_dataset(input_csv: str, samples: int, random_state: int) -> pd.DataFrame:
    if input_csv:
        data_path = Path(input_csv)
        if not data_path.exists():
            raise FileNotFoundError(f"Input CSV not found: {data_path}")
        df = pd.read_csv(data_path)
    else:
        df = generate_synthetic_dataset(samples=samples, random_state=random_state)

    required_cols = FEATURES + [TARGET]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"Dataset missing required columns: {missing}")

    df = df[required_cols].copy()
    for feature in FEATURES:
        df[feature] = pd.to_numeric(df[feature], errors="coerce")

    df[TARGET] = df[TARGET].astype(str).str.strip().str.upper()
    df = df[df[TARGET].isin(CLASSES)].copy()
    if df.empty:
        raise ValueError("No valid labeled rows found after preprocessing.")

    return df


def build_pipeline(random_state: int) -> Pipeline:
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[("numeric", numeric_pipeline, FEATURES)],
        remainder="drop",
    )

    classifier = RandomForestClassifier(
        n_estimators=300,
        random_state=random_state,
        class_weight="balanced",
        n_jobs=-1,
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", classifier),
        ]
    )


def main() -> None:
    args = parse_args()
    df = load_dataset(
        input_csv=args.input_csv,
        samples=args.samples,
        random_state=args.random_state,
    )

    x = df[FEATURES]
    y = df[TARGET]

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=args.test_size,
        random_state=args.random_state,
        stratify=y,
    )

    model = build_pipeline(random_state=args.random_state)
    model.fit(x_train, y_train)

    y_pred = model.predict(x_test)
    accuracy = accuracy_score(y_test, y_pred)
    report = classification_report(y_test, y_pred, labels=CLASSES, zero_division=0)

    output_path = Path(args.output_model)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "model": model,
        "features": FEATURES,
        "target": TARGET,
        "classes": CLASSES,
        "accuracy": float(accuracy),
    }
    joblib.dump(artifact, output_path)

    print(f"Training samples: {len(x_train)}")
    print(f"Validation samples: {len(x_test)}")
    print(f"Validation accuracy: {accuracy:.4f}")
    print("Classification report:")
    print(report)
    print(f"Saved model artifact to: {output_path}")


if __name__ == "__main__":
    main()
