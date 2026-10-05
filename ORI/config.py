"""ORI configuration - Phase 1 (data foundation).

Everything that is a *scientific decision* lives here, not buried in code,
so it can be reviewed and changed in one place.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

ROOT = Path(__file__).resolve().parent
INPUT_DATA_DIR = ROOT / "input" / "data"
OUTPUT_DIR = ROOT / "output"

DEFAULT_FILE = "Master_file_ORI.xlsx"
MASTER_SHEET = "Master"
DERIVED_SHEET_PREFIXES = ("Transect_", "Station_")   # copies of Master rows; cross-checked only

# ---------------------------------------------------------------- decisions
# USER DECISION: for nutrient parameters, values <= 0 are treated as
# "below detection" (BDL). Raw values are always preserved; BDL values are
# excluded from numerical statistics (no substitution such as DL/2, because
# detection limits are not stated in the file).
BDL_MAX_VALUE = 0.0

# ------------------------------------------------------------- thresholds
MIN_STATIONS_FOR_STATS = 10          # min independent stations for correlation/regression
MIN_STATIONS_PER_TRANSECT = 3        # below this a transect cannot be compared
LOW_POWER_STATIONS_PER_TRANSECT = 5  # below this: comparison allowed, flagged low power
BDL_WARN_FRACTION = 0.30             # parameter flagged if > 30% of stations are BDL
BDL_NO_RELATIONAL_FRACTION = 0.50    # > 50% BDL: no correlation/regression for that parameter
VERTICAL_MIN_VARYING_FRACTION = 0.10 # share of station x parameter series that must vary with depth
COORD_OUTLIER_MIN_KM = 30.0          # station this far from the rest of its transect ...
COORD_OUTLIER_FACTOR = 3.0           # ... and > factor x typical station spacing -> flagged
ROBUST_Z_FLAG = 3.5                  # station-level outlier flag (flag only, never removed)


@dataclass(frozen=True)
class ParameterSpec:
    key: str                      # canonical name used everywhere in ORI
    label: str
    header_pattern: str           # regex matched (case-insens.) at the start of the column header
    unit: str
    kind: str                     # physical | carbonate | nutrient | oxygen
    bdl_rule: bool                # apply the BDL decision (values <= 0)
    hard_range: Tuple[float, float]   # outside this = physically impossible -> flagged
    header_unit_is_unit: bool = True  # False when the bracket text in the header is not a unit
    note: Optional[str] = None


PARAMETERS = [
    ParameterSpec("salinity", "Salinity", r"^salinity", "psu", "physical", False, (0.0, 45.0)),
    ParameterSpec("temperature", "Temperature", r"^temp", "°C", "physical", False, (-2.0, 40.0)),
    ParameterSpec("pH", "pH", r"^ph", "pH units", "carbonate", False, (6.5, 9.0),
                  header_unit_is_unit=False,
                  note="Header says 'MCP'; the pH scale (total/NBS/SWS) is not stated in the file."),
    ParameterSpec("nitrate", "Nitrate", r"^nitrate", "µmol/L", "nutrient", True, (0.0, 100.0)),
    ParameterSpec("nitrite", "Nitrite", r"^nitrite", "µmol/L", "nutrient", True, (0.0, 20.0)),
    ParameterSpec("ammonia", "Ammonia", r"^ammonia", "µmol/L", "nutrient", True, (0.0, 50.0)),
    ParameterSpec("phosphate", "Orthophosphate", r"^ortho", "µmol/L", "nutrient", True, (0.0, 10.0)),
    ParameterSpec("silicate", "Silicate", r"^silicate", "µmol/L", "nutrient", True, (0.0, 200.0)),
    ParameterSpec("DO", "Dissolved oxygen", r"^do\b", "ml/l", "oxygen", False, (0.0, 12.0)),
]
PARAM_BY_KEY = {p.key: p for p in PARAMETERS}


# ================================================================= Phase 2
STATS_DIR_NAME = "statistics"          # output/statistics/  (package is `stats/`, NOT `statistics/`,
                                       # which would shadow Python's standard-library module)
RANDOM_SEED = 20260928                 # every bootstrap / permutation is reproducible
N_BOOTSTRAP = 2000
N_PERMUTATIONS = 999
CI_LEVEL = 0.95
ALPHA = 0.05                           # applied to Benjamini-Hochberg adjusted p-values
STRONG_EFFECT = 0.50                   # |rho| (or eta^2 for groups) treated as large
MODERATE_EFFECT = 0.30
MORAN_K_NEIGHBOURS = 4
LOCAL_ANOMALY_K = 4

# Pairs the plan names explicitly (all pairs are still tested; these also get regression output)
PRIORITY_PAIRS = [
    ("temperature", "salinity"), ("temperature", "DO"), ("salinity", "DO"),
    ("nitrate", "DO"), ("nitrite", "DO"), ("ammonia", "DO"), ("phosphate", "DO"),
    ("silicate", "DO"), ("pH", "DO"),
]


# ------------------------------------------------------------ Phase 2 (statistics)
RANDOM_SEED = 42            # all bootstrap / permutation results are reproducible
N_BOOTSTRAP = 2000          # bootstrap resamples for confidence intervals
N_PERMUTATIONS = 999        # permutations for Moran's I
CI_LEVEL = 0.95
ALPHA = 0.05                # applied to FDR-adjusted p-values (Benjamini-Hochberg)
STRONG_EFFECT = 0.6         # |rho| / epsilon^2 / Moran's I thresholds for evidence strength labels
MODERATE_EFFECT = 0.4
MORAN_K = 4                 # nearest neighbours in the spatial weights matrix
MIN_STATIONS_MORAN = 10

DECIMALS = {"salinity": 3, "temperature": 2, "pH": 3, "nitrate": 2, "nitrite": 3,
            "ammonia": 2, "phosphate": 2, "silicate": 2, "DO": 2}


# ------------------------------------------------------------ Phase 3 (reasoning)
IMPORTANCE_W_STRENGTH = 0.45     # weight: statistical evidence strength
IMPORTANCE_W_EFFECT = 0.30       # weight: effect size (|rho|, epsilon2, |Moran's I|)
IMPORTANCE_W_N = 0.15            # weight: sample size adequacy (n / n_stations)
IMPORTANCE_W_CORROBORATION = 0.10  # weight: same parameter also flagged by other modules
IMPORTANCE_BAND_HIGH = 70
IMPORTANCE_BAND_MEDIUM = 40

CONFOUND_CONTROL = "transect_no"      # spatial proxy used as the control variable
CONFOUND_ATTENUATION_STRONG = 0.5     # partial rho drops by >= 50% of |raw rho| -> "attenuates strongly"
CONFOUND_RESIDUAL_MIN = 0.30          # |partial rho| below this after control -> "consistent with the shared spatial trend"


# ------------------------------------------------------------ Phase 4 (oceanographic knowledge)
KNOWLEDGE_MIN_ABS_RHO_FOR_MATCH = 0.0   # library matches any FDR-significant relational result already filtered upstream


# ------------------------------------------------------------ Phase 5 (literature)
LITERATURE_STORE_PATH = INPUT_DATA_DIR.parent / "literature" / "literature_store.json"
LITERATURE_MIN_TAG_OVERLAP = 1     # minimum overlapping parameter/process tags to count as a match


# ------------------------------------------------------------ Phase 5 (literature)
LITERATURE_STORE_PATH = ROOT / "input" / "literature" / "papers.json"
LITERATURE_REGION_TAGS: list = ["Gulf of Mannar", "Southeastern Arabian Sea"]   # closest known region to this dataset's stations
ZOTERO_API_BASE = "https://api.zotero.org"   # reachable only when ORI runs with normal internet access, not in this sandbox


# ------------------------------------------------------------ Phase 3 addition (familiar/new baseline)
BASELINE_REGION_PRIORITY = ["Gulf of Mannar", "Southeastern Arabian Sea", "Indian Ocean coastal"]
BASELINE_TOLERANCE = 0.10   # observed range must exceed baseline by more than this fraction to count as "notable"
