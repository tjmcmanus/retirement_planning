import streamlit as st
import graphviz

st.title("Flow of funds")
flow_tab,accounts_tab = st.tabs(["Investment Type","Existing Accounts"])
with accounts_tab:

    # Create a graphlib graph object
    graph = graphviz.Digraph()

    graph.edge("IBM Roth 401k (Tax free)", "Schwab Tom Roth IRA (Tax free)")
    
    graph.edge("IBM 401k (Tax deferred)", "IBM Roth 401k (Tax free)")
    graph.edge("IBM 401k (Tax deferred)", "Schwab Joint Brokerage (Taxable)")
    graph.edge("IBM 401k (Tax deferred)", "Schwab Tom IRA (Tax deferred)")
    
    graph.edge("Computershare (Taxable)", "Schwab Joint Brokerage (Taxable)")
    graph.edge("Computershare (Taxable)", "PNC Joint Money Market (Taxable)")
    
    #graph.edge("Highmark 401k (Tax deferred)", "Schwab Joint Brokerage (Taxable)")
    graph.edge("Highmark 401k (Tax deferred)", "Schwab Sarah IRA (Tax deferred)")
    graph.edge("CGEY 401k (Tax deferred)", "Schwab Sarah IRA (Tax deferred)")
    graph.edge("CVS 401k (Tax deferred)", "Schwab Sarah IRA (Tax deferred)")
    graph.edge("HM Pension (Tax deferred)", "Schwab Sarah IRA (Tax deferred)")
   

    
    graph.edge("IBM Pension New (Tax deferred)", "Schwab Tom IRA (Tax deferred)")
   
    graph.edge("IBM Pension Old (Tax deferred)", "Schwab Tom IRA (Tax deferred)")
    
    graph.edge("Schwab Sarah IRA (Tax deferred)", "Schwab Sarah Roth IRA (Tax free)")
    graph.edge("Schwab Sarah IRA (Tax deferred)", "Schwab Joint Brokerage (Taxable)")
    
    graph.edge("Schwab Tom IRA (Tax deferred)", "Schwab Tom Roth IRA (Tax free)")
    
    graph.edge("Schwab Joint Brokerage (Taxable)", "PNC Joint Money Market (Taxable)")
    
    graph.edge("Schwab Tom Roth IRA (Tax free)", "PNC Joint Money Market (Taxable)")
    
    graph.edge("Schwab Sarah Roth IRA (Tax free)", "PNC Joint Money Market (Taxable)")
    #graph.edge("PNC Joint Checking", "PNC Tom Checking")
    #graph.edge("PNC Joint Checking", "PNC Sarah Checking")
    #graph.edge("PNC Joint Money Market", "Schwab Joint Brokerage")
    #graph.edge("PNC Sarah Money Market", "Schwab Joint Brokerage")
    graph.edge("PNC Sarah Money Market (Taxable)", "PNC Sarah Checking (Taxable)")
    
    graph.edge("PNC Sarah Checking (Taxable)","PNC Sarah Money Market (Taxable)" )
    #graph.edge("PNC Tom Money Market", "Schwab Joint Brokerage")
    graph.edge("PNC Tom Money Market (Taxable)", "PNC Tom Checking (Taxable)")
    
    graph.edge("PNC Tom Checking (Taxable)","PNC Tom Money Market (Taxable)")

    graph.edge("PNC Joint Money Market (Taxable)", "PNC Sarah Checking (Taxable)")
    graph.edge("PNC Joint Money Market (Taxable)", "PNC Tom Checking (Taxable)")
    graph.edge("PNC Joint Money Market (Taxable)", "PNC Joint Checking (Taxable)")

    st.graphviz_chart(graph)
    
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