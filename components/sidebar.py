import streamlit as st


from streamlit_card import card
def clear_all_cache():
    st.cache_data.clear()
    st.cache_resource.clear()



def set_ss_age(age: str):
    st.session_state["SSI_AGE"] = age
    #st.session_state["project_id"] = project_id
    
def set_conversion_value_at_ssi(amount: str):  
    st.session_state["CONV_AMOUNT_AT_SSI_AGE"] = amount 
    
def set_conversion_rate_at_ssi(rate: str):  
    st.session_state["CONV_TAX_RATE"] = rate 

def set_annual_expense(expense:str):
    st.session_state["EXPENSE"] = expense
    
def set_expense_multiplier(multiplier:str):
    st.session_state["EXPENSE_MULITPLIER"] = multiplier
       
def set_rate_of_return(intrate:str):
    st.session_state["RATE"] = intrate
    
def set_daf_giving_rate(daf_rate:str):
    st.session_state["DAF_RATE"] = daf_rate    

def sidebar():
    with st.sidebar:
       # st.markdown(
        #    "## Provide your retirement configurations\n"
       # )
        st.sidebar.button("Refresh All Data", on_click=clear_all_cache)
        ssi_age_input = st.text_input(
            "Social Security Age",
            type="default",
            placeholder="Add your age you expect to collect Social Security",
            value=st.session_state.get("SSI_AGE", "70"),
        )

       # st.markdown(
       #     "## Provide Roth conversion value at SS age "
       # )
        set_conversion_ssi_input = st.text_input(
            "Roth Conversion at SSI age",
            type="default",
            placeholder="Add the amount to conver to Roth here at SSI",
            help="Consult docs to locate your project id",  
            value=st.session_state.get("CONV_AMOUNT_AT_SSI_AGE", "225000"),
        )

        set_max_tax_rate_roth_input = st.text_input(
            "Max Tax rate for a Roth conversion",
            type="default",
            placeholder="Add the max Tax rate for a Roth conversion",
            value=st.session_state.get("CONV_TAX_RATE", "24"),
        )   

        set_annual_expense_input = st.text_input(
            "Expected Annual Expenses",
            type="default",
            placeholder="Add the expected annual expenses",
            value=st.session_state.get("EXPENSE", "150000"),
        )  
        set_expense_multiplier_input = st.text_input(
            "Desired mulitple of expenses available",
            type="default",
            placeholder="Add the desired multiplier of expenses",
            value=st.session_state.get("EXPENSE_MULITPLIER", "4"),
        )      
        set_rate_of_return_input = st.text_input(
            "Expected Annual Rate of Return",
            type="default",
            placeholder="Add the expected annual rate of return investments",
            value=st.session_state.get("RATE", "6"),
        )  
        set_daf_rate_of_return_input = st.text_input(
            "Donor Advised Fund Disburment rate",
            type="default",
            placeholder="Add Percenage number to give from Donor advised fund",
            value=st.session_state.get("DAF_RATE", "25"),
        )

        if ssi_age_input:
            set_ss_age(ssi_age_input)
        
        if set_conversion_ssi_input:
            set_conversion_value_at_ssi(set_conversion_ssi_input)   
        
        if set_max_tax_rate_roth_input:
            set_conversion_rate_at_ssi(set_max_tax_rate_roth_input) 
        
        if set_annual_expense_input:
            set_annual_expense(set_annual_expense_input) 
            
        if set_expense_multiplier_input:  
            set_expense_multiplier(set_expense_multiplier_input)
              
        if set_rate_of_return_input:
           set_rate_of_return(set_rate_of_return_input)   
           
        if set_daf_rate_of_return_input:   
           set_daf_giving_rate(set_daf_rate_of_return_input)