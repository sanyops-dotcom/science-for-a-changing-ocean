import streamlit as st

# Central entry point for all Data Processor tools.
# All individual tools remain as separate Streamlit pages.

st.set_page_config(
    page_title="Data Processor",
    page_icon="🌊",
    layout="wide",
)

pages = [
    st.Page("Line_plot.py", title="Line Plot", icon="📈"),
    st.Page("MD-to-Word_converter.py", title="MD to Word Converter", icon="📝"),
    st.Page("Sampling_Location.py", title="Sampling Location", icon="📍"),
    st.Page("Station_Profiler.py", title="Station Profiler", icon="📊"),
    st.Page("Transect_profiler.py", title="Transect Profiler", icon="🌊"),
    st.Page("ctd_depth_extractor_app.py", title="CTD Depth Extractor", icon="🔬"),
    st.Page("code-02-multifilemerger.py", title="Multi-file Merger", icon="📂"),
    st.Page("oms_global_statistics.py", title="OMS Global Statistics", icon="🌐"),
    st.Page("splitter_app.py", title="Splitter", icon="✂️"),
    st.Page("station_name_sorter_app.py", title="Station Name Sorter", icon="🔤"),
    st.Page("surface_plot.py", title="Surface Plot", icon="🗺️"),
]

navigation = st.navigation({"Data Processor": pages})
navigation.run()