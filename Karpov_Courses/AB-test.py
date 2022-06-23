#!/usr/bin/env python
# coding: utf-8

# In[1]:


from read_db.CH import Getch
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import pandahouse as ph
from datetime import date
from scipy import stats
import numpy as np

Задание № 1
Итак, что нужно сделать: у нас есть данные АА-теста с '2022-04-17' по '2022-04-23'. Вам нужно сделать симуляцию, как будто мы провели 10000 АА-тестов. На каждой итерации вам нужно сформировать подвыборки с повторением в 500 юзеров из 2 и 3 экспериментальной группы. Провести сравнение этих подвыборок t-testом.

1. Построить гистограмму распределения получившихся 10000 p-values.

2. Посчитать, какой процент p values оказался меньше либо равен 0.05

3. Написать вывод по проведенному АА-тесту, корректно ли работает наша система сплитования.
# In[2]:


df = Getch("""SELECT exp_group, 
                user_id,
                sum(action = 'like') as likes,
                sum(action = 'view') as views,
                likes/views as ctr
        FROM simulator_20220520.feed_actions 
        WHERE toDate(time) between '2022-04-17' and '2022-04-23'
                and exp_group in (2,3)
        GROUP BY exp_group, user_id
    """).df


# In[3]:


big =[]
for x in range(10000):
    group_2 = df[df.exp_group == 2][['user_id', 'ctr']].sample(500, replace=True)
    group_3 = df[df.exp_group == 3][['user_id', 'ctr']].sample(500, replace=True)
    p_values = stats.ttest_ind(group_2.ctr, group_3.ctr, equal_var=False)
    big.append(abs(p_values[1]))
    
data = pd.DataFrame()
data['p'] = pd.DataFrame(big)


# In[4]:


data[data.p <= 0.05].count()


# In[5]:


sns.histplot(data)

Вывод: Чуть больше 5%(538) значений p меньше 0.05, система сплитования работает корректно, распредиление равномерное.Задание № 2
Пришло время проанализировать результаты эксперимента, который мы провели вместе с командой дата сайентистов. Эксперимент проходил с 2022-04-24 по 2022-04-30 включительно. Для эксперимента были задействованы 2 и 1 группы. 

В группе 2 был использован один из новых алгоритмов рекомендации постов, группа 1 использовалась в качестве контроля. 

Основная гипотеза заключается в том, что новый алгоритм во 2-й группе приведет к увеличению CTR. 

Ваша задача — проанализировать данные АB-теста. 
    Выбрать метод анализа и сравнить CTR в двух группах (мы разбирали t-тест, Пуассоновский бутстреп, тест Манна-Уитни, t-тест на сглаженном ctr (α=5) а также t-тест и тест Манна-Уитни поверх бакетного преобразования).
    Сравните данные этими тестами. А еще посмотрите на распределения глазами. Почему тесты сработали так как сработали? 
    Опишите потенциальную ситуацию, когда такое изменение могло произойти. Тут нет идеального ответа, подумайте.
    Напишите рекомендацию, будем ли мы раскатывать новый алгоритм на всех новых пользователей или все-таки не стоит.
# In[3]:


test = Getch("""SELECT exp_group, 
                user_id,
                sum(action = 'like') as likes,
                sum(action = 'view') as views,
                likes/views as ctr
        FROM simulator_20220520.feed_actions 
        WHERE toDate(time) between '2022-04-24' and '2022-04-30'
                and exp_group in (1,2)
        GROUP BY exp_group, user_id
    """).df


# In[4]:


sns.histplot(data = test, x='ctr', hue='exp_group', palette = ['r', 'b'], alpha=0.5, kde=False)


# In[5]:


def get_smothed_ctr(user_likes, user_views, global_ctr, alpha):
    smothed_ctr = (user_likes + alpha * global_ctr) / (user_views + alpha)
    return smothed_ctr

global_ctr_1 = test[test.exp_group == 1].likes.sum()/test[test.exp_group == 1].views.sum()
global_ctr_2 = test[test.exp_group == 2].likes.sum()/test[test.exp_group == 2].views.sum()

group1 = test[test.exp_group == 2].copy()
group1['smothed_ctr'] = test.apply(lambda x: get_smothed_ctr(x['likes'], x['views'], global_ctr_1, 5), axis=1)

sns.distplot(group1.ctr, kde = False)
sns.distplot(group1.smothed_ctr, kde = False)


# In[13]:


A_gt_B = 0
for _ in range(10000):
    A_gt_B+= test[test.exp_group == 1].ctr.sample().values[0] > test[test.exp_group == 2].ctr.sample().values[0]
    
stats.mannwhitneyu(test[test.exp_group == 2].ctr, test[test.exp_group == 1].ctr, alternative = 'two-sided')
print(f'В {A_gt_B/100}% случаев A > B')


# In[7]:


def bootstrap(likes1, views1, likes2, views2, n_bootstrap=3000):

    poisson_bootstraps1 = stats.poisson(1).rvs(
        (n_bootstrap, len(likes1))).astype(np.int64)

    poisson_bootstraps2 = stats.poisson(1).rvs(
            (n_bootstrap, len(likes2))).astype(np.int64)
    
    globalCTR1 = (poisson_bootstraps1*likes1).sum(axis=1)/(poisson_bootstraps1*views1).sum(axis=1)
    
    globalCTR2 = (poisson_bootstraps2*likes2).sum(axis=1)/(poisson_bootstraps2*views2).sum(axis=1)

    return globalCTR1, globalCTR2


# In[17]:


likes1 = test[test.exp_group == 1].likes.to_numpy()
views1 = test[test.exp_group == 1].views.to_numpy()
likes2 = test[test.exp_group == 2].likes.to_numpy()
views2 = test[test.exp_group == 2].views.to_numpy()

ctr1, ctr2 = bootstrap(likes1, views1, likes2, views2)

sns.histplot(ctr1)
sns.histplot(ctr2)


# In[16]:


sns.histplot(ctr2 - ctr1)


# In[ ]:


Вывод:При построении графика видим, что во 2ой группе получается не нормальное распределение, я хотел применить метод Мана-Уитни на сглаженном ctr, 
но при его реализации грифик не сильно изменился,  поэтому я так же воспользовался пуассоновским бутстрепом. Из обоих методов можно сделать вывод, 
что в контрольной группе значения на 5% выше (на 5% чаще встречаются более высокие значения) чем в тестовой, т.е. новый алгоритм нельзя назвать удачным.

Задание №3

    Проанализируйте тест между группами 0 и 3 по метрике линеаризованных лайков. Видно ли отличие? Стало ли 𝑝−𝑣𝑎𝑙𝑢𝑒 меньше?

    Проанализируйте тест между группами 1 и 2 по метрике линеаризованных лайков. Видно ли отличие? Стало ли 𝑝−𝑣𝑎𝑙𝑢𝑒 меньше?
# In[34]:


group = Getch("""SELECT exp_group, 
                user_id,
                sum(action = 'like') as likes,
                sum(action = 'view') as views,
                likes/views as ctr
        FROM simulator_20220520.feed_actions 
        WHERE toDate(time) between '2022-04-24' and '2022-04-30'
                and exp_group in (0, 1, 2, 3)
        GROUP BY exp_group, user_id
    """).df


# In[35]:


xx_1 = group[group.exp_group == 0].copy()
xx_2 = group[group.exp_group ==3].copy()
stats.ttest_ind(xx_1.ctr, xx_2.ctr, equal_var=False)


# In[31]:


ctrcontrol_1 = sum(xx_1.likes)/sum(xx_1.views)
ctrcontrol_2 = sum(xx_2.likes)/sum(xx_2.views)
xx_1['linearised_likes'] = xx_1.likes -  ctrcontrol_1 * xx_1.views
xx_2['linearised_likes'] = xx_2.likes -  ctrcontrol_2 * xx_2.views
sns.distplot(xx_1['linearised_likes'], kde = False)
sns.distplot(xx_2['linearised_likes'], kde = False)


# In[32]:


stats.ttest_ind(xx_1['linearised_likes'], xx_2['linearised_likes'], equal_var=False)


# In[ ]:





# In[36]:


yy_1 = group[group.exp_group ==1].copy()
yy_2 = group[group.exp_group ==2].copy()
stats.ttest_ind(yy_1.ctr, yy_2.ctr, equal_var=False)


# In[33]:


ctrcontrol_21 = sum(yy_1.likes)/sum(yy_1.views)
ctrcontrol_22 = sum(yy_2.likes)/sum(yy_2.views)
yy_1['linearised_likes'] = yy_1.likes -  ctrcontrol_21 * yy_1.views
yy_2['linearised_likes'] = yy_2.likes -  ctrcontrol_22 * yy_2.views
sns.distplot(yy_1['linearised_likes'], kde = False)
sns.distplot(yy_2['linearised_likes'], kde = False)


# In[28]:


stats.ttest_ind(yy_1['linearised_likes'], yy_2['linearised_likes'], equal_var=False)


# In[ ]:


Вывод: В выборках 0 и 3 на графике отличия минимальны, p-value уменьшилось
В выборках 1 и 2 на графике отличия достаточно сильные, p-value наоборот увеличилось

