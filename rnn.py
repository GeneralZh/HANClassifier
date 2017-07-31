import random

import numpy as np

import tensorflow as tf
from tensorflow.contrib.rnn import GRUCell
from tensorflow.python.ops.rnn import dynamic_rnn
from tensorflow.python.ops.rnn import bidirectional_dynamic_rnn as bi_rnn

from keras.datasets import imdb, reuters

def pad_sequences(sequences, padded_len):
    return np.array([zero_pad(sequence, padded_len) for sequence in sequences])

def zero_pad(arr, padded_len):
    if padded_len < len(arr):
        return np.array(arr[:padded_len])

    return np.array(arr + ([0] * (padded_len - len(arr))), dtype='f')

def gen_batch(x, y, n_seq):
    indices = random.sample(range(len(x)), n_seq)
    return x[indices], y[indices]

def one_hot(n, dim):
    vec = [0] * dim
    vec[n] = 1

    return np.array(vec, dtype='f')

def get_vocabulary_size(X):
    return max([max(x) for x in X]) + 1

def attention(inputs, attention_size):
    # Concatenate Bi-RNN outputs.
    inputs = tf.concat(inputs, 2)

    inputs_shape = inputs.shape
    sequence_length = inputs_shape[1].value
    hidden_size = inputs_shape[2].value # Usually hidden_size * 2, because of bi-directional

    # Attention mechanism
    W_w = tf.Variable(tf.truncated_normal([hidden_size, attention_size], stddev=0.1))
    b_w = tf.Variable(tf.truncated_normal([attention_size], stddev=0.1))
    u_w = tf.Variable(tf.truncated_normal([attention_size], stddev=0.1))

    v = tf.tanh(tf.matmul(tf.reshape(inputs, [-1, hidden_size]), W_w) + b_w)
    v_u = tf.matmul(v, tf.reshape(u_w, [-1, 1]))
    exps = tf.reshape(tf.exp(v_u), [-1, sequence_length])
    alphas = exps / tf.reshape(tf.reduce_sum(exps, 1), [-1, 1])

    # Weigh by attention vector
    output = tf.reduce_sum(inputs * tf.reshape(alphas, [-1, sequence_length, 1]), 1)

    return output

# Load Data
(x_train, y_train), (x_test, y_test) = reuters.load_data(path="reuters.npz")

# Pre-process
MAX_LEN = max(len(max(x_train, key=len)), len(max(x_test, key=len)))
# MAX_LEN = 10
N_CLASSES = 46
vocabulary_size = get_vocabulary_size(x_train)
attention_size = 50
hidden_size = 100

x_train = pad_sequences(x_train, MAX_LEN)
x_test = pad_sequences(x_test, MAX_LEN)
y_train = np.array([one_hot(y, N_CLASSES) for y in y_train], dtype='f')
y_test  = np.array([one_hot(y, N_CLASSES) for y in y_test], dtype='f')

x = tf.placeholder(tf.int32, [None, MAX_LEN])
y_ = tf.placeholder(tf.float32, [None, N_CLASSES])

# Embedding Layer
# TODO: Switch to pre-trained embeddings
embeddings_var = tf.Variable(tf.random_uniform([vocabulary_size, 200], -1.0, 1.0), trainable=True)
batch_embedded = tf.nn.embedding_lookup(embeddings_var, x)

rnn_cell = GRUCell(hidden_size)

# ----- Without Attention -----

# outputs, states = dynamic_rnn(rnn_cell, inputs=batch_embedded, dtype=tf.float32)
# W = tf.Variable(tf.zeros([outputs.get_shape()[2].value * outputs.get_shape()[1].value, N_CLASSES]))
# b = tf.Variable(tf.zeros([N_CLASSES]))
#
# y = tf.matmul(tf.reshape(outputs, [-1, outputs.get_shape()[2].value * outputs.get_shape()[1].value]), W) + b

# ----- With Attention -----

# Bi-Directional GRU Cells
outputs, states = bi_rnn(GRUCell(hidden_size), GRUCell(hidden_size), inputs=batch_embedded, dtype=tf.float32)

# + Attention Layer +
attention_out = attention(outputs, attention_size)

W = tf.Variable(tf.zeros([attention_out.get_shape()[1].value, N_CLASSES]))
b = tf.Variable(tf.zeros([N_CLASSES]))

y = tf.nn.softmax(tf.matmul(attention_out, W) + b)

# loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(labels=y_, logits=y))
loss = tf.reduce_mean(-tf.reduce_sum(y_ * tf.log(y), reduction_indices=[1]))
trainer = tf.train.AdamOptimizer(1e-4).minimize(loss)

correct_answer = tf.equal(tf.argmax(y, 1), tf.argmax(y_, 1))
accuracy = tf.reduce_mean(tf.cast(correct_answer, tf.float32))

with tf.Session() as sess:
    sess.run(tf.global_variables_initializer())

    # print sess.run(outputs.get_shape(), feed_dict={x: x_train})
    print 'Training...\n'

    for i in range(1000):
        x_batch, y_batch = gen_batch(x_train, y_train, 100)

        if i % 100 == 0:
            print '%d Loss: %f' % (i, sess.run(loss, feed_dict={x: x_batch, y_: y_batch}))

        sess.run(trainer, feed_dict={x: x_batch, y_: y_batch})

    print
    print 'Loss: ', sess.run(loss, feed_dict={x: x_test, y_: y_test})
    print 'Accuracy: ', sess.run(accuracy, feed_dict={x: x_test, y_: y_test})
