from keras.datasets import mnist
from keras import backend as K
from keras.layers import Input, Dense, Conv2D, MaxPooling2D, UpSampling2D
from keras.models import Model
import h5py
import matplotlib.pyplot as plt
import numpy as np
import os

__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

EPOCHS = 10
BATCH_SIZE = 12


def readFile(gender, dataset, X_img=None, x_gender=None, y_age=None):
    print("Reading", gender, dataset, "data...")
    file_name = gender + "-" + dataset + "-" + ".hdf5"
    with h5py.File(
        os.path.join(__location__, "packaging-dataset", "for_autoencoder", file_name),
        "r+",
    ) as f:
        f_img = f["img"][()]
        f_gender = f["gender"][()]
        f_age = f["age"][()]
        f.close()
    if X_img is None:
        X_img = f_img
    else:
        X_img = np.concatenate((X_img, f_img), axis=0)

    if x_gender is None:
        x_gender = f_gender
    else:
        x_gender = np.concatenate((x_gender, f_gender), axis=0)

    if y_age is None:
        y_age = f_age
    else:
        y_age = np.concatenate((y_age, f_age), axis=0)

    return X_img, x_gender, y_age


########################### Auto encoder ############################
def autoencoder(input_img):
    # output: (224x224)/24.5 input: 224x224
    x = Conv2D(2048, kernel_size=(3, 3), padding="same", activation="relu")(input_img)
    x = MaxPooling2D(pool_size=(2, 2), padding="same")(x)  # 112x112x2048
    # output: 2048x2 input: 56x56x4096
    x = Conv2D(4096, kernel_size=(3, 3), activation="relu", padding="same")(x)
    x = MaxPooling2D(pool_size=(2, 2), padding="same")(x)  # 28x28x4096
    # output: 4096x2 input: 28x28x8192
    encoded = Conv2D(8192, kernel_size=(3, 3), activation="relu", padding="same")(x)

    # output: 4096x2 input: 28x28x8192
    x = Conv2D(8192, kernel_size=(3, 3), activation="relu", padding="same")(encoded)
    x = UpSampling2D(size=(2, 2))(x)  # 56x56x8192
    # output: 2048x2 input: 56x56x4096
    x = Conv2D(4096, kernel_size=(3, 3), activation="relu", padding="same")(x)
    x = UpSampling2D(size=(2, 2))(x)  # 112x112x4096
    # output: 224x224 input: 224x224x1
    decoded = Conv2D(3, kernel_size=(3, 3), padding="same", activation="sigmoid")(x)
    return decoded


####################################################################
# (x_train, _), (x_test, _) = mnist.load_data()
# x_train = x_train.astype("float32") / 255.
# x_test = x_test.astype("float32") / 255.
# x_train = np.reshape(x_train, (len(x_train), 28, 28, 1))
# x_test = np.reshape(x_test, (len(x_test), 28, 28, 1))
####################################################################

genderType = "male"
genderType = "female"
x_test, _, _ = readFile(genderType, "testing")
x_train, _, _ = readFile(genderType, "validation")

input_img = Input(shape=x_train.shape[1:])
# input_img = Input(shape=(224, 224, 1))

autoencoder = Model(input_img, autoencoder(input_img))
print(autoencoder.summary())
autoencoder.compile(optimizer="adadelta", loss="binary_crossentropy")
# autoencoder.compile(loss='mean_squared_error', optimizer = RMSprop())

autoencoder_train = autoencoder.fit(
    x_train,
    x_train,
    epochs=EPOCHS,
    batch_size=BATCH_SIZE,
    shuffle=True,
    validation_data=(x_test, x_test),
)

loss = autoencoder_train.history["loss"]
val_loss = autoencoder_train.history["val_loss"]
epochs = range(epochs)
plt.figure()
plt.plot(epochs, loss, label="Training loss")
plt.plot(epochs, val_loss, label="Validation loss")
plt.title("Training and validation loss")
plt.legend()
plt.show()

decoded_imgs = autoencoder.predict(x_test)

n = 10
plt.figure(figsize=(20, 4))
for i in range(1, n + 1):
    # display original
    ax = plt.subplot(2, n, i)
    plt.imshow(x_test[i].reshape(28, 28))
    plt.gray()
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)

    # display reconstruction
    ax = plt.subplot(2, n, i + n)
    plt.imshow(decoded_imgs[i].reshape(28, 28))
    plt.gray()
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)
plt.show()
