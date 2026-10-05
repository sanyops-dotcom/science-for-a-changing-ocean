import json
import streamlit as st

st.set_page_config(page_title='White Raven', page_icon='🪶', layout='wide')

PROCESS_TAGS = [
    'bio_o2_consumption_n_cycle', 'respiration_linked_acidification',
    'conservative_mixing_gradient', 'upwelling_influenced_water',
    'temperature_do_solubility_link', 'salinity_do_negative_link',
    'phosphate_do_negative_link'
]
PARAMETER_TAGS = ['salinity','temperature','pH','nitrate','nitrite','ammonia','phosphate','silicate','DO','PAEs','PAHs','others']
OCEANS = ['Pacific Ocean','Atlantic Ocean','Indian Ocean','Southern Ocean','Arctic Ocean']
SEAS = ['Amundsen Sea','Andaman Sea','Arafura Sea','Arabian Sea','Baltic Sea','Barents Sea','Bay of Bengal','Beaufort Sea','Bering Sea','Black Sea','Caribbean Sea','Celebes Sea','Chukchi Sea','Coral Sea','East China Sea','East Siberian Sea','Greenland Sea','Gulf of Aden','Gulf of Mexico','Gulf of Oman','Irish Sea','Java Sea','Kara Sea','Labrador Sea','Laccadive Sea','Laptev Sea','Mediterranean Sea','North Sea','Norwegian Sea','Persian Gulf','Philippine Sea','Red Sea','Ross Sea','Sargasso Sea','Scotia Sea','Sea of Japan','Sea of Okhotsk','South China Sea','Tasman Sea','Timor Sea','Weddell Sea','White Sea','Yellow Sea']
OTHER = 'Other'

def blank_region():
    return {'ocean':'','sea':'','region_3':'','region_4':'','region_5':''}

def blank_claim():
    return {'claim':'','process_tags':[],'parameter_tags':[]}

def blank_paper():
    return {'citation':'','region':blank_region(),'claims':[blank_claim()]}

def s(x): return '' if x is None else str(x).strip()

def normalize_region(r):
    if not isinstance(r, dict): r = {}
    return {'ocean':s(r.get('ocean')),'sea':s(r.get('sea')),'region_3':s(r.get('region_3',r.get('subregion_3'))),'region_4':s(r.get('region_4',r.get('subregion_4'))),'region_5':s(r.get('region_5',r.get('subregion_5')))}

def normalize_claim(c):
    if not isinstance(c, dict): c={}
    return {'claim':s(c.get('claim')),'process_tags':[s(x) for x in c.get('process_tags',[]) if s(x)],'parameter_tags':[s(x) for x in c.get('parameter_tags',[]) if s(x)]}

def normalize_paper(p):
    if not isinstance(p,dict): p={}
    if 'citation' in p: citation=s(p.get('citation'))
    else:
        authors=s(p.get('authors')); year=p.get('year'); title=s(p.get('title')); key=s(p.get('zotero_key'))
        citation=' '.join(x for x in [authors, f'{year}.' if year not in ('',None) else '', title] if x)
        if key: citation=f'{citation} [{key}]'.strip()

    # Region is paper-level: all claims in a paper share the same region.
    if isinstance(p.get('region'), dict):
        region=normalize_region(p['region'])
    elif isinstance(p.get('region_tags'), list):
        old=', '.join(str(x).strip() for x in p.get('region_tags',[]) if str(x).strip())
        region=blank_region(); region['region_3']=old
    else:
        # Migrate older claim-level region data by taking the first available
        # claim region. The normalized output stores it only once at paper level.
        region=blank_region()
        old_claims=p.get('claims',[])
        if isinstance(old_claims,list):
            for old_claim in old_claims:
                if isinstance(old_claim,dict):
                    if isinstance(old_claim.get('region'),dict):
                        region=normalize_region(old_claim['region']); break
                    old=old_claim.get('region_tags',[])
                    if isinstance(old,list) and old:
                        region['region_3']=', '.join(str(x).strip() for x in old if str(x).strip())
                        break

    claims=p.get('claims',[])
    if not isinstance(claims,list): claims=[]
    return {'citation':citation,'region':region,'claims':[normalize_claim(c) for c in claims] or [blank_claim()]}

def normalize(data):
    if not isinstance(data,dict) or not isinstance(data.get('papers'),list): raise ValueError("JSON must contain a top-level 'papers' array.")
    return {'papers':[normalize_paper(p) for p in data['papers']]}

def sync():
    for pi,p in enumerate(st.session_state.data['papers']):
        p['citation']=st.session_state.get(f'citation_{pi}',p['citation'])

        # Region is shared by every claim in this paper.
        r=p['region']
        r['ocean']=st.session_state.get(f'region_ocean_{pi}',r['ocean'])
        sea_selected=st.session_state.get(f'region_sea_{pi}',r['sea'])
        sea_manual=st.session_state.get(f'region_sea_other_{pi}','')
        r['sea']=sea_manual.strip() if sea_selected==OTHER and sea_manual.strip() else sea_selected
        r['region_3']=st.session_state.get(f'region_region_3_{pi}',r['region_3'])
        r['region_4']=st.session_state.get(f'region_region_4_{pi}',r['region_4'])
        r['region_5']=st.session_state.get(f'region_region_5_{pi}',r['region_5'])

        for ci,c in enumerate(p['claims']):
            c['claim']=st.session_state.get(f'claim_{pi}_{ci}',c['claim'])
            selected=st.session_state.get(f'process_{pi}_{ci}',c['process_tags']); manual=st.session_state.get(f'process_other_{pi}_{ci}','')
            vals=[x for x in selected if x!=OTHER]
            if OTHER in selected: vals += [x.strip() for x in manual.split(',') if x.strip()]
            c['process_tags']=list(dict.fromkeys(vals))
            selected=st.session_state.get(f'param_{pi}_{ci}',c['parameter_tags']); manual=st.session_state.get(f'param_other_{pi}_{ci}','')
            vals=[x for x in selected if x!=OTHER]
            if OTHER in selected: vals += [x.strip() for x in manual.split(',') if x.strip()]
            c['parameter_tags']=list(dict.fromkeys(vals))

def add_paper(): sync(); st.session_state.data['papers'].append(blank_paper()); st.rerun()
def remove_paper(i):
    sync(); st.session_state.data['papers'].pop(i)
    if not st.session_state.data['papers']: st.session_state.data['papers'].append(blank_paper())
    st.rerun()
def add_claim(i):
    sync()
    if len(st.session_state.data['papers'][i]['claims'])<10: st.session_state.data['papers'][i]['claims'].append(blank_claim())
    st.rerun()
def remove_claim(i,j):
    sync(); st.session_state.data['papers'][i]['claims'].pop(j)
    if not st.session_state.data['papers'][i]['claims']: st.session_state.data['papers'][i]['claims'].append(blank_claim())
    st.rerun()

if 'data' not in st.session_state: st.session_state.data={'papers':[blank_paper()]}

st.title('🪶 White Raven')
st.caption('Literature citation and claim builder — create or edit papers.json.')
with st.expander('📂 Load an existing papers.json', expanded=True):
    up=st.file_uploader('Choose an existing JSON file',type=['json'])
    a,b=st.columns(2)
    with a:
        if up is not None and st.button('Load this file',type='primary',use_container_width=True):
            try:
                st.session_state.data=normalize(json.loads(up.getvalue().decode('utf-8-sig'))); st.session_state.loaded_filename=up.name; st.rerun()
            except Exception as e: st.error(f'Could not load JSON: {e}')
    with b:
        if st.button('Start a new blank file',use_container_width=True): st.session_state.data={'papers':[blank_paper()]}; st.session_state.loaded_filename=None; st.rerun()

st.info(f"Currently editing **{len(st.session_state.data['papers'])} paper(s)**." + (f" Loaded from **{st.session_state.loaded_filename}**." if st.session_state.get('loaded_filename') else ''))

for pi,p in enumerate(st.session_state.data['papers']):
    with st.container(border=True):
        h,r=st.columns([8,1]); h.subheader(f'Paper {pi+1}')
        if r.button('🗑️',key=f'rp{pi}'): remove_paper(pi)
        st.text_area('Citation',value=p['citation'],key=f'citation_{pi}',height=90,placeholder='Qasim, S.Z., 1982. Oceanography of the northern Arabian Sea. Deep Sea Research Part A. Oceanographic Research Papers, 29(9), pp.1041-1068.')

        # Region is entered once per paper and is inherited by all claims.
        st.markdown('### Region (applies to all claims in this paper)')
        idx=(['']+OCEANS).index(p['region']['ocean']) if p['region']['ocean'] in OCEANS else 0
        st.selectbox('1. Ocean', ['']+OCEANS,index=idx,key=f'region_ocean_{pi}')
        sea_options=['']+SEAS+[OTHER]
        oldsea=p['region']['sea']; idx=sea_options.index(oldsea) if oldsea in sea_options else (len(sea_options)-1 if oldsea else 0)
        st.selectbox('2. Sea / Gulf',sea_options,index=idx,key=f'region_sea_{pi}')
        if st.session_state.get(f'region_sea_{pi}', oldsea) == OTHER:
            st.text_input('Manual sea / gulf (used when Other is selected)',value='' if oldsea in SEAS else oldsea,key=f'region_sea_other_{pi}',placeholder='e.g. Philippine Sea (if not listed)')
        elif oldsea and oldsea not in SEAS:
            st.text_input('Existing custom sea / gulf',value=oldsea,key=f'customsea_{pi}')
        st.text_input('3. Region / coastal area',value=p['region']['region_3'],key=f'region_region_3_{pi}',placeholder='e.g. Indian Ocean, coastal zone')
        st.text_input('4. Local area / feature',value=p['region']['region_4'],key=f'region_region_4_{pi}',placeholder='e.g. Kochin, Wadge Bank, shelf')
        st.text_input('5. Specific site / additional region',value=p['region']['region_5'],key=f'region_region_5_{pi}',placeholder='e.g. estuary, station, bay, island')

        st.markdown('### Claims (maximum 10 per paper)')
        for ci,c in enumerate(p['claims']):
            with st.container(border=True):
                h,r=st.columns([8,1]); h.markdown(f'**Claim {ci+1} of 10**')
                if r.button('🗑️',key=f'rc{pi}_{ci}'): remove_claim(pi,ci)
                st.text_area('Claim',value=c['claim'],key=f'claim_{pi}_{ci}',height=110,placeholder='Short paraphrase in your own words — not a copied sentence.')
                st.caption('Region is shared from the paper-level field above. Process and parameter tags are claim-specific.')
                st.markdown('#### Process tags')
                cur=[x for x in c['process_tags'] if x in PROCESS_TAGS]; custom=[x for x in c['process_tags'] if x not in PROCESS_TAGS]
                default=cur+([OTHER] if custom else [])
                st.multiselect('Select process tags',PROCESS_TAGS+[OTHER],default=default,key=f'process_{pi}_{ci}',label_visibility='collapsed')
                st.text_input('Manual process tag (used when Other is selected)',value=', '.join(custom),key=f'process_other_{pi}_{ci}',placeholder='e.g. my_custom_process_key')
                st.markdown('#### Parameter tags')
                cur=[x for x in c['parameter_tags'] if x in PARAMETER_TAGS]; custom=[x for x in c['parameter_tags'] if x not in PARAMETER_TAGS]
                default=cur+([OTHER] if custom else [])
                st.multiselect('Select parameter tags',PARAMETER_TAGS+[OTHER],default=default,key=f'param_{pi}_{ci}',label_visibility='collapsed')
                st.text_input('Manual parameter tag (used when Other is selected)',value=', '.join(custom),key=f'param_other_{pi}_{ci}',placeholder='e.g. chlorophyll_a')
        if len(p['claims'])<10: st.button(f'➕ Add another claim ({len(p["claims"])}/10)',key=f'ac{pi}',on_click=add_claim,args=(pi,))
        else: st.success('Maximum of 10 claims reached for this paper.')

st.divider()
a,b,c=st.columns(3)
with a: st.button('➕ Add another paper',type='primary',use_container_width=True,on_click=add_paper)
with b:
    if st.button('💾 Update preview',use_container_width=True): sync(); st.success('Preview updated.')
with c:
    sync(); out=json.dumps(st.session_state.data,ensure_ascii=False,indent=2)+'\n'
    st.download_button('⬇️ Download papers.json',data=out.encode('utf-8'),file_name='papers.json',mime='application/json',use_container_width=True)
with st.expander('🔎 Preview generated JSON'):
    sync(); st.code(json.dumps(st.session_state.data,ensure_ascii=False,indent=2),language='json')
