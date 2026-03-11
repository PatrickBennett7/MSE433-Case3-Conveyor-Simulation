#!/usr/bin/env python
# coding: utf-8

# # Initialization

# In[1]:

import os
import random
def generate_random_number(seed,begin,end):
    random.seed(seed)  # Set the random seed
    return random.randint(begin, end)


# In[2]:


import pandas as pd
import numpy as np
def saving(lst,name):
  df = pd.DataFrame(lst)

  # Saving the DataFrame to a CSV file
  df.to_csv(name, index=False, header=False)
  print(name)
  print(df)

  print("DataFrame saved to", name)


# In[3]:


seed = int(os.environ.get('REPLICATION_NUM', 1)) + 100 
n_orders    = int(os.environ['N_ORDERS'])    if 'N_ORDERS'    in os.environ else generate_random_number(seed, 10, 15)
n_itemtypes = int(os.environ['N_ITEMTYPES']) if 'N_ITEMTYPES' in os.environ else generate_random_number(seed, 7, 10)
n_totes     = int(os.environ['N_TOTES'])     if 'N_TOTES'     in os.environ else generate_random_number(seed, 15, 20)

print("number of orders between 10 and 15:", n_orders)
print("number of itemtypes between 7 and 10:", n_itemtypes)
print("number of totes between 15 and 20:", n_totes)


# # The list of order_itemtypes
# In this list, element [i][j] indicates the itemstype to which the jth item of order i has been assigned.

# The number of iteams from each itemtype in each order is a random integer between 0 and 3

# In[4]:

random.seed(seed)

order_itemtypes = [[] for _ in range(n_orders)]  # Initialize an empty list of lists
order_quantities = [[] for _ in range(n_orders)]
for i in range(n_orders):
  order_size = random.randint(1, 3)

  tt = random.sample(range(0, n_itemtypes - 1), order_size)
  qq = [random.randint(1, 3) for _ in range(order_size)]
  order_itemtypes[i] = (tt)
  order_quantities[i] = (qq)

print("---------------------")
# print("order_itemtypes")
print("order item types:")
for t in range(n_orders):
  print(order_itemtypes[t])

print(".....................................................")
print("order item quantities:")
for t in range(n_orders):

  print(order_quantities[t])
print(".....................................................")
n_items = [len(row) for row in order_itemtypes]


# # The list of order_totes
# In this list, element [i][j] indicates the tote to which the jth item of order i has been assigned.

# There is a 50% probability that each subsequent item will be assigned to the same tote as the first item.

# In[5]:


orders_totes = [[] for _ in range(n_orders)]
for i in range(n_orders):
    for j in range(len(order_itemtypes[i])):
        if j == 0:
            orders_totes[i].append(random.randint(0, n_totes-1))
        else:
            if random.randint(0, 1) == 0:
                orders_totes[i].append(orders_totes[i][0])
            else:
                orders_totes[i].append(random.randint(0, n_totes-1))
print("orders_totes")
(orders_totes)


# In[6]:


import os
os.makedirs("Data/raw", exist_ok=True)
saving(order_itemtypes,"Data/raw/order_itemtypes.csv")
saving(orders_totes,"Data/raw/orders_totes.csv")
saving(order_quantities,"Data/raw/order_quantities.csv")

