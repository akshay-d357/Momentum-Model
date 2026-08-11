import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

df = pd.DataFrame({'A': [1,2,3], 'B': [4,5,6]})
df.insert(0, "Index", "")

gb = GridOptionsBuilder.from_dataframe(df)
gb.configure_default_column(filterable=True)
gb.configure_column("Index", valueGetter=JsCode("function(params) { return params.node.rowIndex + 1; }"))
gridOptions = gb.build()

AgGrid(df, gridOptions=gridOptions, allow_unsafe_jscode=True)
