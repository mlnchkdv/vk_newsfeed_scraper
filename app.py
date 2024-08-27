import streamlit as st
import requests
import json
import pandas as pd
import datetime
import time
import plotly.graph_objs as go
from ru_sentiment import SentimentAnalyzer

# Инициализация модели для анализа тональностей
analyzer = SentimentAnalyzer()

def get_unixtime_from_datetime(date_time):
    return str(int(time.mktime(date_time.timetuple())))

def get_vk_newsfeed(query, start_time, end_time, access_token):
    df = pd.DataFrame()
    count = "200"

    start_time = datetime.datetime.strptime(start_time, "%Y-%m-%d").date()
    end_time = datetime.datetime.strptime(end_time, "%Y-%m-%d").date()

    delta = datetime.timedelta(days=30)
    start_delta_time = start_time
    end_delta_time = start_time + delta

    while end_delta_time <= end_time:
        url = (
            f"https://api.vk.com/method/newsfeed.search?q={query}"
            f"&count={count}&access_token={access_token}"
            f"&start_time={get_unixtime_from_datetime(start_delta_time)}"
            f"&end_time={get_unixtime_from_datetime(end_delta_time)}&v=5.131"
        )

        res = requests.get(url)
        text = res.text
        
        try:
            json_text = json.loads(text)
            if 'response' in json_text:
                df = pd.concat([df, pd.json_normalize(json_text['response'], record_path=['items'])])
            else:
                st.error(f"Error in response: {json_text.get('error', 'Unknown error')}")
                break
        except json.JSONDecodeError as e:
            st.error(f"JSON Decode Error: {e}")
            break

        start_delta_time += delta
        end_delta_time += delta
        time.sleep(3)

    return df

def analyze_sentiment_with_ru_sentiment(texts):
    sentiments = analyzer.predict(texts)
    return sentiments

def plot_graphs(vk_df):
    vk_df['date'] = pd.to_datetime(vk_df['date'], unit='s')

    columns_for_deduplication = [col for col in vk_df.columns if col != 'attachments']
    vk_df.drop_duplicates(subset=columns_for_deduplication, inplace=True)
    vk_df.sort_values(by='date', inplace=True)

    for col in ['likes.count', 'reposts.count', 'views.count', 'comments.count']:
        if isinstance(vk_df[col].iloc[0], list):
            vk_df[col] = vk_df[col].apply(lambda x: x[0] if x else 0)

    vk_df['er_view'] = (vk_df['likes.count'] + vk_df['comments.count'] + vk_df['reposts.count']) / vk_df['views.count'] * 100
    df_grouped = vk_df.groupby(vk_df['date'].dt.date)['id'].count().reset_index(name='count')
    metrics = vk_df.groupby(vk_df['date'].dt.date)['er_view'].sum().reset_index()

    st.dataframe(vk_df)
    st.markdown('ER View is calculated as: $ER\\ View = \\frac{Likes + Comments + Reposts}{Views} \\times 100$')

    # Первый график с четырьмя показателями
    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=vk_df['date'], y=vk_df['likes.count'], mode='lines', name='Likes'))
    fig1.add_trace(go.Scatter(x=vk_df['date'], y=vk_df['reposts.count'], mode='lines', name='Reposts'))
    fig1.add_trace(go.Scatter(x=vk_df['date'], y=vk_df['views.count'], mode='lines', name='Views'))
    fig1.add_trace(go.Scatter(x=vk_df['date'], y=vk_df['comments.count'], mode='lines', name='Comments'))
    fig1.update_layout(
        title='Engagement Metrics',
        xaxis_title='Date',
        yaxis_title='Count',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig1)

    # Объединенный график с контрастными цветами
    fig_combined = go.Figure()
    fig_combined.add_trace(go.Scatter(x=df_grouped['date'], y=df_grouped['count'], mode='lines', name='Number of Publications', line=dict(color='blue')))
    fig_combined.add_trace(go.Scatter(x=metrics['date'], y=metrics['er_view'], mode='lines', name='Engagement Rate (ER View)', yaxis='y2', line=dict(color='orange')))
    fig_combined.update_layout(
        title='Dynamics of Publications and Engagement Rate',
        xaxis_title='Date',
        yaxis=dict(
            title='Number of Publications',
            titlefont=dict(color='blue'),
            tickfont=dict(color='blue')
        ),
        yaxis2=dict(
            title='Engagement Rate',
            titlefont=dict(color='orange'),
            tickfont=dict(color='orange'),
            overlaying='y',
            side='right'
        ),
        legend_title='Metrics',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_combined)

    return vk_df

def filter_by_sentiment(vk_df, sentiment_filter):
    return vk_df[vk_df['sentiment'] == sentiment_filter]

def perform_sentiment_analysis(vk_df):
    st.write("Performing sentiment analysis...")
    vk_df['sentiment'] = analyze_sentiment_with_ru_sentiment(vk_df['text'].tolist())
    st.write("Sentiment analysis completed.")

    # Фильтрация по тональности
    sentiment_filter = st.selectbox("Filter by sentiment", options=['positive', 'negative', 'neutral'])
    filtered_df = filter_by_sentiment(vk_df, sentiment_filter)

    st.write(f"Filtered data with sentiment: {sentiment_filter}")
    st.dataframe(filtered_df[['date', 'text', 'sentiment']])

    # Построение графиков после фильтрации
    plot_graphs(filtered_df)

# Streamlit UI
st.title("VK Newsfeed Scraper")

st.write("""
Код `%23` в начале запроса, означает `#`, соответственно, если необходимо поставить между словами пробел, то нужно использовать код `%20`, например `советское%20прошлое` (заменяется кодом [ACSII](https://wm-school.ru/html/html_url_acsii.html)).
""")

query = st.text_input("Enter VK query", "%23советскиеКосмонавты")
access_token = "vk1.a.KuDiZApblGDyCzLiWywXxaCWLO_P3ZHvYleRaZUeNlmmhuNhAx6aypapbjb0Bqo6uvNwjP07MF46JLCQQbqW6YWZqFNLLUZllmGbixQazsKQEoL-zwcLzWrcI181RJEiXAjAqtvTK7aBnelB4KvnZ1T_rvOlicCTSDkyhusiFFpz7R2FaVhf1s-YDJnNfZMeACMdP1Cql8GXD7zzS-_fIA"

col_1, col_2 = st.columns(2)
with col_1:
    start_date = st.date_input("Start date", datetime.date(2023, 10, 1))
with col_2:
    end_date = st.date_input("End date", datetime.date(2023, 12, 31))

if st.button("Fetch Data"):
    if access_token:
        try:
            vk_df = get_vk_newsfeed(query, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), access_token)
            vk_df = vk_df[['id', 'date', 'owner_id', 'text', 'comments.count', 'likes.count', 'reposts.count', 'views.count', 'attachments']]
            vk_df = plot_graphs(vk_df)
            csv_file = vk_df.to_csv().encode('utf-8')
            st.download_button(
                label="Download data as CSV",
                data=csv_file,
                file_name='vk_data.csv',
                mime='text/csv',
            )
            st.success("Data fetched successfully!")
            
            # Кнопка для анализа тональностей появляется после загрузки данных и отображения графиков
            st.markdown("---")
            st.subheader("Sentiment Analysis")
            if st.button("Analyze Sentiment"):
                perform_sentiment_analysis(vk_df)
        except Exception as e:
            st.error(f"An error occurred: {e}")
    else:
        st.error("Please enter a valid VK Access Token.")
