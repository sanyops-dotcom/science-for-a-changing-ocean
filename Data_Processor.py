import streamlit as st

# Central entry point for the Data Processor tools.
# The existing individual Streamlit apps remain separate.

st.set_page_config(
    page_title="Data Processor",
    page_icon="🌊",
    layout="wide",
)

pages = [
    st.Page("Data_Processor/Line_plot.py", title="Line Plot", icon="📈"),
    st.Page("Data_Processor/MD-to-Word_converter.py", title="MD to Word Converter", icon="📝"),
    st.Page("Data_Processor/Sampling_Location.py", title="Sampling Location", icon="📍"),
    st.Page("Data_Processor/Station_Profiler.py", title="Station Profiler", icon="📊"),
    st.Page("Data_Processor/Transect_profiler.py", title="Transect Profiler", icon="🌊"),
    st.Page("Data_Processor/ctd_depth_extractor_app.py", title="CTD Depth Extractor", icon="🔬"),
    st.Page("Data_Processor/code-02-multifilemerger.py", title="Multi-file Merger", icon="📂"),
    st.Page("Data_Processor/oms_global_statistics.py", title="OMS Global Statistics", icon="🌐"),
    st.Page("Data_Processor/splitter_app.py", title="Splitter", icon="✂️"),
    st.Page("Data_Processor/station_name_sorter_app.py", title="Station Name Sorter", icon="🔤"),
    st.Page("Data_Processor/surface_plot.py", title="Surface Plot", icon="🗺️"),
]

navigation = st.navigation({"Data Processor": pages})
navigation.run()
