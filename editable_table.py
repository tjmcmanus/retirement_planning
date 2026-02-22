import streamlit as st
import pandas as pd
import numpy as np

st.title('Editable Data Entry Table')

# 1. Initialize a DataFrame (can also load from a CSV, Excel, or database)
# It's recommended to start with an empty or pre-structured DataFrame
# to define column data types and names.
initial_data = pd.DataFrame(
    [
        {"Name": "Alice", "Age": 30, "City": "New York"},
        {"Name": "Bob", "Age": 45, "City": "Paris"},
        {"Name": "Charlie", "Age": 28, "City": "London"},
    ]
).reset_index(drop=True)

# You can also start with an empty structure for new inputs:
# initial_data = pd.DataFrame(columns=['Name', 'Age', 'City'])
# initial_data = initial_data.fillna(0) # Fill with default values if needed

st.markdown("### Input Data Below")

# 2. Use st.data_editor to display an editable table
# The 'num_rows="dynamic"' option allows users to add or delete rows via the UI
edited_df = st.data_editor(initial_data, num_rows="dynamic")

# 3. The 'edited_df' variable automatically contains the current state of the table
# after user interactions (editing cells, adding/deleting rows).

st.markdown("### Extracted DataFrame (After Editing)")

# 4. Display the extracted DataFrame for verification
st.write(edited_df)

# You can also use the data in other parts of your application, for example:
if st.button('Process Data'):
    st.success(f'Data processed. Total entries: {len(edited_df)}.')
    # Further processing of the 'edited_df' can be done here.
