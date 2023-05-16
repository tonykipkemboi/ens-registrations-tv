from subgrounds import Subgrounds
from subgrounds.subgraph import SyntheticField
from subgrounds.pagination import ShallowStrategy
from streamlit_autorefresh import st_autorefresh
from datetime import datetime as dt
from PIL import Image

import pandas as pd
import streamlit as st


def get_data(url: str) -> pd.DataFrame:
    """Fetches ENS registration data from a given subgraph URL.

    Args:
        url (str): The ENS subgraph URL.

    Returns:
        pd.DataFrame: The ENS registrations data as a pandas DataFrame.
    """
    # Initialize subgrounds
    sg = Subgrounds()
    ens = sg.load_subgraph(url)

    # Synthetic field for registration date
    ens.Registration.registrationdate = SyntheticField(
        lambda registrationDate: str(dt.fromtimestamp(registrationDate)),
        SyntheticField.STRING,
        ens.Registration.registrationDate
    )

    # Synthetic field for expiry date
    ens.Registration.expirydate = SyntheticField(
        lambda expiryDate: str(dt.fromtimestamp(expiryDate)),
        SyntheticField.STRING,
        ens.Registration.expiryDate
    )

    # Field paths to load + first 1000 registrations in descending order
    registrations = ens.Query.registrations(
        first=20,
        orderBy=ens.Registration.registrationDate,
        orderDirection="desc"
    )

    # Payload
    field_paths = [
        registrations.registrationdate,
        registrations.domain.name,
        registrations.labelName,
        registrations.domain.owner.id,
        registrations.cost,
        registrations.expirydate
    ]

    df = sg.query_df(field_paths, pagination_strategy=ShallowStrategy)
    
    return df


def apply_edits(df: pd.DataFrame) -> pd.DataFrame:
    """Performs various transformations on the input DataFrame.

    Args:
        df (pd.DataFrame): Input DataFrame with raw ENS registrations data.

    Returns:
        pd.DataFrame: Transformed DataFrame with added and reformatted columns.
    """
    # Add cost in Ether columns
    df['cost_in_ether'] = df['registrations_cost'] / (10**18)

    # Rename columns
    cols = {'registrations_registrationdate': 'Registration Date', 'registrations_domain_name': 'Name',
            'registrations_labelName': 'Label Name', 'registrations_domain_owner_id': 'Owner',
            'registrations_cost': 'reg_cost', 'registrations_expirydate': 'Expiry Date', 'cost_in_ether': 'Cost'}

    df.rename(columns=cols, inplace=True)

    # Select target columns
    df = df[['Name', 'Owner', 'Registration Date',
             'Expiry Date', 'Cost']].copy()

    # Convert date object to datetime
    df[["Registration Date", "Expiry Date"]] = df[[
        "Registration Date", "Expiry Date"]].apply(pd.to_datetime)
    df["Registration Date"] = df["Registration Date"].apply(
        lambda x: x.strftime("%m-%d-%Y @%H:%M:%S"))
    df["Expiry Date"] = df["Expiry Date"].apply(
        lambda x: x.strftime("%m-%d-%Y @%H:%M:%S"))

    return df

def convert_df(df: pd.DataFrame) -> bytes:
    """Converts the input DataFrame into a CSV format and encodes it.

    Args:
        df (pd.DataFrame): The input DataFrame.

    Returns:
        bytes: The encoded CSV data.
    """
    # IMPORTANT: Cache the conversion to prevent computation on every rerun
    return df.to_csv().encode('utf-8')


if __name__ == '__main__':

    # App config setup
    st.set_page_config( 
        page_icon='assets/ethereum-name-service-ens-logo.png',
        page_title='Real-Time ENS Registrations',
        layout='wide'
    )

    # App title
    st.markdown("<h1 style='text-align: center; color: red;'>📺 ENS Registrations TV 📺</h1>",
                unsafe_allow_html=True)

    # update every 5 mins
    st_autorefresh(interval=0.5 * 60 * 1000, key="dataframerefresh")

    # URL for ENS subgraph
    SUBGRAPH_URL = 'https://api.thegraph.com/subgraphs/name/ensdomains/ens'

    # Call get_data function
    data = get_data(url=SUBGRAPH_URL)

    # Transform data
    final = apply_edits(data)

    with st.container():
        col1, col2, col3 = st.columns(3)
        tab1, tab2, tab3 = st.tabs(
            ["✍🏾 Registrations", "📈 Chart", "📥 Download Data"])

        with col1:
            with tab1:
                expander = st.expander("🚨 DISCLAIMER 🚨")
                expander.write("""
                *Some of the names being registered contain words or language that is considered `profane`, `vulgar`, or `offensive` by some* 
                """)

                col1, col2, col3 = st.columns(3)

                col1.metric("Domain 🌐", value=final['Name'][0])

                diff = final['Cost'][0].round(
                    decimals=3) - final['Cost'][1].round(decimals=3)

                col2.metric(label="Cost Ξ", value=final['Cost'][0].round(
                    decimals=4), delta=diff)

                col3.metric("Owner 🧑‍🚀", value=final['Owner'][0][:8]+'...'+final['Owner'][0][-4:])
                st.write('---')
                st.subheader('Most recent registrations')

                st.dataframe(final.head(10), use_container_width=True)

        with col2:
            with tab2:
                st.info('This section is still a work in progress...')
                _, sub, _ = st.columns(3)
                with sub:
                    st.subheader('Price vs. Name')
                graph = final[['Name', 'Cost']].copy()
                st.bar_chart(graph, y='Cost', x='Name')

        with col3:
            with tab3:
                st.subheader('Download ENS Dataset')
                st.write(
                    ' ⚠️ *The data is limited to the 20 recent name registrations*')
                csv = convert_df(final)

                st.download_button(
                    label="Download data as CSV",
                    data=csv,
                    file_name='ens_dataset.csv',
                    mime='text/csv',
                )
        st.caption('Refresh rate: `30 seconds`')
