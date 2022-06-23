#!/usr/bin/env python
# coding: utf-8

# In[2]:


import telegram
import pandas as pd
import pandahouse as ph
import numpy as np
import io
import matplotlib.pyplot as plt
import seaborn as sns


# In[3]:


connection = {'host': 'https://clickhouse.lab.karpov.courses',
                      'database':'simulator_20220520',
                      'user':'student', 
                      'password':'dpo_python_2020'
                     }


# In[45]:


stickiness_table = ph.read_clickhouse('WITH allthat as (SELECT month, month_quant, day, day_quant FROM (SELECT toMonth(time) as month, toDate(time) as day, count(Distinct user_id) as day_quant  from simulator_20220520.feed_actions group by month, day order by month, day) as t1 join (SELECT toMonth(time) as month, count(Distinct user_id) as month_quant  from simulator_20220520.feed_actions group by month order by month) as t2 on t1.month = t2.month) SELECT day, (round(day_quant/month_quant, 2)) as stickiness  FROM allthat where day > date_sub(DAY, 6, today())', connection=connection)
top_posts = ph.read_clickhouse("SELECT post_id, round(likes / views, 2) as CTR FROM (SELECT post_id, count(action) as likes  from (SELECT post_id, action, toDate(time) FROM simulator_20220520.feed_actions where time > date_sub(DAY, 6, today()) and action = 'like') group by post_id order by likes) t1 JOIN (SELECT post_id, count(action) as views  from (SELECT post_id, action, toDate(time) FROM simulator_20220520.feed_actions where time > date_sub(DAY, 6, today()) and action = 'view') group by post_id order by views desc ) t2 on t1.post_id = t2.post_id limit 20", connection=connection)
top_users = ph.read_clickhouse("SELECT user_id, count(reciever_id) as message_quant FROM (SELECT user_id, time, reciever_id FROM simulator_20220520.message_actions WHERE time > date_sub(DAY, 6, today())) group by user_id order by message_quant desc limit 20", connection=connection)
feed_and_message_new_members = ph.read_clickhouse("SELECT start, count(user_id) as quant  FROM (SELECT user_id,  min(toDate(time)) as start FROM  (SELECT t2.user_id as user_id, time as time from simulator_20220520.feed_actions t1 right join simulator_20220520.message_actions t2  on t1.user_id = t2.user_id) group by user_id) where start > date_sub(DAY, 6, today()) group by start", connection=connection)
feed_new_members_table = ph.read_clickhouse("SELECT start, count(user_id) as quant  FROM (SELECT user_id,  min(toDate(time)) as start FROM simulator_20220520.feed_actions group by user_id) where start > date_sub(DAY, 6, today()) group by start", connection=connection)
feed_new_members = sum(feed_new_members_table.quant) - sum(feed_and_message_new_members.quant)
activity = ph.read_clickhouse("SELECT day, messages, actions from (Select toDate(time) as day, count(reciever_id) as messages from simulator_20220520.message_actions group by day) t1 join (Select toDate(time) as day, count(action) as actions from simulator_20220520.feed_actions group by day) t2 on t1.day = t2.day order by day desc limit 7", connection=connection)


# In[ ]:


bot = telegram.Bot(token='5428603496:AAHNqFQVWZIkRvrLHbVhOpdJj2ttI0g2Q0Y')
chat_id = -715060805


# In[ ]:


msg = f'Новых пользователей ленты новостей {feed_new_members} {chr(10)}Новых пользователей ленты новостей и мессенджера {int(feed_and_message_new_members.quant)}'
bot.sendMessage(chat_id=chat_id, text=msg)


# In[18]:


week = np.datetime64('today') - np.timedelta64(6, 'D')


# In[7]:

sns.set_style("whitegrid") 
plt.rcParams['figure.figsize']=10,4
plot = sns.lineplot(data = stickiness_table, x = 'day', y = 'stickiness')
plt.title(f'Частота взаимодействия с продуктом за неделю c {week}')

plot_object = io.BytesIO()
plt.savefig(plot_object)
plot_object.name = 'test_plot.png'
plot_object.seek(0)

plt.close()
bot.sendPhoto(chat_id=chat_id, photo=plot_object)


# In[ ]:


top_table = top_posts.join(top_users)
file_object = io.StringIO()
top_table.to_csv(file_object)
file_object.name = 'TOP20_posts_and_users.csv'
file_object.seek(0)
bot.sendMessage(chat_id=chat_id, text=f'Самый популярный пост: {top_posts.post_id[0]} {chr(10)}Самый активный клиент мессенджера: {top_users.user_id[0]} {chr(10)}Полная таблица  активности во вложении:')
bot.sendDocument(chat_id=chat_id, document=file_object)


# In[36]:


fig, ax = plt.subplots(1, 2, figsize=(12,4))
plot = sns.lineplot(data = activity, x = 'day', y = 'actions', ax=ax[0])
plot1 = sns.lineplot(data = activity, x = 'day', y = 'messages', ax=ax[1])
plt.title(f'Активность ленты и мессенджера за неделю c {week}', loc='right')
plt.subplots_adjust(wspace=0.3, hspace=0)

plot_object = io.BytesIO()
plt.savefig(plot_object)
plot_object.name = 'test_plot.png'
plot_object.seek(0)

plt.close()
bot.sendPhoto(chat_id=chat_id, photo=plot_object)

