# coding: utf-8

import numpy as np
from sklearn import svm
#from sklearn import preprocessing
from sklearn.hmm import GaussianHMM
from sklearn.decomposition import PCA
from sklearn.metrics import accuracy_score
# import csv
import pickle

# 定数の設定
N_LABEL = 9

# データの読み込み
lefthand_mocap_train = pickle.load(open("lefthand_mocap_train", "rb"))
lefthand_mocap_test = pickle.load(open("lefthand_mocap_test", "rb"))
labels_train = pickle.load(open("../labels_train.dump", "rb"))
labels_test = pickle.load(open("../labels_test.dump", "rb"))

# 学習データ、テストデータそれぞれについてPCAの入力(複数フレーム)をつくる
## 学習データのPCA入力
len_anglevec = lefthand_mocap_train.shape[1]
window_length = 3
features_pca_train = np.empty((len(lefthand_mocap_train)-(window_length-1), len_anglevec*window_length))
for i in xrange(window_length-1, len(lefthand_mocap_train)):
    feature_reshaped = np.reshape(lefthand_mocap_train[i-(window_length-1):i+1, :], (1, len_anglevec*window_length))
    features_pca_train[i-(window_length-1), :] = feature_reshaped
## テストデータのPCA入力
features_pca_test = np.empty((len(lefthand_mocap_test)-(window_length-1), len_anglevec*window_length))
for i in xrange(window_length-1, len(lefthand_mocap_test)):
    feature_reshaped = np.reshape(lefthand_mocap_test[i-(window_length-1):i+1, :], (1, len_anglevec*window_length))
    features_pca_test[i-(window_length-1), :] = feature_reshaped

# 線形PCAで学習データ、テストデータのmocapを次元圧縮
pca = PCA(n_components=5) #n_components: 圧縮する次元数
## 線形PCAの学習と変換
lefthand_pca_train = pca.fit_transform(features_pca_train)
lefthand_pca_test = pca.fit_transform(features_pca_test)

# ラベル列の長さをそろえる
lenSeq = 30
labels_pca_train = labels_train[lenSeq+window_length-2:]
labels_pca_test = labels_test[lenSeq+window_length-2:]

# 次元削減したMocap系列をlenSeqの長さに分割
pcaSeq_train = [[], [], [], [], [], [], [], [], []] #もっと綺麗に書く
for t in range(lefthand_pca_train.shape[0]-(lenSeq-1)):
    seq = lefthand_pca_train[t:t+lenSeq, :]
    pcaSeq_train[labels_pca_train[t]].append(seq)

pcaSeq_test = [] #もっと綺麗に書く
for t in range(lefthand_pca_test.shape[0]-(lenSeq-1)):
    seq = lefthand_pca_test[t:t+lenSeq, :]
    pcaSeq_test.append(seq)
# print len(pcaSeq_test)

#各行動ごとにGaussianHMMをつくりリストに格納し学習
print "training HMM..."
list_ghmm = []
for i in range(N_LABEL):
	list_ghmm.append(GaussianHMM(n_components=3))
	list_ghmm[i].fit(pcaSeq_train[i])

lik_train = np.empty((lefthand_pca_train.shape[0]-(lenSeq-1), N_LABEL)) #学習データ尤度行列
lik_test = np.empty((len(pcaSeq_test), N_LABEL)) #テストデータ尤度行列
# print lik_test.shape, lik_train.shape

# 学習後のHMMにより尤度計算
print "computing likelihood..."
for i in range(N_LABEL): # どのHMMを使うか
	#学習データ
	countT = 0
	labels_lik_train = [] # 学習用尤度列ラベル
	for ii in range(N_LABEL): # 学習用の各系列の最後のラベルがどれか
		for t_train in range(len(pcaSeq_train[ii])):
			lik_train[countT, i] = list_ghmm[i].score(pcaSeq_train[ii][t_train]) ##←おかしい??
			labels_lik_train.append(ii)
			countT += 1
	#テストデータ
	for t_test in range(len(pcaSeq_test)):
		lik_test[t_test, i] = list_ghmm[i].score(pcaSeq_test[t_test])


# SVMに入力する特徴量を生成
# lenSeqはHMMの入力と共通になっている
features_train = np.empty((lik_train.shape[0]-(lenSeq-1), N_LABEL*lenSeq))

for i in xrange(lenSeq-1, lik_train.shape[0]):
    likelihood_reshaped = np.reshape(lik_train[i-(lenSeq-1):i+1, :], (1, N_LABEL*lenSeq))
#     print likelihood_reshaped.shape, features_train.shape
    features_train[i-(lenSeq-1), :] = likelihood_reshaped

#featuresの長さに合わせるためにラベル列の前9個を消去
labels_svm_train = labels_lik_train[lenSeq-1:]

#テスト用
features_test = np.empty((lik_test.shape[0]-(lenSeq-1), N_LABEL*lenSeq))

for i in xrange(lenSeq-1, lik_test.shape[0]):
    likelihood_reshaped = np.reshape(lik_test[i-(lenSeq-1):i+1, :], (1, N_LABEL*lenSeq))
#     print likelihood_reshaped.shape, features_train.shape
    features_test[i-(lenSeq-1), :] = likelihood_reshaped

#featuresの長さに合わせるためにラベル列の前を消去
labels_svm_test = labels_pca_test[lenSeq-1:]


# SVMによる学習、テスト
print "training SVM..."
svm_lik = svm.SVC()
svm_lik.fit(features_train, labels_svm_train)

labels_predicted = svm_lik.predict(features_test)
accuracy = accuracy_score(labels_predicted, labels_svm_test)

print "accuracy=%f" % accuracy
