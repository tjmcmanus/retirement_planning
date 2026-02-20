import streamlit as st
import graphviz

st.title("Flow of funds")
flow_tab,some_tab = st.tabs(["Investment Type"," "])
with some_tab:
    print(" ")
    
with flow_tab: 

    buckets = graphviz.Digraph()
    buckets.edge("Stable (Traditional)", "Cash (Joint MM)", "Use when stocks are down")
    buckets.edge("Growth (Brokerage)", "Cash (Joint MM)","Use when stocks are up" )
    buckets.edge("Growth (Traditional)", "Stable (Traditional)","Balance annually")
    buckets.edge("Growth (Roth)", "Cash (Joint MM)","Big Purchases")
    buckets.edge("Growth (Traditional)", "Growth (Brokerage)", "Replenish/RMDs")
    buckets.edge("Growth (Traditional)", "Growth (Roth)", "Roth Conversions")
    buckets.edge("Growth (Brokerage)", "Donor Advised Fund","Giving plan")
    buckets.edge("Cash (Joint MM)", "Cash (Joint Checking)","Spend for living")
    st.graphviz_chart(buckets) 