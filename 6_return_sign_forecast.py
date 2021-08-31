# -*- coding: utf-8 -*-
"""TP6_DLF.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1js3saP9sEKhdkef2NB8tJO4e2Rdtouv_
"""

!pip install yfinance

import yfinance as yf
from tensorflow.keras import Sequential
from tensorflow.keras.layers import Dense, Conv1D, MaxPool1D, Dropout, LeakyReLU, BatchNormalization, LSTM
from tensorflow.keras.losses import BinaryCrossentropy
from tensorflow.keras.optimizers import Adam
import tensorflow as tf
import tensorflow.keras.backend as K
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from google.colab import drive
drive.mount('/content/drive')
DRIVE = '/content/drive/MyDrive/Colab Notebooks'

"""# Préparation de données
type de prévision : classification<br>
type de représentation de données : signes( +, -, 0)<br>
Architecture NN: 2 layers of LSTM model and dense output layer with RELU activation<br>


"""

def raw_data(cols):
    return pd.DataFrame(yf.download("^GSPC")[cols].dropna())

def log_return(cols):
    log_data = np.log(raw_data(cols))
    return log_data.diff().dropna()

def get_sign(df):
    df[(df > -1e-4) & (df < 1e-4)] = 0
    df[df > 0] = 1
    df[df < 0] = -1
    return df

#split a univariate sequence into samples
def split_sequence_univariate(sequence, n_steps):
    X, y = list(), list()
    for i in range(len(sequence)):
        # find the end of this pattern
        end_ix = i + n_steps
        # check if we are beyond the sequence
        if end_ix > len(sequence)-1:
            break
            
        # gather input and output parts of the pattern
        seq_x, seq_y = sequence[i:end_ix], sequence[end_ix]
        X.append(seq_x)
        y.append(seq_y)
    return np.array(X), np.array(y)

# split a multivariate sequence into samples
def split_sequences_multivariate(sequences, n_steps):
    sequences = sequences.reshape((len(sequences), -1))
    X, y = list(), list()
    for i in range(len(sequences)):
# find the end of this pattern
        end_ix = i + n_steps
# check if we are beyond the dataset
        if end_ix > len(sequences)-1:
            break
# gather input and output parts of the pattern
        seq_x, seq_y = sequences[i:end_ix, :], sequences[end_ix, 0]
        X.append(seq_x)
        y.append(seq_y.flatten())
    return np.array(X), np.array(y)


def train_test_set(df, len_seq, batch, test_in_batch=False):
    train_len = int(len(df) * 0.8)
    train_set = df.iloc[:train_len, :].values
    test_set = df.iloc[train_len:, :].values
    train_x, train_y = split_sequences_multivariate(train_set, len_seq)
    test_x, test_y = split_sequences_multivariate(test_set, len_seq)

    train_x, train_y = train_x[:batch * (len(train_x) // batch)], train_y[:batch * (len(train_y) // batch)]
    batches = tf.data.Dataset.from_tensor_slices((train_x, train_y)).shuffle(train_x.shape[0]).batch(batch)

    print('train batch: %s*%s, train set shape: %s, train target shape: %s' %
          (batch, len(train_x) // batch, train_x.shape, train_y.shape))
    if test_in_batch:
        test_x, test_y = test_x[:batch * (len(test_x) // batch)], test_y[:batch * (len(test_y) // batch)]
        test_batches = tf.data.Dataset.from_tensor_slices((test_x, test_y)).batch(batch)
        print('test batch: %s*%s, test set shape: %s, test target shape: %s' % 
              (batch, len(test_x) // batch, test_x.shape, test_y.shape))
        return batches, test_batches, None


    print('test set shape: %s, test target shape: %s' % (test_x.shape, test_y.shape))
    return batches, test_x, test_y


def run_lstm(dataset, len_seq, units, epochs, batch):
    with tf.device('/device:GPU:0'):
        train_batch, test_x, test_y = train_test_set(dataset, len_seq, batch)

        model = Sequential([
            # Shape [batch, time, features] => [batch, time, lstm_units]
            LSTM(units, input_shape=(len_seq,test_x.shape[-1]), return_sequences=True),
            LSTM(units,  return_sequences=False),
            # Shape => [batch, time, features]
            Dense(3, activation='relu'),
            Dense(1)
        ])
        # early_stopping = tf.keras.callbacks.EarlyStopping(monitor='val_loss',
        #                                                 patience=patience,
        #                                                 mode='min')

        model.compile(loss=tf.losses.MeanSquaredError(),
                        optimizer=tf.optimizers.Adam(),
                        metrics=[tf.metrics.MeanAbsoluteError()])
        print(model.summary())

        history = model.fit(train_batch, epochs=epochs, verbose=0)
                            # callbacks=[early_stopping])
        print('*** model training done ***')
        
        plt.plot(history.history['loss'])
        plt.xlabel('epoch')
        plt.ylabel('mse')
        plt.show()

        # to do : use test set to calculate metrics
        return model, test_x, test_y

adjclose_ret = log_return('Adj Close') # dataframe
plt.plot(adjclose_ret)
plt.show()
adjclose_ret = get_sign(adjclose_ret)
adjclose_ret

"""# 1 Rendement seuls"""

LSTM1, TX1, TY1 = run_lstm(adjclose_ret,
                         len_seq=100, units=128, epochs=100, batch=64)

PRED1 = np.sign(LSTM1(TX1, training=False).numpy().flatten())
print(np.sign(PRED1))
print(np.sum(PRED1 == TY1.flatten()) / len(PRED1))
# plt.plot(TY, label='actual', alpha=0.7)
# plt.plot(PRED, label='predict')
# plt.legend()

"""[result]: We can get a precision of 50.02% on test set.

# 2 Rendements et OHLC
"""

def data_with_log_ratio():
    data = raw_data(['Open', 'Close', 'High', 'Low'])
    res = get_sign(log_return('Adj Close'))
    data['logHO'] = np.ma.log(data['High'].values / data['Open'].values).filled(0)
    data['logLO'] = np.ma.log(data['Low'].values / data['Open'].values).filled(0)
    data['logCO'] = np.ma.log(data['Close'].values / data['Open'].values).filled(0)
    data = data[['logHO','logLO','logCO']]
    data = data[(data.T != 0).any()]
    # data=(data-data.mean())/data.std()
    return pd.merge(res, data, left_index=True, right_index=True)

data_log_ratio = data_with_log_ratio()

LSTM2, TX2, TY2 = run_lstm(data_log_ratio,
                         len_seq=100, units=128, epochs=200, batch=64)

PRED2 = np.sign(LSTM2(TX2, training=False).numpy().flatten())
print(np.sign(PRED2))
print(np.sum(PRED2 == TY2.flatten()) / len(PRED2))

"""[result]: We can get a precision of 50.78% on test set.

## 2.bis Rendements et signes de OHLC
"""

def data_with_log_ratio_sign():
    data = raw_data(['Open', 'Close', 'High', 'Low'])
    res = get_sign(log_return('Adj Close'))
    data['logHO'] = np.ma.log(data['High'].values / data['Open'].values).filled(0)
    data['logLO'] = np.ma.log(data['Low'].values / data['Open'].values).filled(0)
    data['logCO'] = np.ma.log(data['Close'].values / data['Open'].values).filled(0)
    data = data[['logHO','logLO','logCO']]
    data = data[(data.T != 0).any()]
    data = get_sign(data)
    # data=(data-data.mean())/data.std()
    return pd.merge(res, data, left_index=True, right_index=True)

data_log_ratio_sign = data_with_log_ratio_sign()
print(data_log_ratio_sign)
LSTM2c, TX2c, TY2c = run_lstm(data_log_ratio_sign,
                         len_seq=100, units=128, epochs=200, batch=64)
PRED2c = np.sign(LSTM2c(TX2c, training=False).numpy().flatten())
print(np.sign(PRED2c))
print(np.sum(PRED2c == TY2c.flatten()) / len(PRED2c))

"""[result]: We can get a precision of 51.05% on test set.

# 3 Rendement, OHLC et volume
"""

def data_ratio_volume():
    data_lr = data_with_log_ratio()
    
    data = raw_data('Volume')
    data['Volume'] = np.ma.log(data['Volume'].values).filled(0)
    # data.plot()
    # data=(data-data.mean())/data.std()
    return pd.merge(data_lr, data, left_index=True, right_index=True)

data_full = data_ratio_volume()

print(data_full)
# data_full['Volume'].plot()

LSTM3, TX3, TY3 = run_lstm(data_full,
                         len_seq=100, units=128, epochs=100, batch=64)

PRED3 = np.sign(LSTM3(TX3, training=False).numpy().flatten())
print(np.sign(PRED3))
print(np.sum(PRED3 == TY3.flatten()) / len(PRED3))

"""[result]: We can get a precision of 53.68% on test set."""