import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns
from statsbombpy import sb
from mplsoccer import Pitch
import io
import time

@st.cache_data
def carregar_competicoes():
    competicoes = sb.competitions()
    if competicoes.empty:
        st.warning('Nenhuma competição encontrada.')
    return competicoes

@st.cache_data
def carregar_dados(competition_id, season_id):
    partidas = sb.matches(competition_id=competition_id, season_id=season_id)
    if partidas.empty:
        st.warning('Nenhuma partida encontrada para a competição selecionada.')
    return partidas

@st.cache_data
def carregar_eventos_partida(match_id):
    eventos = sb.events(match_id=match_id)
    if eventos.empty:
        st.warning('Nenhum evento encontrado para a partida selecionada.')
    return eventos

def exibir_eventos_jogador(events, jogadores_selecionados=None, num_events=None, intervalo=None):
    if jogadores_selecionados:
        for jogador in jogadores_selecionados:
            eventos_jogador = events[events['player'] == jogador]
            
            if intervalo:
                eventos_jogador = eventos_jogador[(eventos_jogador['minute'] >= intervalo[0]) & 
                                                  (eventos_jogador['minute'] <= intervalo[1])]

            if not eventos_jogador.empty:
                contagem_eventos = eventos_jogador['type'].value_counts().reset_index()
                contagem_eventos.columns = ['Tipo de Evento', 'Total']
                st.write(f'Total de cada tipo de evento para o jogador **{jogador}**:')
                st.table(contagem_eventos)
                st.write(f'Exibindo os primeiros {num_events} eventos para o jogador **{jogador}**:')
                st.table(eventos_jogador[['player', 'type', 'location', 'pass_end_location', 'minute']].head(num_events))
            else:
                st.warning(f'Nenhum evento encontrado para o jogador **{jogador}**.')
    else:
        contagem_eventos_geral = events['type'].value_counts().reset_index()
        contagem_eventos_geral.columns = ['Tipo de Evento', 'Total']
        st.write('Total de cada tipo de evento (geral):')
        st.table(contagem_eventos_geral)
        st.write(f'Exibindo os primeiros {num_events} eventos gerais:')
        st.table(events[['player', 'type', 'location', 'pass_end_location', 'minute']].head(num_events))

def exibir_estats_partida(eventos):
    if 'outcome' in eventos.columns:
        gols = eventos[(eventos['type'] == 'Shot') & (eventos['shot_outcome'] == 'Goal')].shape[0]
    else:
        gols = 0
    passes = len(eventos[eventos['type'] == 'Pass'])
    chutes = len(eventos[eventos['type'] == 'Shot'])

    st.metric(label='Total de Gols', value=gols, delta=f"{gols}", delta_color="normal" if gols > 0 else "inverse")
    st.metric(label='Total de Passes', value=passes, delta=f"{passes}", delta_color="normal" if passes > 0 else "inverse")
    st.metric(label='Total de Chutes', value=chutes, delta=f"{chutes}", delta_color="normal" if chutes > 0 else "inverse")

    conversion_rate = (gols / chutes) * 100 if chutes > 0 else 0
    st.metric(label='Taxa de Conversão de Chutes (%)', value=f"{conversion_rate:.2f}%", delta_color="normal" if conversion_rate > 0 else "inverse")

    return {'Gols': gols, 'Passes': passes, 'Chutes': chutes, 'Taxa de Conversão': conversion_rate}

def exibir_eventos_partida(eventos, num_events):
    eventos_relevantes = eventos[eventos['type'].isin(['Pass', 'Shot', 'Foul Committed', 'Offside', 'Substitution'])]
    
    if not eventos_relevantes.empty:
        contagem_eventos = eventos_relevantes['type'].value_counts().reset_index()
        contagem_eventos.columns = ['Tipo de Evento', 'Total']
        
        st.subheader('Total de cada tipo de evento:')
        st.dataframe(contagem_eventos)
    else:
        st.warning('Nenhum evento relevante encontrado para a partida.')

def plotar_mapa_passes(eventos, jogadores_selecionados):
    for jogador in jogadores_selecionados:
        pitch = Pitch(line_color='black')
        fig, ax = pitch.draw()
        passes = eventos[(eventos['type'] == 'Pass') & (eventos['player'] == jogador)]

        st.subheader(f'Mapa de Passes: {jogador}')     
        if not passes.empty:
            for _, row in passes.iterrows():
                pitch.arrows(row['location'][0], row['location'][1],
                             row['pass_end_location'][0], row['pass_end_location'][1],
                             ax=ax, color='blue', width=2, headwidth=3, headlength=4)
            st.pyplot(fig)  
            plt.clf()
        else:
            st.warning(f'Nenhum passe encontrado para o jogador **{jogador}**.')

def plotar_mapa_chutes(eventos, jogadores_selecionados):
    for jogador in jogadores_selecionados:
        pitch = Pitch(line_color='black')
        fig, ax = pitch.draw()
        shots = eventos[(eventos['type'] == 'Shot') & (eventos['player'] == jogador)]
        
        st.subheader(f'Mapa de Chutes: {jogador}')       
        if not shots.empty:
            for _, row in shots.iterrows():
                pitch.scatter(row['location'][0], row['location'][1],
                              ax=ax, color="red", s=row['shot_statsbomb_xg'] * 100, alpha=0.6)
            st.pyplot(fig)  
            plt.clf()  
        else:
            st.warning(f'Nenhum chute encontrado para o jogador **{jogador}**.')

def plotar_taxa_conversao(eventos):
    chutes = eventos[eventos['type'] == 'Shot']
    if not chutes.empty:
        conversion_data = chutes.groupby('match_id').agg(
            Gols=('shot_outcome', lambda x: (x == 'Goal').sum()),
            Chutes=('shot_outcome', 'count')
        ).reset_index()
        conversion_data['Taxa de Conversão (%)'] = (conversion_data['Gols'] / conversion_data['Chutes'] * 100).fillna(0)

        sns.barplot(data=conversion_data, x='match_id', y='Taxa de Conversão (%)', palette='viridis')
        plt.xticks(rotation=45)
        plt.title('Taxa de Conversão de Chutes em Gols por Partida')
        plt.xlabel('ID da Partida') 
        plt.ylabel('Taxa de Conversão (%)')
       
def exibir_estats_jogador(eventos, jogadores_selecionados): 
    for jogador in jogadores_selecionados:
        if 'outcome' in eventos.columns:
            gols = eventos[(eventos['player'] == jogador) & (eventos['type'] == 'Shot') & (eventos['shot_outcome'] == 'Goal')].shape[0]
        else:
            gols = 0
        passes = len(eventos[(eventos['player'] == jogador) & (eventos['type'] == 'Pass')])
        chutes = len(eventos[(eventos['player'] == jogador) & (eventos['type'] == 'Shot')])

        st.metric(label=f'Total de Gols - {jogador}', value=gols, delta=gols)
        st.metric(label=f'Quantidade de Passes - {jogador}', value=passes, delta=passes)
        st.metric(label=f'Quantidade de Chutes - {jogador}', value=chutes, delta=chutes)

        conversion_rate = (gols / chutes) * 100 if chutes > 0 else 0
        st.metric(label=f'Taxa de Conversão de Chutes (%) - {jogador}', value=f"{conversion_rate:.2f}%", delta=f"{conversion_rate:.2f}%")


def main():
    st.title('Dashboard Interativo')
    st.subheader('Trabalhando com análise de dados no mundo do futebol')

    with st.spinner('Carregando dados...'):
        time.sleep(3)

    st.sidebar.title('Filtros')

    # Carregando competições
    competicoes = carregar_competicoes()
    competicoes_unicas = competicoes.drop_duplicates(subset='competition_id')

    # Adicionando um estado para armazenar o ID da competição
    if 'id_competicao' not in st.session_state:
        st.session_state.id_competicao = None

    id_competicao = st.sidebar.selectbox(
        'Selecione a competição', 
        competicoes_unicas['competition_id'], 
        format_func=lambda x: competicoes_unicas[competicoes_unicas['competition_id'] == x]['competition_name'].values[0]
    )

    # Armazenando o id_competicao no session_state
    if id_competicao != st.session_state.id_competicao:
        st.session_state.id_competicao = id_competicao

    # Carregando as partidas da competição selecionada
    temporadas = competicoes[competicoes['competition_id'] == id_competicao]['season_id'].unique()
    
    if 'id_temporada' not in st.session_state:
        st.session_state.id_temporada = None
    
    id_temporada = st.sidebar.selectbox('Selecione a temporada', temporadas)

    if id_temporada != st.session_state.id_temporada:
        st.session_state.id_temporada = id_temporada
    
    partidas = carregar_dados(competition_id=id_competicao, season_id=id_temporada)

    if not partidas.empty:
        id_partida = st.sidebar.selectbox(
            'Selecione a partida',
            partidas['match_id'], 
            format_func=lambda x: f"{partidas[partidas['match_id'] == x]['home_team'].values[0]} vs {partidas[partidas['match_id'] == x]['away_team'].values[0]}"
        )

        # Carregando eventos da partida selecionada
        progress_bar = st.progress(0)
        eventos = carregar_eventos_partida(id_partida)
        progress_bar.progress(100)

        if not eventos.empty:
            st.sidebar.title('Análise de Eventos')

            st.header('Estatísticas da Partida')
            estats = exibir_estats_partida(eventos)

            st.sidebar.header('Eventos por Jogador')
            jogadores = eventos['player'].unique()
            if 'jogadores_selecionados' not in st.session_state:
                st.session_state.jogadores_selecionados = []

            jogadores_selecionados = st.sidebar.multiselect('Selecione os jogadores', jogadores)
            st.session_state.jogadores_selecionados = jogadores_selecionados

            num_events = st.sidebar.number_input('Número de eventos a exibir', min_value=1, max_value=100, value=10)
            if 'intervalo' not in st.session_state:
                st.session_state.intervalo = (0, 90)
            intervalo = st.sidebar.slider('Intervalo de minutos', 0, 90, (0, 90))
            st.session_state.intervalo = intervalo

            exibir_eventos_jogador(eventos, jogadores_selecionados, num_events, intervalo)

            st.header('Eventos da Partida')
            exibir_eventos_partida(eventos, num_events)

            download_data = st.sidebar.button("Download dos dados da partida em CSV")
            if download_data:
                buffer = io.StringIO()
                eventos.to_csv(buffer, index=False)
                st.sidebar.download_button("Baixar dados", 
                                           buffer.getvalue(), 
                                           "dados_partida.csv", 
                                           "text/csv")

            if jogadores_selecionados:
                exibir_estats_jogador(eventos, jogadores_selecionados)

            st.header('Mapas de Passes e Chutes e Taxa de Conversão')
            if st.sidebar.button('Plotar Mapa de Passes'):
                plotar_mapa_passes(eventos, jogadores_selecionados)
            if st.sidebar.button('Plotar Mapa de Chutes'):
                plotar_mapa_chutes(eventos, jogadores_selecionados)

            if st.sidebar.button('Plotar Taxa de Conversão'):
                plotar_taxa_conversao(eventos)
            if st.sidebar.button('Download dos dados filtrados'):
                buffer = io.BytesIO()
                eventos.to_csv(buffer, index=False)
                buffer.seek(0)
                st.download_button(label="Download dos Eventos Filtrados", 
                                   data=buffer, 
                                   file_name='eventos_filtrados.csv', 
                                   mime='text/csv')
    else:
        st.warning('Nenhuma partida encontrada para a competição e temporada selecionadas.')


if __name__ == "__main__":
    main()
