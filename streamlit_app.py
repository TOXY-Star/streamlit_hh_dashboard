import requests
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(
    page_title="Мой дашборд",
    page_icon="https://yt3.ggpht.com/yti/ANjgQV-qrpyeVOB8Ju7AHRcMgGguTuwEFW6hafBTFZq0rJMeZUs=s108-c-k-c0x00ffffff-no-rj",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.logo('https://yt3.ggpht.com/yti/ANjgQV-qrpyeVOB8Ju7AHRcMgGguTuwEFW6hafBTFZq0rJMeZUs=s108-c-k-c0x00ffffff-no-rj', icon_image='https://yt3.ggpht.com/yti/ANjgQV-qrpyeVOB8Ju7AHRcMgGguTuwEFW6hafBTFZq0rJMeZUs=s108-c-k-c0x00ffffff-no-rj')

# --- Функции ---
def parsing(text, city, period):
    url = "https://api.hh.ru/vacancies"
    dfs_list = []
    for i in range(20):
        params = {
            'text': f'name:{text}',
            'area': city,
            'per_page': 100,
            'page': i,
            'period': period
        }
        response = requests.get(url, params=params)
        if response.status_code != 200:
            break
        vacancies = response.json()
        if vacancies['items'] == []:
            break
        df = pd.json_normalize(vacancies['items'], max_level=1)
        dfs_list.append(df)
    if dfs_list:
        return pd.concat(dfs_list, ignore_index=True)
    return pd.DataFrame()

@st.cache_data
def format_df(df):
    if df.empty:
        return df
    df_exploded = df.explode('work_format')
    work_format_df = pd.json_normalize(df_exploded['work_format']).add_prefix('work_format_')
    df_final = pd.concat([df_exploded.reset_index(drop=True), work_format_df.reset_index(drop=True)], axis=1)
    
    df_result = df_final[[
        'id', 'name', 'salary.from', 'salary.to', 'salary.currency', 'salary.gross',
        'address.lat', 'address.lng', 'area.name', 'experience.name',
        'work_format_name', 'published_at', 'employer.name','alternate_url'
    ]]
    
    salary_from = df_result['salary.from'].fillna(df_result['salary.to'])
    salary_to = df_result['salary.to'].fillna(df_result['salary.from'])
    df_result['salary_avr'] = (salary_from + salary_to) / 2
    
    return df_result

# --- Sidebar ---
with st.sidebar:
    title = st.text_input('Выберите профессию 👷', 'Аналитик')
    city = st.text_input('Город', 1)
    period = st.slider('Период поиска (дней)', 1, 365, 1)

    if st.button('Refresh'):
        df_result = format_df(parsing(title, city, period))
        st.session_state['df_result'] = df_result  # сохраняем данные

    filter_id = st.text_input('Фильтр по ID вакансии', '')

# --- Основной блок ---
df_result = st.session_state.get('df_result', pd.DataFrame())

# Применяем фильтр по ID, если есть
if filter_id.strip() != '' and not df_result.empty:
    # Сохраняем оригинальный df, а фильтруем в копии
    df_result = df_result[df_result['id'] == filter_id.strip()].copy()
    if not df_result.empty:
        with st.sidebar:
            st.subheader("Результаты поиска:")
            
            # Проверяем наличие столбца
            if 'alternate_url' in df_result.columns:
                for i, url in enumerate(df_result['alternate_url'], 1):
                    if pd.notna(url) and str(url).strip() != '':
                        st.markdown(f"{i}. [Ссылка {i}]({url})")
                    else:
                        st.warning(f"Для записи {i} URL не найден")
            else:
                st.error("Столбец 'alternate_url' не найден в данных")
else:
    df_result = df_result.copy()
# --- Проверка на пустой DataFrame ---
if df_result.empty:
    st.markdown('# Привет')
else:
    # --- Метрики ---
    total_count = len(df_result)
    non_null_count = df_result['salary_avr'].count()
    fill_percentage = round((non_null_count / total_count) * 100) if total_count > 0 else 0
    average_salary = round(df_result['salary_avr'].mean()) if non_null_count > 0 else 0
    
    left, middle, right = st.columns(3)
    left.metric("Найдено вакансий", total_count)
    middle.metric("Вакансий с зарплатой", non_null_count, f"{fill_percentage}%")
    right.metric("Средняя зарплата", average_salary if average_salary else "-")

    # --- Карта ---
    map_df = df_result.dropna(subset=['address.lat', 'address.lng'])
    if not map_df.empty:
        map_df2 = map_df.rename(columns={'address.lat':'lat','address.lng':'lon'})
        st.map(map_df2, latitude="lat", longitude="lon")

    # --- Круговые диаграммы ---
    if df_result['experience.name'].notna().any():
        exp_counts = df_result['experience.name'].value_counts().reset_index()
        exp_counts.columns = ['Категория', 'Значение']
        exp_fig = px.pie(exp_counts, names='Категория', values='Значение', title="Требуемый опыт")
    else:
        exp_fig = None

    if df_result['work_format_name'].notna().any():
        form_counts = df_result['work_format_name'].value_counts().reset_index()
        form_counts.columns = ['Категория', 'Значение']
        form_fig = px.pie(form_counts, names='Категория', values='Значение', title="Место работы")
    else:
        form_fig = None

    if exp_fig or form_fig:
        left_col, right_col = st.columns(2)
        if exp_fig:
            left_col.plotly_chart(exp_fig)
        if form_fig:
            right_col.plotly_chart(form_fig)

    # --- Топ работодателей ---
    df_with_salary = df_result[df_result['salary_avr'].notna()]
    if not df_with_salary.empty:
        employer_salary = df_with_salary.groupby('employer.name').agg({'salary_avr':'mean','id':'count'}).reset_index()
        employer_salary = employer_salary.rename(columns={'employer.name':'employer','salary_avr':'avg_salary','id':'vacancy_count'}).sort_values('avg_salary', ascending=False)
        top_employers = employer_salary.head(15)
        
        fig = px.bar(
            top_employers,
            x='employer',
            y='avg_salary',
            color='avg_salary',
            color_continuous_scale='blues',
            text='avg_salary',
            hover_data=['vacancy_count'],
            title="Топ-15 работодателей по средней зарплате"
        )
        st.plotly_chart(fig, use_container_width=True)

    # --- Таблица ---
    st.dataframe(df_result)
