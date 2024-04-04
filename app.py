import streamlit as st
import requests
import json
import pandas as pd
import datetime
import time
# import plotly.express as px
import plotly.graph_objs as go

def get_unixtime_from_datetime(date_time):
    return str(int(time.mktime(date_time.timetuple())))

def get_vk_newsfeed(query, start_time, end_time, access_token):
    df = pd.DataFrame()
    q = query
    count = "200"

    start_time = datetime.datetime.strptime(start_time, "%Y-%m-%d").date()
    end_time = datetime.datetime.strptime(end_time, "%Y-%m-%d").date()

    delta = datetime.timedelta(days=30)
    start_delta_time = start_time
    end_delta_time = start_time + delta

    while end_delta_time <= end_time:
        url = (
            "https://api.vk.com/method/newsfeed.search?q="
            + q
            + "&count="
            + count
            + "&access_token="
            + access_token
            + "&start_time="
            + get_unixtime_from_datetime(start_delta_time)
            + "&end_time="
            + get_unixtime_from_datetime(end_delta_time)
            + "&v=5.131"
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

        df = pd.concat([df, pd.json_normalize(json_text['response'], record_path =['items'])])

        start_delta_time += delta
        end_delta_time += delta
        time.sleep(3)

    return df

# Streamlit UI
st.title("VK Newsfeed Scraper")

query = st.text_input("Enter VK query", "%23советскиеКосмонавты")
# start_date = st.date_input("Start date", datetime.date(2023, 10, 1))
# end_date = st.date_input("End date", datetime.date(2023, 12, 31))
# access_token = st.text_input("Enter your VK Access Token", "")
access_token = "vk1.a.KuDiZApblGDyCzLiWywXxaCWLO_P3ZHvYleRaZUeNlmmhuNhAx6aypapbjb0Bqo6uvNwjP07MF46JLCQQbqW6YWZqFNLLUZllmGbixQazsKQEoL-zwcLzWrcI181RJEiXAjAqtvTK7aBnelB4KvnZ1T_rvOlicCTSDkyhusiFFpz7R2FaVhf1s-YDJnNfZMeACMdP1Cql8GXD7zzS-_fIA"

# query = st.text_input("Enter VK query", "%23советскиеКосмонавты")

col_1, col_2 = st.columns(2)
with col_1:
    start_date = st.date_input("Start date", datetime.date(2023, 10, 1))
with col_2:
    end_date = st.date_input("End date", datetime.date(2023, 12, 31))


if st.button("Fetch Data"):
    if access_token:
        try:
            vk_df = get_vk_newsfeed(query, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), access_token)           
            vk_df = vk_df[['id', 'date', 'owner_id', 'short_text_rate', 'text', 'comments.count', 'likes.count', 'reposts.count', 'views.count', 'attachments']]
            vk_df['date'] = pd.to_datetime(vk_df['date'], unit='s')

            # Удаление дубликатов, исключая столбец 'attachments'
            columns_for_deduplication = [col for col in vk_df.columns if col != 'attachments']
            vk_df.drop_duplicates(subset=columns_for_deduplication, inplace=True)
            
            # Сортировка по дате
            vk_df.sort_values(by='date', inplace=True)      

            # Преобразование данных, если они в формате списка
            for col in ['likes.count', 'reposts.count', 'views.count', 'comments.count']:
                if isinstance(vk_df[col].iloc[0], list):
                    vk_df[col] = vk_df[col].apply(lambda x: x[0] if x else 0)

            # Расчет метрики вовлеченности ER View
            # vk_df['er_view'] = (vk_df['likes.count'] + vk_df['comments.count'] + vk_df['reposts.count']) / vk_df['views.count'] * 100           
            # Расчет метрики вовлеченности и подготовка данных для графиков
            vk_df['er_view'] = (vk_df['likes.count'] + vk_df['comments.count'] + vk_df['reposts.count']) / vk_df['views.count'] * 100           
            df_grouped = vk_df.groupby(vk_df['date'].dt.date)['id'].count().reset_index(name='count')
            metrics = vk_df.groupby(vk_df['date'].dt.date)['er_view'].sum().reset_index()

            # Отображение полной таблицы данных
            st.dataframe(vk_df)
            
            # Отображение формулы вовлеченности в формате LaTeX
            st.markdown('ER View is calculated as: $ER\\ View = \\frac{Likes + Comments + Reposts}{Views} \\times 100$')
                        
            # Создание объединенного графика
            fig = go.Figure()
            # Добавление графика динамики публикаций
            fig.add_trace(go.Scatter(x=df_grouped['date'], y=df_grouped['count'], mode='lines', name='Number of Publications'))
            # Добавление графика метрики вовлеченности с использованием вторичной оси Y
            fig.add_trace(go.Scatter(x=metrics['date'], y=metrics['er_view'], mode='lines', name='Engagement Rate (ER View)', yaxis='y2'))
            # Определение макета графика
            fig.update_layout(
                title='Dynamics of Publications and Engagement Rate',
                xaxis_title='Date',
                yaxis=dict(
                    title='Number of Publications',
                    titlefont=dict(color='blue'),
                    tickfont=dict(color='blue')
                ),
                yaxis2=dict(
                    title='Engagement Rate',
                    titlefont=dict(color='lightblue'),
                    tickfont=dict(color='lightblue'),
                    overlaying='y',
                    side='right'
                ),
                legend_title='Metrics'
            )

            # Отображение графика
            st.plotly_chart(fig)
                        
            # Сохранение данных в CSV
            csv_file = vk_df.to_csv().encode('utf-8')
            st.download_button(
                label="Download data as CSV",
                data=csv_file,
                file_name='vk_data.csv',
                mime='text/csv',
            )

            st.success("Data fetched successfully!")
        except Exception as e:
            st.error(f"An error occurred: {e}")
    else:
        st.error("Please enter a valid VK Access Token.")
