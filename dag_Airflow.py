#!/usr/bin/env python
# coding: utf-8

# In[1]:


from datetime import datetime, timedelta
import pandas as pd
import pandahouse as ph
from io import StringIO
import requests

from airflow.decorators import dag, task
from airflow.operators.python import get_current_context


# In[ ]:





# In[2]:


default_args = {
    'owner': 'm.novikov',
    'depends_on_past': False,
    'retries': 3,
    'retry_delay': timedelta(minutes=7),
    'start_date': datetime(2022, 6, 16),
}


# In[3]:


schedule_interval = '0 23 * * *'


# In[2]:


connection = {'host': 'https://clickhouse.lab.karpov.courses',
                      'database':'simulator_20220520',
                      'user':'student', 
                      'password':'dpo_python_2020'
                     }

connection_load = {'host': 'https://clickhouse.lab.karpov.courses',
                      'database':'test',
                      'user':'student-rw', 
                      'password':'656e2b0c9c'
                     }


# In[15]:


@dag(default_args=default_args, schedule_interval=schedule_interval, catchup=False)
def dag_af_homework_novikov():
    
    @task()
    def extract_feed_actions():
        query_feed='''Select user_id, 
                             toDate(time) as day, 
                             age,   
                             gender, 
                             os, 
                             countIf(action, action ='like') as likes, 
                             countIf(action, action = 'view') as views 
                      from simulator_20220520.feed_actions
                      where day = today() - 1
                      group by user_id, day, age, gender, os
                        '''
        df_feed = ph.read_clickhouse(query=query_feed, connection=connection)
        return df_feed
    
    @task()
    def extract_message_actions():
        query_message= '''Select user_id, 
                                 messages_received,
                                 messages_sent, 
                                 users_received, 
                                 users_sent
                          from 
                              (Select user_id, 
                                      count(reciever_id) as messages_sent, 
                                      count(distinct reciever_id) as users_sent
                                  from simulator_20220520.message_actions
                                  where toDate(time) = today() - 1
                                  group by user_id) as t1
                         join (Select reciever_id, 
                                      count(user_id) as messages_received, 
                                      count(distinct user_id) as users_received
                                  from simulator_20220520.message_actions
                                  where toDate(time) = today() - 1
                                  group by reciever_id) as t2
                         on t1.user_id = t2.reciever_id
                         '''
        df_messages = ph.read_clickhouse(query=query_message, connection=connection)
        return df_messages
    
    @task
    def join_feed_and_messages(df_feed, df_messages):
        full_table = df_feed.merge(df_messages, how ='left', on='user_id')
        return full_table

    @task
    def age_slice(full_table):
        cut_labels = ['до 18', '18-32', '32-45', '45+']
        cut_bins = [0, 18, 32, 40, 150]
        full_table['age_intervals'] = pd.cut(full_table['age'], bins=cut_bins, labels=cut_labels)
        age_slice_df=full_table.groupby(['day', 'age_intervals']).agg({'likes': 'sum', 'views':'sum', 'messages_received': 'sum', 'messages_sent': 'sum', 'users_received': 'sum', 'users_sent':'sum'})
        age_slice_df['slice'] = 'age'
        return age_slice_df
    
    @task
    def gender_slice(full_table):
        full_table.loc[(full_table.gender == 0), ('gender')] = 'М'
        full_table.loc[(full_table.gender == 1), ('gender')] = 'Ж'
        gender_slice_df=full_table.groupby(['day', 'gender']).agg({'likes': 'sum', 'views':'sum', 'messages_received': 'sum', 'messages_sent': 'sum', 'users_received': 'sum', 'users_sent':'sum'})
        gender_slice_df['slice'] = 'gender'
        return gender_slice_df
    
    @task
    def os_slice(full_table):
        os_slice_df=full_table.groupby(['day', 'os']).agg({'likes': 'sum', 'views':'sum', 'messages_received': 'sum', 'messages_sent': 'sum', 'users_received': 'sum', 'users_sent':'sum'})
        os_slice_df['slice'] = 'os'
        return os_slice_df
    
    @task
    def final_table(age_slice_df, gender_slice_df, os_slice_df):
        final = pd.concat([gender_slice_df, age_slice_df, os_slice_df]).reset_index()
        final_1 = final.rename(columns={'gender': 'metric_values'})
        final_table_all = final_1.reindex(columns=['day', 'slice', 'metric_values', 'likes', 'views', 'messages_received', 'messages_sent', 'users_received', 'users_sent'])
        final_table_all = final_table_all.astype({
                                   'messages_received':'int64',
                                    'messages_sent':'int64',
                                    'users_received':'int64',
                                    'users_sent':'int64'})

        return final_table_all
   
    @task
    def load_table_to_clickhouse(final_table_all):
            table = '''CREATE TABLE IF NOT EXISTS test.m_novikov7
            (day Date, 
            slice String, 
            metric_values String, 
            likes UInt64, 
            views UInt64, 
            messages_received Int64, 
            messages_sent Int64, 
            users_received Int64, 
            users_sent Int64) 
            ENGINE = MergeTree
            '''
            ph.execute(query=table, connection=connection_load)
            ph.to_clickhouse(df=final_table_all, table='m_novikov7', connection=connection_load, index=False)

    
    df_feed = extract_feed_actions()
    df_messages = extract_message_actions()
    full_table = join_feed_and_messages(df_feed, df_messages)
    age_slice_df = age_slice(full_table)
    gender_slice_df = gender_slice(full_table)
    os_slice_df = os_slice(full_table)
    final_table_all = final_table(age_slice_df, gender_slice_df, os_slice_df)
    load_table_to_clickhouse(final_table_all)

dag_af_homework_novikov = dag_af_homework_novikov()
