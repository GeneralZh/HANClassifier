import sys

import numpy as np

import tensorflow as tf
from tensorflow.contrib.rnn import GRUCell
from tensorflow.python.ops.rnn import dynamic_rnn, bidirectional_dynamic_rnn

from keras.datasets import imdb, reuters

from utils import *

def attention(inputs, ATTENTION_SIZE):
    # Concatenate Bi-RNN outputs.
    inputs = tf.concat(inputs, 2)

    inputs_shape = inputs.shape
    sequence_length = inputs_shape[1].value
    HIDDEN_SIZE = inputs_shape[2].value # Usually HIDDEN_SIZE * 2, because of bi-directional

    # Attention mechanism
    W_w = tf.Variable(tf.truncated_normal([HIDDEN_SIZE, ATTENTION_SIZE], stddev=0.1))
    b_w = tf.Variable(tf.truncated_normal([ATTENTION_SIZE], stddev=0.1))
    u_w = tf.Variable(tf.truncated_normal([ATTENTION_SIZE], stddev=0.1))

    v = tf.tanh(tf.matmul(tf.reshape(inputs, [-1, HIDDEN_SIZE]), W_w) + b_w)
    v_u = tf.matmul(v, tf.reshape(u_w, [-1, 1]))
    exps = tf.reshape(tf.exp(v_u), [-1, sequence_length])
    alphas = exps / tf.reshape(tf.reduce_sum(exps, 1), [-1, 1])

    # Weigh by attention vector
    output = tf.reduce_sum(inputs * tf.reshape(alphas, [-1, sequence_length, 1]), 1)

    return output

# Load Data
(x_train, y_train), (x_test, y_test) = reuters.load_data(path="reuters.npz")

# Pre-process
# MAX_LEN = max(len(max(x_train, key=len)), len(max(x_test, key=len)))
MAX_LEN = 10
N_CLASSES = 46
VOCAB_SIZE = get_vocabulary_size(x_train)
ATTENTION_SIZE = 50
HIDDEN_SIZE = 100

x_train = pad_sequences(x_train, MAX_LEN)
x_test = pad_sequences(x_test, MAX_LEN)
y_train = np.array([one_hot(y, N_CLASSES) for y in y_train], dtype='f')
y_test  = np.array([one_hot(y, N_CLASSES) for y in y_test], dtype='f')

x = tf.placeholder(tf.int32, [None, MAX_LEN])
y_ = tf.placeholder(tf.float32, [None, N_CLASSES])

# Embedding Layer
# TODO: Switch to pre-trained embeddings
embeddings_var = tf.Variable(tf.random_uniform([VOCAB_SIZE, 200], -1.0, 1.0), trainable=True)
batch_embedded = tf.nn.embedding_lookup(embeddings_var, x)

# ----- With Attention -----
if len(sys.argv) > 1 and sys.argv[1] == '--attention':
    # Bi-Directional GRU Cells
    outputs, states = bidirectional_dynamic_rnn(
        GRUCell(HIDDEN_SIZE),
        GRUCell(HIDDEN_SIZE),
        inputs=batch_embedded, dtype=tf.float32
    )

    # + Attention Layer +
    attention_out = attention(outputs, ATTENTION_SIZE)

    W = tf.Variable(tf.zeros([attention_out.get_shape()[1].value, N_CLASSES]))
    b = tf.Variable(tf.zeros([N_CLASSES]))

    y = tf.nn.softmax(tf.matmul(attention_out, W) + b)

# ----- Without Attention -----
else:
    outputs, states = dynamic_rnn(GRUCell(HIDDEN_SIZE), inputs=batch_embedded, dtype=tf.float32)
    out_shape = outputs.get_shape().as_list()

    W = tf.Variable(tf.zeros([out_shape[2] * out_shape[1], N_CLASSES]))
    b = tf.Variable(tf.zeros([N_CLASSES]))

    y = tf.nn.softmax(tf.matmul(tf.reshape(outputs, [-1, out_shape[2] * out_shape[1]]), W) + b)

# loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(labels=y_, logits=y))
loss = tf.reduce_mean(-tf.reduce_sum(y_ * tf.log(y), reduction_indices=[1]))
trainer = tf.train.AdamOptimizer(1e-4).minimize(loss)

correct_answer = tf.equal(tf.argmax(y, 1), tf.argmax(y_, 1))
accuracy = tf.reduce_mean(tf.cast(correct_answer, tf.float32))

with tf.Session() as sess:
    sess.run(tf.global_variables_initializer())

    # print sess.run(outputs.get_shape(), feed_dict={x: x_train})
    print 'Training...\n'

    total_size = len(x_train)
    batch_size = 100

    for epoch in range(5):
        print '=== Epoch %d ===\n' % epoch

        n_batches = total_size / batch_size

        for i_batch in range(n_batches):
            start_index = i_batch * batch_size
            end_index = start_index + batch_size

            x_batch, y_batch = x_train[start_index: end_index], y_train[start_index: end_index]

            if i_batch % 10 == 0:
                print 'Batch %d | Loss: %f' % (i_batch, sess.run(loss, feed_dict={x: x_batch, y_: y_batch}))

            sess.run(trainer, feed_dict={x: x_batch, y_: y_batch})

    print
    print 'Loss: ', sess.run(loss, feed_dict={x: x_test, y_: y_test})
    print 'Accuracy: ', sess.run(accuracy, feed_dict={x: x_test, y_: y_test})
