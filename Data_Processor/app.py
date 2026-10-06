
import json
from pathlib import Path
import streamlit as st

st.set_page_config(
    page_title="Papers JSON Builder",
    page_icon="📚",
    layout="wide",
)

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

DEFAULT_PROCESS_TAGS = [
    "bio_o2_consumption_n_cycle",
    "respiration_linked_acidification",
    "conservative_mixing_gradient",
    "upwelling_influenced_water",
    "temperature_do_solubility_link",
    "salinity_do_negative_link",
    "phosphate_do_negative_link",
]

DEFAULT_PARAMETER_TAGS = [
    "salinity",
    "temperature",
    "pH",
    "nitrate",
    "nitrite",
    "ammonia",
    "phosphate",
    "silicate",
    "DO",
    "PAEs",
    "PAHs",
    "others",
]

OTHER = "Other (enter manually)"


def get_process_tags():
    """
    If knowledge/library.py is available in the same project, try to
    discover process_key values from it. Otherwise use the fallback list.
    """
    try:
        import knowledge.library as library

        # Common possibilities:
        for attr_name in ("PROCESS_KEYS", "process_keys", "PROCESS_TAGS", "process_tags"):
            value = getattr(library, attr_name, None)
            if isinstance(value, (list, tuple, set)):
                return list(dict.fromkeys(str(x) for x in value))

        # If the project exposes a dictionary/list of process definitions,
        # try to extract process_key values.
        for attr_name in ("PROCESSES", "processes"):
            value = getattr(library, attr_name, None)
            if isinstance(value, dict):
                found = []
                for item in value.values():
                    if isinstance(item, dict) and "process_key" in item:
                        found.append(str(item["process_key"]))
                if found:
                    return list(dict.fromkeys(found))
            elif isinstance(value, (list, tuple)):
                found = []
                for item in value:
                    if isinstance(item, dict) and "process_key" in item:
                        found.append(str(item["process_key"]))
                if found:
                    return list(dict.fromkeys(found))
    except Exception:
        pass

    return DEFAULT_PROCESS_TAGS


def get_parameter_tags():
    """
    If config.py is available in the same project and exposes PARAMETERS,
    use its canonical keys. Otherwise use the requested fallback list.
    """
    try:
        import config

        parameters = getattr(config, "PARAMETERS", None)

        if isinstance(parameters, dict):
            return list(parameters.keys())

        if isinstance(parameters, (list, tuple, set)):
            return [str(x) for x in parameters]
    except Exception:
        pass

    return DEFAULT_PARAMETER_TAGS


PROCESS_TAGS = get_process_tags()
PARAMETER_TAGS = get_parameter_tags()


# -------------------------------------------------------------------
# Data helpers
# -------------------------------------------------------------------

def blank_claim():
    return {
        "claim": "",
        "source_location": "",
        "region_tags": [],
        "process_tags": [],
        "parameter_tags": [],
    }


def blank_paper():
    return {
        "zotero_key": "",
        "title": "",
        "authors": "",
        "year": None,
        "region_tags": [],
        "claims": [blank_claim()],
    }


def clean_string_list(values):
    if not isinstance(values, list):
        return []
    return [str(x).strip() for x in values if str(x).strip()]


def normalize_claim(claim):
    if not isinstance(claim, dict):
        claim = {}

    return {
        "claim": str(claim.get("claim", "")),
        "source_location": str(claim.get("source_location", "")),
        "region_tags": clean_string_list(claim.get("region_tags", [])),
        "process_tags": clean_string_list(claim.get("process_tags", [])),
        "parameter_tags": clean_string_list(claim.get("parameter_tags", [])),
    }


def normalize_paper(paper):
    if not isinstance(paper, dict):
        paper = {}

    year = paper.get("year")
    if year in ("", None):
        year = None
    else:
        try:
            year = int(year)
        except (TypeError, ValueError):
            year = None

    claims = paper.get("claims", [])
    if not isinstance(claims, list):
        claims = []

    return {
        "zotero_key": str(paper.get("zotero_key", "")),
        "title": str(paper.get("title", "")),
        "authors": str(paper.get("authors", "")),
        "year": year,
        "region_tags": clean_string_list(paper.get("region_tags", [])),
        "claims": [normalize_claim(c) for c in claims] or [blank_claim()],
    }


def normalize_document(data):
    if isinstance(data, dict) and isinstance(data.get("papers"), list):
        return {
            "papers": [normalize_paper(p) for p in data["papers"]]
        }
    raise ValueError("The file must contain a top-level JSON object with a 'papers' array.")


def tags_to_text(tags):
    return ", ".join(tags)


def text_to_tags(text):
    return [x.strip() for x in text.split(",") if x.strip()]


def load_json_bytes(raw_bytes):
    data = json.loads(raw_bytes.decode("utf-8-sig"))
    return normalize_document(data)


def make_download_json(data):
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def sync_from_widgets():
    """
    Streamlit widgets write their values into session_state automatically.
    This function reads them back into the structured document.
    """
    papers = st.session_state.data["papers"]

    for pi, paper in enumerate(papers):
        paper["zotero_key"] = st.session_state.get(f"zotero_{pi}", paper["zotero_key"])
        paper["title"] = st.session_state.get(f"title_{pi}", paper["title"])
        paper["authors"] = st.session_state.get(f"authors_{pi}", paper["authors"])

        year_value = st.session_state.get(f"year_{pi}", paper["year"])
        paper["year"] = int(year_value) if year_value not in ("", None) else None

        paper["region_tags"] = text_to_tags(
            st.session_state.get(f"paper_regions_{pi}", tags_to_text(paper["region_tags"]))
        )

        for ci, claim in enumerate(paper["claims"]):
            claim["claim"] = st.session_state.get(
                f"claim_{pi}_{ci}", claim["claim"]
            )
            claim["source_location"] = st.session_state.get(
                f"source_{pi}_{ci}", claim["source_location"]
            )
            claim["region_tags"] = text_to_tags(
                st.session_state.get(
                    f"claim_regions_{pi}_{ci}",
                    tags_to_text(claim["region_tags"]),
                )
            )

            process_selected = st.session_state.get(
                f"process_{pi}_{ci}", claim["process_tags"]
            )
            process_manual = st.session_state.get(
                f"process_other_{pi}_{ci}", ""
            )

            process_values = [
                x for x in process_selected if x != OTHER
            ]
            if OTHER in process_selected and process_manual.strip():
                process_values.append(process_manual.strip())
            claim["process_tags"] = list(dict.fromkeys(process_values))

            parameter_selected = st.session_state.get(
                f"parameters_{pi}_{ci}", claim["parameter_tags"]
            )
            parameter_manual = st.session_state.get(
                f"parameter_other_{pi}_{ci}", ""
            )

            parameter_values = [
                x for x in parameter_selected if x != OTHER
            ]
            if OTHER in parameter_selected and parameter_manual.strip():
                parameter_values.append(parameter_manual.strip())
            claim["parameter_tags"] = list(dict.fromkeys(parameter_values))


def initialize(data=None):
    if "data" not in st.session_state:
        st.session_state.data = data or {"papers": [blank_paper()]}


def add_paper():
    sync_from_widgets()
    st.session_state.data["papers"].append(blank_paper())
    st.rerun()


def remove_paper(index):
    sync_from_widgets()
    st.session_state.data["papers"].pop(index)
    if not st.session_state.data["papers"]:
        st.session_state.data["papers"].append(blank_paper())
    st.rerun()


def add_claim(paper_index):
    sync_from_widgets()
    st.session_state.data["papers"][paper_index]["claims"].append(blank_claim())
    st.rerun()


def remove_claim(paper_index, claim_index):
    sync_from_widgets()
    claims = st.session_state.data["papers"][paper_index]["claims"]
    claims.pop(claim_index)
    if not claims:
        claims.append(blank_claim())
    st.rerun()


# -------------------------------------------------------------------
# Header
# -------------------------------------------------------------------

st.title("📚 Papers JSON Builder")
st.caption(
    "Load an existing papers.json, edit it, add papers/claims, and download the result."
)

# -------------------------------------------------------------------
# File loading
# -------------------------------------------------------------------

with st.expander("📂 Load an existing papers.json", expanded=True):
    uploaded = st.file_uploader(
        "Choose an existing JSON file",
        type=["json"],
        help="The file should have a top-level 'papers' array.",
    )

    col1, col2 = st.columns(2)

    with col1:
        if uploaded is not None:
            if st.button("Load this file", type="primary", use_container_width=True):
                try:
                    loaded = load_json_bytes(uploaded.getvalue())
                    st.session_state.data = loaded
                    st.session_state.loaded_filename = uploaded.name
                    st.success(
                        f"Loaded {len(loaded['papers'])} paper(s) from {uploaded.name}."
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(f"Could not load the JSON file: {exc}")

    with col2:
        if st.button("Start a new blank file", use_container_width=True):
            st.session_state.data = {"papers": [blank_paper()]}
            st.session_state.loaded_filename = None
            st.rerun()


initialize()

# -------------------------------------------------------------------
# Status
# -------------------------------------------------------------------

st.info(
    f"Currently editing **{len(st.session_state.data['papers'])} paper(s)**."
    + (
        f" Loaded from **{st.session_state.loaded_filename}**."
        if st.session_state.get("loaded_filename")
        else ""
    )
)

# -------------------------------------------------------------------
# Paper editor
# -------------------------------------------------------------------

for pi, paper in enumerate(st.session_state.data["papers"]):

    with st.container(border=True):
        header_col, remove_col = st.columns([8, 1])

        with header_col:
            st.subheader(f"Paper {pi + 1}")

        with remove_col:
            if st.button("🗑️", key=f"remove_paper_{pi}", help="Remove this paper"):
                remove_paper(pi)

        col1, col2 = st.columns(2)

        with col1:
            st.text_input(
                "Zotero key",
                value=paper["zotero_key"],
                key=f"zotero_{pi}",
                placeholder="e.g. desousa1996",
            )

            st.text_input(
                "Authors",
                value=paper["authors"],
                key=f"authors_{pi}",
                placeholder="e.g. DeSousa, Dileepkumar, Sardessai...",
            )

            st.text_input(
                "Paper regions",
                value=tags_to_text(paper["region_tags"]),
                key=f"paper_regions_{pi}",
                help="Free text. Enter multiple regions separated by commas.",
                placeholder="Arabian Sea, Kerala coast",
            )

        with col2:
            st.text_input(
                "Title",
                value=paper["title"],
                key=f"title_{pi}",
                placeholder="Full paper title",
            )

            year_default = paper["year"] if paper["year"] is not None else 0
            st.number_input(
                "Year",
                min_value=0,
                max_value=3000,
                value=year_default,
                step=1,
                key=f"year_{pi}",
            )

        st.markdown("### Claims")

        for ci, claim in enumerate(paper["claims"]):

            with st.container(border=True):
                claim_header, claim_remove = st.columns([8, 1])

                with claim_header:
                    st.markdown(f"**Claim {ci + 1}**")

                with claim_remove:
                    if st.button(
                        "🗑️",
                        key=f"remove_claim_{pi}_{ci}",
                        help="Remove this claim",
                    ):
                        remove_claim(pi, ci)

                st.text_area(
                    "Claim",
                    value=claim["claim"],
                    key=f"claim_{pi}_{ci}",
                    height=120,
                    placeholder="Write a short paraphrase in your own words — not a copied sentence.",
                )

                st.text_input(
                    "Source location",
                    value=claim["source_location"],
                    key=f"source_{pi}_{ci}",
                    placeholder="e.g. p.4, section 3.2",
                )

                st.text_input(
                    "Claim regions",
                    value=tags_to_text(claim["region_tags"]),
                    key=f"claim_regions_{pi}_{ci}",
                    help="Free text. Enter multiple regions separated by commas.",
                    placeholder="Arabian Sea, Kerala coast",
                )

                st.markdown("**Process tags**")

                current_process = [
                    x for x in claim["process_tags"]
                    if x in PROCESS_TAGS
                ]
                custom_process = [
                    x for x in claim["process_tags"]
                    if x not in PROCESS_TAGS
                ]

                process_options = PROCESS_TAGS + [OTHER]

                process_default = current_process[:]
                if custom_process:
                    process_default.append(OTHER)

                selected_process = st.multiselect(
                    "Select process tags",
                    options=process_options,
                    default=process_default,
                    key=f"process_{pi}_{ci}",
                    help="Select one or more canonical process keys. Choose Other for a manual tag.",
                    label_visibility="collapsed",
                )

                st.text_input(
                    "Manual process tag (used when Other is selected)",
                    value=", ".join(custom_process),
                    key=f"process_other_{pi}_{ci}",
                    placeholder="e.g. my_custom_process_key",
                )

                st.markdown("**Parameter tags**")

                current_parameters = [
                    x for x in claim["parameter_tags"]
                    if x in PARAMETER_TAGS
                ]
                custom_parameters = [
                    x for x in claim["parameter_tags"]
                    if x not in PARAMETER_TAGS
                ]

                parameter_options = PARAMETER_TAGS + [OTHER]

                parameter_default = current_parameters[:]
                if custom_parameters:
                    parameter_default.append(OTHER)

                st.multiselect(
                    "Select parameter tags",
                    options=parameter_options,
                    default=parameter_default,
                    key=f"parameters_{pi}_{ci}",
                    help="Select the canonical parameter keys. Choose Other for a manual tag.",
                    label_visibility="collapsed",
                )

                st.text_input(
                    "Manual parameter tag (used when Other is selected)",
                    value=", ".join(custom_parameters),
                    key=f"parameter_other_{pi}_{ci}",
                    placeholder="e.g. chlorophyll_a",
                )

        st.button(
            "➕ Add another claim",
            key=f"add_claim_{pi}",
            on_click=add_claim,
            args=(pi,),
        )

st.divider()

# -------------------------------------------------------------------
# Bottom controls
# -------------------------------------------------------------------

col1, col2, col3 = st.columns(3)

with col1:
    st.button(
        "➕ Add another paper",
        type="primary",
        use_container_width=True,
        on_click=add_paper,
    )

with col2:
    if st.button("💾 Update preview", use_container_width=True):
        sync_from_widgets()
        st.success("Preview updated.")

with col3:
    sync_from_widgets()
    output_json = make_download_json(st.session_state.data)

    st.download_button(
        "⬇️ Download papers.json",
        data=output_json.encode("utf-8"),
        file_name="papers.json",
        mime="application/json",
        use_container_width=True,
    )

# -------------------------------------------------------------------
# JSON preview
# -------------------------------------------------------------------

with st.expander("🔎 Preview generated JSON"):
    sync_from_widgets()
    st.code(make_download_json(st.session_state.data), language="json")
