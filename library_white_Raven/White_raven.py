import base64
import hmac
import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import streamlit as st

st.set_page_config(page_title='White Raven', page_icon='🪶', layout='wide')

# ---------------------------------------------------------------------------
# DEFAULT TAG LISTS
# Tags and seas you add later are stored by the 🔄 Refresh button in tags.json
# (next to the library files, or in your GitHub repo) and are merged into these
# lists every time the app starts. You can also edit the defaults here by hand.
# ---------------------------------------------------------------------------
PROCESS_TAGS = [
    'bio_o2_consumption_n_cycle',
    'respiration_linked_acidification',
    'conservative_mixing_gradient',
    'upwelling_influenced_water',
    'temperature_do_solubility_link',
    'salinity_do_negative_link',
    'phosphate_do_negative_link',
]
PARAMETER_TAGS = [
    'salinity',
    'temperature',
    'pH',
    'nitrate',
    'nitrite',
    'ammonia',
    'phosphate',
    'silicate',
    'DO',
    'PAEs',
    'PAHs',
    'others',
]
SEAS = [
    'Amundsen Sea',
    'Andaman Sea',
    'Arabian Sea',
    'Arafura Sea',
    'Baltic Sea',
    'Barents Sea',
    'Bay of Bengal',
    'Beaufort Sea',
    'Bering Sea',
    'Black Sea',
    'Caribbean Sea',
    'Celebes Sea',
    'Chukchi Sea',
    'Coral Sea',
    'East China Sea',
    'East Siberian Sea',
    'Greenland Sea',
    'Gulf of Aden',
    'Gulf of Mexico',
    'Gulf of Oman',
    'Irish Sea',
    'Java Sea',
    'Kara Sea',
    'Labrador Sea',
    'Laccadive Sea',
    'Laptev Sea',
    'Mediterranean Sea',
    'North Sea',
    'Norwegian Sea',
    'Persian Gulf',
    'Philippine Sea',
    'Red Sea',
    'Ross Sea',
    'Sargasso Sea',
    'Scotia Sea',
    'Sea of Japan',
    'Sea of Okhotsk',
    'South China Sea',
    'Tasman Sea',
    'Timor Sea',
    'Weddell Sea',
    'White Sea',
    'Yellow Sea',
]
# ---------------------------------------------------------------------------
# END TAG LISTS
# ---------------------------------------------------------------------------

OCEANS = ['Pacific Ocean', 'Atlantic Ocean', 'Indian Ocean', 'Southern Ocean', 'Arctic Ocean']
OTHER = 'Other'
MAX_CLAIMS = 10

SOURCE_FILE = Path(__file__).resolve()
TAG_LISTS = {'PROCESS_TAGS': PROCESS_TAGS, 'PARAMETER_TAGS': PARAMETER_TAGS, 'SEAS': SEAS}

# Streamlit widget keys start with one of these; used to clear stale widget state.
WIDGET_PREFIXES = ('citation_', 'region_', 'claim_', 'process_', 'param_')


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def clean(value):
    return '' if value is None else str(value).strip()


def unique(values):
    return list(dict.fromkeys(values))


def split_manual(text):
    return [part.strip() for part in text.split(',') if part.strip()]


def merge_tags(selected, manual_text):
    """Combine ticked options with manual entries (manual only counts if Other is ticked)."""
    values = [x for x in selected if x != OTHER]
    if OTHER in selected:
        values += split_manual(manual_text)
    return unique(values)


# ---------------------------------------------------------------------------
# Blank records
# ---------------------------------------------------------------------------
def blank_region():
    return {'ocean': '', 'sea': '', 'region_3': '', 'region_4': '', 'region_5': ''}


def blank_claim():
    return {'claim': '', 'process_tags': [], 'parameter_tags': []}


def blank_paper():
    return {'citation': '', 'region': blank_region(), 'claims': [blank_claim()]}


# ---------------------------------------------------------------------------
# Loading / migrating older JSON formats
# ---------------------------------------------------------------------------
def normalize_region(raw):
    if not isinstance(raw, dict):
        raw = {}
    return {
        'ocean': clean(raw.get('ocean')),
        'sea': clean(raw.get('sea')),
        'region_3': clean(raw.get('region_3', raw.get('subregion_3'))),
        'region_4': clean(raw.get('region_4', raw.get('subregion_4'))),
        'region_5': clean(raw.get('region_5', raw.get('subregion_5'))),
    }


def normalize_claim(raw):
    if not isinstance(raw, dict):
        raw = {}
    return {
        'claim': clean(raw.get('claim')),
        'process_tags': [clean(x) for x in raw.get('process_tags', []) if clean(x)],
        'parameter_tags': [clean(x) for x in raw.get('parameter_tags', []) if clean(x)],
    }


def build_citation(raw):
    if 'citation' in raw:
        return clean(raw.get('citation'))
    authors = clean(raw.get('authors'))
    year = raw.get('year')
    title = clean(raw.get('title'))
    key = clean(raw.get('zotero_key'))
    parts = [authors, f'{year}.' if year not in ('', None) else '', title]
    citation = ' '.join(x for x in parts if x)
    return f'{citation} [{key}]'.strip() if key else citation


def build_region(raw, claims):
    """Region is paper-level. Older files stored it per claim or as region_tags."""
    if isinstance(raw.get('region'), dict):
        return normalize_region(raw['region'])

    region = blank_region()
    if isinstance(raw.get('region_tags'), list):
        region['region_3'] = ', '.join(clean(x) for x in raw['region_tags'] if clean(x))
        return region

    for old_claim in claims:
        if not isinstance(old_claim, dict):
            continue
        if isinstance(old_claim.get('region'), dict):
            return normalize_region(old_claim['region'])
        old_tags = old_claim.get('region_tags', [])
        if isinstance(old_tags, list) and old_tags:
            region['region_3'] = ', '.join(clean(x) for x in old_tags if clean(x))
            return region
    return region


def normalize_paper(raw):
    if not isinstance(raw, dict):
        raw = {}
    claims = raw.get('claims', [])
    if not isinstance(claims, list):
        claims = []
    return {
        'citation': build_citation(raw),
        'region': build_region(raw, claims),
        'claims': [normalize_claim(c) for c in claims] or [blank_claim()],
    }


def normalize(data):
    if not isinstance(data, dict) or not isinstance(data.get('papers'), list):
        raise ValueError("JSON must contain a top-level 'papers' array.")
    return {'papers': [normalize_paper(p) for p in data['papers']]}


# ---------------------------------------------------------------------------
# Widget state <-> data
# ---------------------------------------------------------------------------
def sync():
    """Copy what is currently typed/selected in the widgets into st.session_state.data."""
    ss = st.session_state
    for pi, paper in enumerate(ss.data['papers']):
        paper['citation'] = ss.get(f'citation_{pi}', paper['citation'])

        region = paper['region']
        region['ocean'] = ss.get(f'region_ocean_{pi}', region['ocean'])
        sea = ss.get(f'region_sea_{pi}', region['sea'])
        if sea == OTHER:
            sea = ss.get(f'region_sea_other_{pi}', '').strip()
        region['sea'] = sea
        region['region_3'] = ss.get(f'region_region_3_{pi}', region['region_3'])
        region['region_4'] = ss.get(f'region_region_4_{pi}', region['region_4'])
        region['region_5'] = ss.get(f'region_region_5_{pi}', region['region_5'])

        for ci, claim in enumerate(paper['claims']):
            claim['claim'] = ss.get(f'claim_{pi}_{ci}', claim['claim'])
            claim['process_tags'] = merge_tags(
                ss.get(f'process_{pi}_{ci}', claim['process_tags']),
                ss.get(f'process_other_{pi}_{ci}', ''),
            )
            claim['parameter_tags'] = merge_tags(
                ss.get(f'param_{pi}_{ci}', claim['parameter_tags']),
                ss.get(f'param_other_{pi}_{ci}', ''),
            )


def reset_widgets():
    """Forget widget state so every widget is rebuilt from st.session_state.data."""
    for key in list(st.session_state):
        if key.startswith(WIDGET_PREFIXES):
            del st.session_state[key]


# ---------------------------------------------------------------------------
# Storage: a local folder (VS Code) or a GitHub repo (Streamlit Cloud)
# GitHub is used when the app's secrets contain a [github] section.
# ---------------------------------------------------------------------------
LIBRARY_FOLDER = '.'  # local mode: '.' = the same folder as this file
TAGS_FILE = 'tags.json'

GITHUB_HINTS = {
    401: 'the token was rejected (wrong or expired)',
    403: 'the token cannot write to this repo (needs Contents: read and write) or a rate limit was hit',
    404: 'repo, branch or folder not found, or the token has no access to it',
    409: 'the file changed while saving',
    422: 'the file changed while saving, or the branch does not exist',
}


class GitHubError(OSError):
    def __init__(self, code, message):
        super().__init__(f'GitHub {code}: {message}')
        self.code = code


def github_config():
    """Settings from the [github] secrets section; None means "use local files"."""
    try:
        section = dict(st.secrets['github'])
    except Exception:  # no secrets file or no [github] section
        return None
    missing = [key for key in ('token', 'repo') if not section.get(key)]
    if missing:
        raise GitHubError(0, f"the [github] secrets section is missing: {', '.join(missing)}")
    return {'token': section['token'], 'repo': section['repo'],
            'branch': section.get('branch', 'main'), 'folder': str(section.get('folder', '')).strip('/')}


def gh_api(cfg, name, method='GET', payload=None):
    path = '/'.join(part for part in (cfg['folder'], name) if part)
    url = f"https://api.github.com/repos/{cfg['repo']}/contents/{urllib.parse.quote(path)}"
    if method == 'GET':
        url += '?ref=' + urllib.parse.quote(cfg['branch'])
    body = json.dumps(payload).encode('utf-8') if payload is not None else None
    request = urllib.request.Request(url, data=body, method=method, headers={
        'Authorization': f"Bearer {cfg['token']}",
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'User-Agent': 'white-raven',
        'Content-Type': 'application/json',
    })
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as err:
        raise GitHubError(err.code, GITHUB_HINTS.get(err.code, err.reason)) from err


def gh_fetch(cfg, name):
    """(text, sha) of a file in the repo, or (None, None) if it does not exist."""
    try:
        info = gh_api(cfg, name)
    except GitHubError as err:
        if err.code == 404:
            return None, None
        raise
    if info.get('encoding') != 'base64':
        raise GitHubError(0, f'{name} is too large to read through the GitHub API')
    return base64.b64decode(info['content']).decode('utf-8-sig'), info['sha']


def gh_put(cfg, name, text, message, sha):
    payload = {'message': message, 'branch': cfg['branch'],
               'content': base64.b64encode(text.encode('utf-8')).decode('ascii')}
    if sha:
        payload['sha'] = sha
    gh_api(cfg, name, 'PUT', payload)


@st.cache_data(ttl=60, show_spinner=False)
def gh_read_cached(repo, branch, folder, name, _token):
    cfg = {'token': _token, 'repo': repo, 'branch': branch, 'folder': folder}
    return gh_fetch(cfg, name)[0]


def library_dir():
    text = st.session_state.get('lib_dir_input', LIBRARY_FOLDER).strip() or LIBRARY_FOLDER
    folder = Path(text)
    return (folder if folder.is_absolute() else SOURCE_FILE.parent / folder).resolve()


def store_read(name):
    """Text of a stored file, or None if it does not exist yet (GitHub reads are cached for a minute)."""
    cfg = github_config()
    if cfg:
        return gh_read_cached(cfg['repo'], cfg['branch'], cfg['folder'], name, cfg['token'])
    path = library_dir() / name
    return path.read_text(encoding='utf-8-sig') if path.exists() else None


def store_update(name, transform, message):
    """Read the latest copy, apply transform(text_or_None) -> new text (or None = no change), write it back.

    On GitHub this commits to the repo; if someone else changed the file in the meantime
    the latest copy is fetched again and the change is re-applied.
    """
    cfg = github_config()
    if not cfg:
        path = library_dir() / name
        new_text = transform(path.read_text(encoding='utf-8-sig') if path.exists() else None)
        if new_text is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_name(path.name + '.tmp')
            temp.write_text(new_text, encoding='utf-8')
            temp.replace(path)
        return

    for attempt in range(3):
        text, sha = gh_fetch(cfg, name)
        new_text = transform(text)
        if new_text is None:
            return
        try:
            gh_put(cfg, name, new_text, message, sha)
            st.cache_data.clear()
            return
        except GitHubError as err:
            if err.code not in (409, 422) or attempt == 2:
                raise


def storage_label():
    try:
        cfg = github_config()
    except OSError:
        return 'storage'
    return f"GitHub ({cfg['repo']}, branch {cfg['branch']})" if cfg else 'the library folder'


# ---------------------------------------------------------------------------
# Optional editor password: friends can browse and download, only you can save
# Set it in the app's secrets:  [app]  edit_password = "your-password"
# With no password set (e.g. running locally) everything is open.
# ---------------------------------------------------------------------------
def edit_password():
    try:
        return str(st.secrets['app']['edit_password'])
    except Exception:  # no secrets file or no [app] section
        return ''


def can_edit():
    expected = edit_password()
    if not expected:
        return True
    entered = st.session_state.get('editor_password_input', '')
    return hmac.compare_digest(entered.encode('utf-8'), expected.encode('utf-8'))


LOCKED_MESSAGE = 'Saving is locked. Enter the editor password in the sidebar to save to the library or save new tags.'


# ---------------------------------------------------------------------------
# New tags / seas: kept in tags.json and merged into the lists at start-up
# ---------------------------------------------------------------------------
EXTRA_TAG_KEYS = {'PROCESS_TAGS': 'process_tags', 'PARAMETER_TAGS': 'parameter_tags', 'SEAS': 'seas'}
LIST_LABELS = {'PROCESS_TAGS': 'process tag', 'PARAMETER_TAGS': 'parameter tag', 'SEAS': 'sea / gulf'}


def parse_object(text):
    data = json.loads(text) if text and text.strip() else {}
    return data if isinstance(data, dict) else {}


def apply_extra_tags():
    """Merge the tags saved in tags.json into the default lists (runs at every start-up)."""
    try:
        extras = parse_object(store_read(TAGS_FILE))
        st.session_state.tags_error = None
    except (OSError, ValueError) as err:
        st.session_state.tags_error = str(err)
        return
    for name, key in EXTRA_TAG_KEYS.items():
        values = extras.get(key, [])
        for tag in values if isinstance(values, list) else []:
            tag = clean(tag)
            if tag and tag not in TAG_LISTS[name]:
                TAG_LISTS[name].append(tag)
    TAG_LISTS['SEAS'].sort(key=str.lower)


def find_new_entries():
    """Return {list_name: [values]} for tags/seas used in the data but missing from the lists."""
    used = {name: [] for name in TAG_LISTS}
    for paper in st.session_state.data['papers']:
        if paper['region']['sea']:
            used['SEAS'].append(paper['region']['sea'])
        for claim in paper['claims']:
            used['PROCESS_TAGS'] += claim['process_tags']
            used['PARAMETER_TAGS'] += claim['parameter_tags']

    new = {}
    for name, values in used.items():
        known = set(TAG_LISTS[name])
        fresh = [v for v in unique(values) if v not in known]
        if fresh:
            new[name] = fresh
    return new


def refresh():
    sync()
    if not can_edit():
        st.session_state.flash = ('error', LOCKED_MESSAGE)
        return
    new = find_new_entries()
    if not new:
        st.session_state.flash = ('info', 'Nothing new to save — every tag and sea is already stored.')
        reset_widgets()
        return

    def add_tags(text):
        data = parse_object(text)
        for name, fresh in new.items():
            key = EXTRA_TAG_KEYS[name]
            existing = data.get(key, [])
            data[key] = unique((existing if isinstance(existing, list) else []) + fresh)
        return json.dumps(data, ensure_ascii=False, indent=2) + '\n'

    try:
        store_update(TAGS_FILE, add_tags, f'White Raven: add new tags to {TAGS_FILE}')
        lines = [f"{LIST_LABELS[n]}: {', '.join(v)}" for n, v in new.items()]
        st.session_state.flash = ('success', f'Saved to {storage_label()} → ' + ' | '.join(lines))
    except (OSError, ValueError) as err:
        st.session_state.flash = ('error', f'Could not save the new tags: {err}')
    reset_widgets()


# ---------------------------------------------------------------------------
# Library: one JSON file per section (same format as papers.json)
# ---------------------------------------------------------------------------
SECTIONS = {
    'Introduction': 'introduction.json',
    'Results': 'results.json',
    'Discussion': 'discussion.json',
}


def citation_key(citation):
    return ' '.join(citation.lower().split())


def parse_papers(text):
    return normalize(json.loads(text))['papers'] if text and text.strip() else []


def read_section(section):
    """Papers stored in one library file ([] if the file does not exist yet)."""
    return parse_papers(store_read(SECTIONS[section]))


def claim_key(text):
    return ' '.join(text.lower().split())


def save_library():
    """Save the papers being edited into the chosen library file (papers are matched by citation).

    Default: if the paper is already stored, only claims that are not stored yet are added, so
    nobody's earlier claims are lost. With "replace" ticked, the stored paper is overwritten
    (use it when you loaded a paper from the library to edit or delete claims).
    """
    sync()
    if not can_edit():
        st.session_state.flash = ('error', LOCKED_MESSAGE)
        return
    section = st.session_state.get('save_section', 'Introduction')
    replace = bool(st.session_state.get('save_replace', False))
    filename = SECTIONS[section]
    tally = {}

    def merge(text):
        tally.update(added=0, merged=0, replaced=0, same=0, skipped=0)
        stored = parse_papers(text)
        index = {citation_key(p['citation']): i for i, p in enumerate(stored)}
        for paper in st.session_state.data['papers']:
            claims = [c for c in paper['claims'] if c['claim'].strip()]
            if not paper['citation'].strip() or not claims:
                tally['skipped'] += 1
                continue
            entry = {'citation': paper['citation'], 'region': paper['region'], 'claims': claims}
            key = citation_key(entry['citation'])
            if key not in index:
                index[key] = len(stored)
                stored.append(entry)
                tally['added'] += 1
            elif replace:
                stored[index[key]] = entry
                tally['replaced'] += 1
            else:
                existing = stored[index[key]]
                seen = {claim_key(c['claim']) for c in existing['claims']}
                fresh = [c for c in claims if claim_key(c['claim']) not in seen]
                if not fresh:
                    tally['same'] += 1
                    continue
                existing['claims'] += fresh
                for field, value in entry['region'].items():  # fill region gaps, never overwrite
                    if value and not existing['region'].get(field):
                        existing['region'][field] = value
                tally['merged'] += len(fresh)
        if not (tally['added'] or tally['merged'] or tally['replaced']):
            return None
        return json.dumps({'papers': stored}, ensure_ascii=False, indent=2) + '\n'

    try:
        store_update(filename, merge, f'White Raven: update {filename}')
    except (OSError, ValueError) as err:
        st.session_state.flash = ('error', f'Could not save to {filename}: {err}')
        return

    if not (tally['added'] or tally['merged'] or tally['replaced']):
        if tally['same']:
            st.session_state.flash = ('info', 'Nothing new — those claims are already in the library.')
        else:
            st.session_state.flash = ('warning', 'Nothing saved — each paper needs a citation and at least one claim.')
        return
    parts = []
    if tally['added']:
        parts.append(f"{tally['added']} new paper(s)")
    if tally['merged']:
        parts.append(f"{tally['merged']} claim(s) added to papers already stored")
    if tally['replaced']:
        parts.append(f"{tally['replaced']} paper(s) replaced")
    note = f" ({tally['skipped']} skipped: no citation or no claims)" if tally['skipped'] else ''
    st.session_state.flash = ('success', f'Saved to {filename} in {storage_label()}: ' + ', '.join(parts) + '.' + note)


def load_from_library():
    section = st.session_state.get('load_section', 'Introduction')
    try:
        papers = read_section(section)
    except (OSError, ValueError) as err:
        st.session_state.flash = ('error', f'Could not read {SECTIONS[section]}: {err}')
        return
    if not papers:
        st.session_state.flash = ('warning', f'{SECTIONS[section]} is empty or does not exist yet.')
        return
    st.session_state.data = {'papers': papers}
    st.session_state.loaded_filename = f'library / {SECTIONS[section]}'
    st.session_state.save_replace = True  # editing a stored paper: save should replace it
    reset_widgets()


def collect_rows(sections):
    """Flatten the chosen library files into one row per claim."""
    rows = []
    for section in sections:
        try:
            papers = read_section(section)
        except (OSError, ValueError) as err:
            st.error(f'Could not read {SECTIONS[section]}: {err}')
            continue
        for paper in papers:
            for claim in paper['claims']:
                rows.append({
                    'section': section,
                    'citation': paper['citation'],
                    'region': paper['region'],
                    'claim': claim['claim'],
                    'process_tags': claim['process_tags'],
                    'parameter_tags': claim['parameter_tags'],
                })
    return rows


def tag_options(listed, rows, field):
    """All listed tags plus any used in the library but not listed, with usage counts."""
    counts = {}
    for row in rows:
        for tag in row[field]:
            counts[tag] = counts.get(tag, 0) + 1
    extras = sorted(t for t in counts if t not in listed)
    return list(listed) + extras, counts


def row_matches(row, process, parameter, match_all, oceans, seas, region_text):
    wanted = {('p', t) for t in process} | {('m', t) for t in parameter}
    have = {('p', t) for t in row['process_tags']} | {('m', t) for t in row['parameter_tags']}
    if wanted:
        if match_all and not wanted <= have:
            return False
        if not match_all and not wanted & have:
            return False

    region = row['region']
    if oceans and region['ocean'] not in oceans:
        return False
    if seas and region['sea'] not in seas:
        return False
    if region_text:
        haystack = ' '.join([region['region_3'], region['region_4'], region['region_5']]).lower()
        if region_text.lower() not in haystack:
            return False
    return True


# ---------------------------------------------------------------------------
# Add / remove (run as button callbacks)
# ---------------------------------------------------------------------------
def add_paper():
    sync()
    st.session_state.data['papers'].append(blank_paper())
    reset_widgets()


def remove_paper(pi):
    sync()
    papers = st.session_state.data['papers']
    papers.pop(pi)
    if not papers:
        papers.append(blank_paper())
    reset_widgets()


def add_claim(pi):
    sync()
    claims = st.session_state.data['papers'][pi]['claims']
    if len(claims) < MAX_CLAIMS:
        claims.append(blank_claim())
    reset_widgets()


def remove_claim(pi, ci):
    sync()
    claims = st.session_state.data['papers'][pi]['claims']
    claims.pop(ci)
    if not claims:
        claims.append(blank_claim())
    reset_widgets()


# ---------------------------------------------------------------------------
# Page sections
# ---------------------------------------------------------------------------
def render_loader():
    with st.expander('📂 Load an existing papers.json', expanded=True):
        uploaded = st.file_uploader('Choose an existing JSON file', type=['json'])
        left, right = st.columns(2)
        with left:
            if uploaded is not None and st.button('Load this file', type='primary', use_container_width=True):
                try:
                    st.session_state.data = normalize(json.loads(uploaded.getvalue().decode('utf-8-sig')))
                    st.session_state.loaded_filename = uploaded.name
                    reset_widgets()
                    st.rerun()
                except ValueError as err:
                    st.error(f'Could not load JSON: {err}')
        with right:
            if st.button('Start a new blank file', use_container_width=True):
                st.session_state.data = {'papers': [blank_paper()]}
                st.session_state.loaded_filename = None
                reset_widgets()
                st.rerun()

        st.markdown('**…or edit what is already in the library**')
        pick, load = st.columns([2, 1])
        pick.selectbox('Library section to load', list(SECTIONS), key='load_section',
                       label_visibility='collapsed')
        load.button('📚 Load from library', use_container_width=True, on_click=load_from_library)


def render_region(pi, region):
    st.markdown('### Region (applies to all claims in this paper)')

    ocean_options = [''] + OCEANS
    ocean_index = ocean_options.index(region['ocean']) if region['ocean'] in OCEANS else 0
    st.selectbox('1. Ocean', ocean_options, index=ocean_index, key=f'region_ocean_{pi}')

    sea_options = [''] + SEAS + [OTHER]
    if region['sea'] in sea_options:
        sea_index = sea_options.index(region['sea'])
    elif region['sea']:
        sea_index = len(sea_options) - 1  # custom sea -> "Other"
    else:
        sea_index = 0
    sea_key = f'region_sea_{pi}'
    st.selectbox('2. Sea / Gulf', sea_options, index=sea_index, key=sea_key)
    if st.session_state[sea_key] == OTHER:
        st.text_input(
            'Manual sea / gulf (used when Other is selected)',
            value='' if region['sea'] in SEAS else region['sea'],
            key=f'region_sea_other_{pi}',
            placeholder='e.g. Philippine Sea (if not listed)',
        )

    st.text_input('3. Region / coastal area', value=region['region_3'], key=f'region_region_3_{pi}',
                  placeholder='e.g. Indian Ocean, coastal zone')
    st.text_input('4. Local area / feature', value=region['region_4'], key=f'region_region_4_{pi}',
                  placeholder='e.g. Kochin, Wadge Bank, shelf')
    st.text_input('5. Specific site / additional region', value=region['region_5'], key=f'region_region_5_{pi}',
                  placeholder='e.g. estuary, station, bay, island')


def render_tag_picker(title, options, current, key, other_key, placeholder):
    st.markdown(f'#### {title}')
    known = [x for x in current if x in options]
    custom = [x for x in current if x not in options]
    st.multiselect(f'Select {title.lower()}', options + [OTHER],
                   default=known + ([OTHER] if custom else []),
                   key=key, label_visibility='collapsed')
    st.text_input(f'Manual {title.lower()[:-1]} (used when Other is selected)',
                  value=', '.join(custom), key=other_key, placeholder=placeholder)


def render_claim(pi, ci, claim):
    with st.container(border=True):
        head, trash = st.columns([8, 1])
        head.markdown(f'**Claim {ci + 1} of {MAX_CLAIMS}**')
        trash.button('🗑️', key=f'rc{pi}_{ci}', on_click=remove_claim, args=(pi, ci))
        st.text_area('Claim', value=claim['claim'], key=f'claim_{pi}_{ci}', height=110,
                     placeholder='Short paraphrase in your own words — not a copied sentence.')
        st.caption('Region is shared from the paper-level field above. Process and parameter tags are claim-specific.')
        render_tag_picker('Process tags', PROCESS_TAGS, claim['process_tags'],
                          f'process_{pi}_{ci}', f'process_other_{pi}_{ci}', 'e.g. my_custom_process_key')
        render_tag_picker('Parameter tags', PARAMETER_TAGS, claim['parameter_tags'],
                          f'param_{pi}_{ci}', f'param_other_{pi}_{ci}', 'e.g. chlorophyll_a')


def render_paper(pi, paper):
    with st.container(border=True):
        head, trash = st.columns([8, 1])
        head.subheader(f'Paper {pi + 1}')
        trash.button('🗑️', key=f'rp{pi}', on_click=remove_paper, args=(pi,))
        st.text_area('Citation', value=paper['citation'], key=f'citation_{pi}', height=90,
                     placeholder='Qasim, S.Z., 1982. Oceanography of the northern Arabian Sea. '
                                 'Deep Sea Research Part A. Oceanographic Research Papers, 29(9), pp.1041-1068.')
        render_region(pi, paper['region'])

        st.markdown(f'### Claims (maximum {MAX_CLAIMS} per paper)')
        for ci, claim in enumerate(paper['claims']):
            render_claim(pi, ci, claim)

        count = len(paper['claims'])
        if count < MAX_CLAIMS:
            st.button(f'➕ Add another claim ({count}/{MAX_CLAIMS})', key=f'ac{pi}',
                      on_click=add_claim, args=(pi,))
        else:
            st.success(f'Maximum of {MAX_CLAIMS} claims reached for this paper.')


def render_footer(json_text):
    st.divider()
    col_paper, col_refresh, col_download = st.columns(3)
    with col_paper:
        st.button('➕ Add another paper', type='primary', use_container_width=True, on_click=add_paper)
    with col_refresh:
        st.button('🔄 Refresh (save new tags)', use_container_width=True, on_click=refresh,
                  disabled=not can_edit())
    with col_download:
        st.download_button('⬇️ Download papers.json', data=json_text.encode('utf-8'),
                           file_name='papers.json', mime='application/json', use_container_width=True)

    with st.container(border=True):
        st.markdown('**📚 Library**')
        target, save = st.columns([2, 1])
        target.selectbox('Save these papers to', list(SECTIONS), key='save_section',
                         format_func=lambda name: f'{name}  →  {SECTIONS[name]}')
        save.button('📚 Save to library', type='primary', use_container_width=True, on_click=save_library,
                    disabled=not can_edit())
        st.checkbox('Replace the stored paper instead of merging', key='save_replace',
                    help='Off (default): if the paper is already in the file, only its new claims are added, '
                         'so nobody’s earlier claims are lost. On: the stored paper is overwritten — use it '
                         'after loading a paper from the library to edit or delete its claims.')
        st.caption('Papers are matched by citation. Claims left empty are not saved. '
                   'New tags are kept with the Refresh button.')
    with st.expander('🔎 Preview generated JSON'):
        st.code(json_text, language='json')


def render_picker():
    st.markdown('### 🔎 Claim picker')
    st.caption('Pick tags one by one, choose the library sections, and download the matching claims.')

    sections = st.multiselect('Library sections', list(SECTIONS), default=list(SECTIONS), key='pick_sections')
    rows = collect_rows(sections)
    if not rows:
        st.info(f'No claims found yet in {library_dir()}. Save papers to the library from the Builder tab first.')
        return

    process_options, process_counts = tag_options(PROCESS_TAGS, rows, 'process_tags')
    parameter_options, parameter_counts = tag_options(PARAMETER_TAGS, rows, 'parameter_tags')

    left, right = st.columns(2)
    process = left.multiselect('Process tags', process_options, key='pick_process',
                               format_func=lambda t: f'{t}  ({process_counts.get(t, 0)})')
    parameter = right.multiselect('Parameter tags', parameter_options, key='pick_parameter',
                                  format_func=lambda t: f'{t}  ({parameter_counts.get(t, 0)})')
    mode = st.radio('A claim must carry…', ['All selected tags', 'Any selected tag'],
                    horizontal=True, key='pick_mode')

    st.markdown('**Filters (optional)**')
    sea_options = SEAS + sorted({r['region']['sea'] for r in rows if r['region']['sea'] and r['region']['sea'] not in SEAS})
    f1, f2, f3 = st.columns(3)
    oceans = f1.multiselect('Ocean', OCEANS, key='pick_oceans')
    seas = f2.multiselect('Sea / Gulf', sea_options, key='pick_seas')
    region_text = f3.text_input('Region / area contains', key='pick_region',
                                placeholder='matches region 3, 4 and 5').strip()

    results = [r for r in rows
               if row_matches(r, process, parameter, mode.startswith('All'), oceans, seas, region_text)]
    st.success(f'{len(results)} of {len(rows)} claims match.')

    payload = {
        'filters': {'sections': sections, 'process_tags': process, 'parameter_tags': parameter,
                    'match': 'all' if mode.startswith('All') else 'any',
                    'oceans': oceans, 'seas': seas, 'region_contains': region_text},
        'count': len(results),
        'claims': results,
    }
    st.download_button('⬇️ Download selected claims', data=(json.dumps(payload, ensure_ascii=False, indent=2) + '\n').encode('utf-8'),
                       file_name='selected_claims.json', mime='application/json',
                       type='primary', use_container_width=True, disabled=not results)

    for row in results[:50]:
        with st.container(border=True):
            st.write(row['claim'])
            where = ' › '.join(x for x in [row['region']['ocean'], row['region']['sea'], row['region']['region_3'],
                                           row['region']['region_4'], row['region']['region_5']] if x)
            st.caption(f"**{row['section']}** · {row['citation']}" + (f' · {where}' if where else ''))
            st.caption('Process: ' + (', '.join(row['process_tags']) or '—') +
                       '  |  Parameter: ' + (', '.join(row['parameter_tags']) or '—'))
    if len(results) > 50:
        st.caption(f'Showing the first 50 of {len(results)}; the download contains all of them.')


def render_sidebar():
    with st.sidebar:
        st.markdown('### 📚 Library')
        try:
            cfg = github_config()
        except OSError as err:
            st.error(str(err))
            return

        if cfg:
            st.caption(f"☁️ GitHub: {cfg['repo']} · branch {cfg['branch']} · folder {cfg['folder'] or '(repo root)'}")
            st.button('↻ Reload from GitHub', use_container_width=True, on_click=st.cache_data.clear,
                      help='Library reads are cached for a minute. Use this to see changes made elsewhere.')
        else:
            st.text_input('Library folder', value=LIBRARY_FOLDER, key='lib_dir_input',
                          help='Relative to this app file, or a full path.')
            st.caption(f'💻 Local: {library_dir()}')

        if edit_password():
            st.text_input('Editor password', type='password', key='editor_password_input',
                          help='Needed to save to the library. Browsing and downloading stay open.')
            st.caption('🔓 Saving unlocked' if can_edit() else '🔒 Read-only')

        if st.session_state.get('tags_error'):
            st.warning(f"Could not read {TAGS_FILE}: {st.session_state.tags_error}")

        for section, filename in SECTIONS.items():
            try:
                text = store_read(filename)
                if text is None:
                    st.caption(f'• {section} — {filename} (not created yet)')
                else:
                    st.caption(f'• {section} — {filename} ({len(parse_papers(text))} paper(s))')
            except (OSError, ValueError):
                st.caption(f'• {section} — {filename} (unreadable)')


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
if 'data' not in st.session_state:
    st.session_state.data = {'papers': [blank_paper()]}

# Widgets only change between runs, so one sync at the top captures everything.
sync()

apply_extra_tags()
render_sidebar()

st.title('🪶 White Raven')
st.caption('Literature citation and claim builder — create or edit papers.json, keep a library, pick claims by tag.')

flash = st.session_state.pop('flash', None)
if flash:
    getattr(st, flash[0])(flash[1])

builder_tab, picker_tab = st.tabs(['✍️ Builder', '🔎 Claim picker'])

with builder_tab:
    render_loader()

    papers = st.session_state.data['papers']
    loaded = st.session_state.get('loaded_filename')
    st.info(f'Currently editing **{len(papers)} paper(s)**.' + (f' Loaded from **{loaded}**.' if loaded else ''))

    for pi, paper in enumerate(papers):
        render_paper(pi, paper)

    render_footer(json.dumps(st.session_state.data, ensure_ascii=False, indent=2) + '\n')

with picker_tab:
    render_picker()