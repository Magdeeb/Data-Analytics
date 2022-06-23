#!/usr/bin/env python
# coding: utf-8

# In[1]:


from read_db.CH import Getch
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import telegram
import pandahouse as ph
from datetime import date
import io
import sys 
import os


# In[7]:


def check_anomaly(df, metric, a = 4, n = 6):
    #проверяет  метрику на аномальные значения
    df['q25'] = df[metric].shift(1).rolling(n).quantile(0.25)
    df['q75'] = df[metric].shift(1).rolling(n).quantile(0.75)
    df['iqr'] = df['q75'] - df['q25']
    df['up']= df['q75'] + a*df['iqr']
    df['low'] = df['q25'] - a*df['iqr']
    
    df['up'] = df['up'].rolling(n, center=True, min_periods = 1).mean()
    df['low'] = df['low'].rolling(n, center=True, min_periods = 1).mean()
    
    if df[metric].iloc[-1] > df['up'].iloc[-1] and df[metric].iloc[-1] < df['low'].iloc[-1]:
        is_alert = 1
    else:
        is_alert = 0
    
    return is_alert, df 
                                                        
                                                        
                                                        

def run_alerts(chat=None):
    #система алертов
    chat_id = chat or -652068442
    bot = telegram.Bot(token='5428603496:AAHNqFQVWZIkRvrLHbVhOpdJj2ttI0g2Q0Y')
    
    data = Getch('''SELECT t1.fmperiods, date, hm, uniq_users, likes, views, ctr, uniq_message_users, messages_amount 
    FROM (SELECT
                toStartOfFifteenMinutes(time) as fmperiods,
                toDate(time) as date,
                formatDateTime(fmperiods, '%R') as hm, 
                uniqExact(user_id) as uniq_users,
                countIf(user_id, action = 'like') as likes,
                countIf(user_id, action = 'view') as views,
                (likes/views) as ctr
            FROM simulator_20220520.feed_actions
            WHERE time >= today() - 1 and time < toStartOfFifteenMinutes(now())
            GROUP BY fmperiods, date, hm ORDER BY fmperiods) t1 
    JOIN (SELECT
                toStartOfFifteenMinutes(time) as fmperiods,
                uniqExact(user_id) as uniq_message_users,
                count(reciever_id) as messages_amount
            FROM simulator_20220520.message_actions
            WHERE time >= today() - 1 and time < toStartOfFifteenMinutes(now())
            GROUP BY fmperiods ORDER BY fmperiods) t2 
    on t1.fmperiods = t2.fmperiods''').df

    metricks_list = ['uniq_users', 'uniq_message_users', 'likes', 'views', 'messages_amount', 'ctr', ]
    for metric in metricks_list:
        print(metric)
        df = data[['fmperiods', 'date', 'hm', metric]].copy()
        is_alert, df = check_anomaly(df, metric)
        
        if is_alert == 1 or True:
            current_value = df[metric].iloc[-1]
            value_diff = abs(1 - (df[metric].iloc[-1]/df[metric].iloc[-2]))
            msg = f'''Метрика {metric}:\nТекущее значение {current_value:.2f}\nОтклонение от предыдущего значения {value_diff:.2%}\nhttps://superset.lab.karpov.courses/superset/dashboard/923/'''
            
          
            sns.set(rc={'figure.figsize': (16, 10)})
            plt.tight_layout()
            sns.set_style("whitegrid")                                           
            ax = sns.lineplot(x=df['fmperiods'], y=df['up'], label='up', linestyle='-.')
            ax = sns.lineplot(x=df['fmperiods'], y=df[metric], label='metric')
            ax = sns.lineplot(x=df['fmperiods'], y=df['low'], label='low', linestyle='-.')
                      
            ax.set(xlabel='time')
            ax.set(ylabel=metric)
            
            ax.set_title(metric)
            ax.set(ylim=(0, None))
                                                        
            plot_object = io.BytesIO()
            ax.figure.savefig(plot_object)
            plot_object.seek(0)
            plot_object.name = '{0}.png'.format(metric)
            plt.close()
            
            bot.sendMessage(chat_id=chat_id, text=msg)
            bot.sendPhoto(chat_id=chat_id, photo=plot_object)
        
    return

try:
    run_alerts()
except Exception as e:
    print(e)

