
from pathlib import Path
import pandas as pd

DATASET_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "UDISE_2020_21_Table_3.17.csv"
)

def load_dataset():
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATASET_PATH}")

    df = pd.read_csv(DATASET_PATH)

    df.columns = df.columns.str.strip()

    state_col = "India/State/ UT"
    boys_col = "Enrolment of Age Group - All Ages - Pre-Primary to Higher Secondary - Boys"
    girls_col = "Enrolment of Age Group - All Ages - Pre-Primary to Higher Secondary - Girls"
    total_col = "Enrolment of Age Group - All Ages - Pre-Primary to Higher Secondary - Total"

    required = [state_col, boys_col, girls_col, total_col]

    missing = [col for col in required if col not in df.columns]

    if missing:
        raise ValueError(f"Missing dataset columns: {missing}")

    df = df.loc[
        df[state_col].notna()
        & (df[state_col].str.strip().str.lower() != "india")
    ].copy()

    for col in [boys_col, girls_col, total_col]:
        df.loc[:, col] = pd.to_numeric(df[col], errors="coerce")

    df.loc[:, "gender_gap"] = df[boys_col] - df[girls_col]

    df.loc[:, "girls_enrolment_percentage"] = (
        df[girls_col] / df[total_col].replace(0, float("nan")) * 100
    ).round(2)

    return df


def get_dataset_summary():
    df = load_dataset()

    boys_col = "Enrolment of Age Group - All Ages - Pre-Primary to Higher Secondary - Boys"
    girls_col = "Enrolment of Age Group - All Ages - Pre-Primary to Higher Secondary - Girls"
    total_col = "Enrolment of Age Group - All Ages - Pre-Primary to Higher Secondary - Total"

    return {
        "total_states": len(df),
        "total_enrolment": int(df[total_col].sum()),
        "total_boys": int(df[boys_col].sum()),
        "total_girls": int(df[girls_col].sum()),
        "states": df["India/State/ UT"].tolist()
    }
