#!/usr/bin/python3

from six.moves import cPickle
import cv2
import fnmatch
import numpy as np
import os
import pandas as pd
import sys
import math

# Turn saving renders feature on/off
SAVE_RENDERS = not False

# Create intermediate images in separate folders for debugger.
# mask, cut_hand, delete_object, render
SAVE_IMAGE_FOR_DEBUGGER = not False

# Extracting hands from images and using that new dataset.
# Simple dataset is correct, I am verifying the original.
EXTRACTING_HANDS = not False

# Turn rotate image on/off
ROTATE_IMAGE = False

# Usar el descriptor basado en gradiente
IMAGE_GRADIENTS = False


# Show the images
def writeImage(path, image):
    if SAVE_IMAGE_FOR_DEBUGGER:
        cv2.imwrite(
            os.path.join(__location__, "dataset_sample", path, img_file),
            image
        )


# XXX: Combertimos en gris y normalizamos el historama de colores
def histogramsEqualization(img):
    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(img)


# Delete small objects from the images
def deleteObjects(image):
    # We look for contours
    (_, contours, _) = cv2.findContours(image, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)

    # In case of having more than 10000 contours, sub figures
    if len(contours) > 10000:
        # Create a kernel of '1' of 10x10, used as an eraser
        # kernel = np.ones((10, 10), np.uint8)
        kernel = np.ones((30, 30), np.uint8)
        # Transformation is applied to eliminate particles
        img = cv2.morphologyEx(image, cv2.MORPH_OPEN, kernel)

        # Get a new mask with fewer objects
        _, thresh = cv2.threshold(img, 75, 255, cv2.THRESH_OTSU)

        # Detect the edges with Canny and then we look for contours
        img = cv2.Canny(thresh, 100, 400)  # 50,150  ; 100,500
        (_, contours, _) = cv2.findContours(img, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)

        image = cv2.bitwise_and(image, image, mask=thresh)

    if len(contours) > 1:
        # He reported it because it can take a long time if the number is large
        if len(contours) > 3000:
            updateProgress(progress[0], progress[1], total_file,
                           img_file + " Img with " + str(len(contours)) + " contours")

        # I guess the largest object is the hand or the only object in the image
        # From the contour list search the index of the largest object
        largest_object_index = 0
        for i, cnt in enumerate(contours):
            if cv2.contourArea(contours[largest_object_index]) < cv2.contourArea(cnt):
                largest_object_index = i

        # Paint the objects smaller than 30% of the large, limit: (0.2, 0.5]
        lenOfObjetoGrande = cv2.contourArea(contours[largest_object_index]) * 0.3
        for i, cnt in enumerate(contours):
            if cv2.contourArea(cnt) < lenOfObjetoGrande:
                cv2.drawContours(image, contours, i, (0, 0, 0), -1)

        # Paint the largest object in white
        cv2.drawContours(
            image,  # image,
            contours,  # objects
            largest_object_index,  # índice de objeto (-1, todos)
            (255, 255, 255),  # color
            -1  # tamaño del borde (-1, pintar adentro)
        )
        # Add a border to the largest object in white
        cv2.drawContours(
            image,  # image,
            contours,  # objects
            largest_object_index,  # índice de objeto (-1, todos)
            (255, 255, 255),  # color
            10  # tamaño del borde (-1, pintar adentro)
        )

    writeImage("delete_object", np.hstack([  # ===========================
        # img,
        # thresh,
        image
    ]))  # show the images ===============================================

    return image, len(contours)


# Cut the hand of the image
# Look for the largest objects and create a mask, with that new mask
# is applied to the original and cut out.
def cutHand(image):
    image_copy = image.copy()

    # applying gaussian blur
    blurred = cv2.GaussianBlur(image, (47, 47), 0)

    # thresholdin: Otsu's Binarization method
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_OTSU)
    thresh = cv2.GaussianBlur(thresh, (41, 41), 0)

    writeImage("cut_hand", np.hstack([  # ================================
        # img,
        thresh,
        image
    ]))  # show the images ===============================================

    (image, contours, _) = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_NONE)

    # I guess the largest object is the hand or the only object in the image.
    largest_object_index = 0
    for i, cnt in enumerate(contours):
        if cv2.contourArea(contours[largest_object_index]) < cv2.contourArea(cnt):
            largest_object_index = i

    # create bounding rectangle around the contour (can skip below two lines)
    [x, y, w, h] = cv2.boundingRect(contours[largest_object_index])
    # Black background below the largest object
    cv2.rectangle(image, (x, y), (x+w, y+h), (0, 0, 0), -1)

    cv2.drawContours(
        image,  # image,
        contours,  # objects
        largest_object_index,  # índice de objeto (-1, todos)
        (255, 255, 255),  # color
        -1  # tamaño del borde (-1, pintar adentro)
    )

    # Joining broken parts of an object.
    kernel = np.ones((1, 1), np.uint8)
    image_mask = cv2.erode(image, kernel, iterations=2)
    kernel = np.ones((5, 5), np.uint8)
    image_mask = cv2.dilate(image_mask, kernel, iterations=2)

    # Clean black spaces within the target
    kernel = np.ones((75, 75), np.uint8)
    image_mask = cv2.morphologyEx(image_mask, cv2.MORPH_CLOSE, kernel)

    # Trim that object of mask and image
    mask = image_mask[y:y+h, x:x+w]
    image_cut = image_copy[y:y+h, x:x+w]

    # Evaluate the center of the mask in search of black block
    # In case the image is black, return the original
    # Get a square from the center of the mask
    # print('\n', cv2.mean(image_cut)[0] * 0.392)
    if (cv2.mean(image_cut)[0] * 0.392 > 10.0 or True):
        # Trim that object
        return cv2.bitwise_and(image_cut, image_cut, mask=mask)
    else:
        print("-------------IMAGEN NEGRA----------------\n")
        return image_copy


# Create a mask for the hand.
# I guess the biggest objecUsar el descriptor basado en gradientet is the hand
def createMask(image, sensitivity=0.25):
    mask = cv2.inRange(
        image,
        np.array(int(sensitivity * 255)),  # lower color
        np.array(255)  # upper color
    )

    # Clean black spaces within the target
    kernel = np.ones((20, 20), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # Blur the image to avoid erasing borders
    mask = cv2.GaussianBlur(mask, (25, 25), 0)

    # Joining broken parts of an object.
    # kernel = np.ones((3, 3), np.uint8)
    # mask = cv2.erode(mask, kernel, iterations=2)

    # Detect the edges with Canny
    # img = cv2.Canny(image, 100, 100)  # 50,150  ; 100,500

    # _, thresh = cv2.threshold(image, 80, 255, cv2.THRESH_OTSU)

    # Delete other figures
    mask, contours = deleteObjects(mask)

    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=2)

    # Blur the image to avoid erasing borders
    mask = cv2.GaussianBlur(mask, (25, 25), 0)

    writeImage("mask", np.hstack([  # ====================================
        # img,
        mask,
        image
    ]))  # show the images ===============================================

    return mask


# Create and apply a mask to the image, then cut out the large objects and
# if the image is too white again, apply the procedure.
# In each iteration the intensity increases.
def extractingHands(image, sensitivity=0.20):
    # Create mask to highlight your hand
    mask = createMask(image, sensitivity)
    # Aplly mask
    img_mask = cv2.bitwise_and(image, image, mask=mask)
    # Trim the hand of the image
    img = cutHand(img_mask)

    avg_white = cv2.mean(img)[0]  # 0 to 255
    # print('\n value', avg_white, 'proce', avg_white *
    #      0.392, 'sen', sensitivity, '+', avg_white * 0.001)
    if (avg_white * 0.392 > 60.0):
        img = extractingHands(image, sensitivity + avg_white * 0.001)

    return img


def rotateImage(imageToRotate):
    edges = cv2.Canny(imageToRotate, 50, 150, apertureSize=3)
    # Obtener una línea de la imágen
    lines = cv2.HoughLines(edges, 1, np.pi/180, 200)
    for rho, theta in lines[0]:
        a = np.cos(theta)
        b = np.sin(theta)
        x0 = a*rho
        y0 = b*rho
        x1 = int(x0 + 1000*(-b))
        y1 = int(y0 + 1000*(a))
        x2 = int(x0 - 1000*(-b))
        y2 = int(y0 - 1000*(a))
        cv2.line(imageToRotate, (x1, y1), (x2, y2), (0, 0, 255), 2)
        angle = math.atan2(y1 - y2, x1 - x2)
        angleDegree = (angle*180)/math.pi

    if (angleDegree < 0):
        angleDegree = angleDegree + 360
    # print('\n', angleDegree)

    if (angleDegree >= 0 and angleDegree < 45):
        angleToSubtract = 0
    elif (angleDegree >= 45 and angleDegree < 135):
        angleToSubtract = 90
    elif (angleDegree >= 135 and angleDegree < 225):
        angleToSubtract = 180
    elif (angleDegree >= 225 and angleDegree < 315):
        angleToSubtract = 270
    else:
        angleToSubtract = 0
    # print(angleToSubtract)
    angleToRotate = angleDegree - angleToSubtract
    # print(angleToRotate)
    num_rows, num_cols = imageToRotate.shape[:2]
    rotation_matrix = cv2.getRotationMatrix2D((num_cols/2, num_rows/2), angleToRotate, 1)
    img_rotation = cv2.warpAffine(img, rotation_matrix, (num_cols, num_rows))
    return img_rotation


# Show a progress bar
def updateProgress(progress, tick='', total='', status='Loading...'):
    lineLength = 80
    barLength = 23
    if isinstance(progress, int):
        progress = float(progress)
    if progress < 0:
        progress = 0
        status = "Waiting...\r"
    if progress >= 1:
        progress = 1
        status = "Completed loading data\r\n"
    block = int(round(barLength * progress))
    line = str("\rImage: {0}/{1} [{2}] {3}% {4}").format(
        tick,
        total,
        str(("#" * block)) + str("." * (barLength - block)),
        round(progress * 100, 1),
        status
    )
    emptyBlock = lineLength - len(line)
    emptyBlock = " "*emptyBlock if emptyBlock > 0 else ""
    sys.stdout.write(line + emptyBlock)
    sys.stdout.flush()


# For this problem the validation and test data provided by the concerned authority did not have labels, so the training data was split into train, test and validation sets
__location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))
# __location__ = os.path.realpath(os.path.join(
#    os.getcwd(), os.path.dirname("C:/Pablo/Git/deeplearningforcomputervision/")))

train_dir = os.path.join(__location__, 'dataset_sample')

X_train = []
y_age = []
y_gender = []

df = pd.read_csv(os.path.join(train_dir, 'boneage-training-dataset.csv'))
a = df.values
m = a.shape[0]


# Create the directories to save the images
if SAVE_IMAGE_FOR_DEBUGGER:
    for folder in ['mask', 'cut_hand', 'delete_object', 'render']:
        if not os.path.exists(os.path.join(__location__, "dataset_sample", folder)):
            os.makedirs(os.path.join(__location__, "dataset_sample", folder))
if SAVE_RENDERS:
    if not os.path.exists(os.path.join(__location__, "dataset_sample", "render")):
        os.makedirs(os.path.join(__location__, "dataset_sample", "render"))

print('Loading data set...')
# file names on train_dir
files = os.listdir(train_dir)
# filter image files
files = [f for f in files if fnmatch.fnmatch(f, '*.png')]
total_file = len(files)

for i in range(total_file):
    img_file = files[i]

    # Update the progress bar
    progress = float(i / total_file), (i + 1)
    updateProgress(progress[0], progress[1], total_file, img_file)

    y_age.append(df.boneage[df.id == int(img_file[:-4])].tolist()[0])
    a = df.male[df.id == int(img_file[:-4])].tolist()[0]
    if a:
        y_gender.append(1)
    else:
        y_gender.append(0)

    # Read a image
    img_path = os.path.join(train_dir, img_file)
    img = cv2.imread(img_path)

    img = histogramsEqualization(img)

    if EXTRACTING_HANDS:
        img = extractingHands(img)

    if ROTATE_IMAGE:
        # Rotate hands
        img = rotateImage(img)

    # Image Gradients
    if IMAGE_GRADIENTS:
        laplacian = cv2.Laplacian(img, cv2.CV_64F)
        sobelx = cv2.Sobel(img, cv2.CV_64F, 1, 0, ksize=5)
        sobely = cv2.Sobel(img, cv2.CV_64F, 0, 1, ksize=5)
        img = cv2.bitwise_or(sobelx, sobely)

        # sobelx8u = cv2.Sobel(img, cv2.CV_8U, 1, 0, ksize=5)
        # sobelx64f = cv2.Sobel(img, cv2.CV_64F, 1, 0, ksize=5)
        # abs_sobel64f = np.absolute(sobelx64f)
        # sobel_8u = np.uint8(abs_sobel64f)

    # ====================== show the images ================================
    if SAVE_IMAGE_FOR_DEBUGGER or SAVE_RENDERS:
        cv2.imwrite(
            os.path.join(__location__, "dataset_sample", "render", img_file),
            np.hstack([
                img
            ])
        )
    # =======================================================================

    # Resize the images
    img = cv2.resize(img, (224, 224))

    x = np.asarray(img, dtype=np.uint8)
    X_train.append(x)

updateProgress(1, total_file, total_file, img_file)

print('\nSaving data...')
# Save data
train_pkl = open('data.pkl', 'wb')
cPickle.dump(X_train, train_pkl, protocol=cPickle.HIGHEST_PROTOCOL)
train_pkl.close()

train_age_pkl = open('data_age.pkl', 'wb')
cPickle.dump(y_age, train_age_pkl, protocol=cPickle.HIGHEST_PROTOCOL)
train_age_pkl.close()

train_gender_pkl = open('data_gender.pkl', 'wb')
cPickle.dump(y_gender, train_gender_pkl, protocol=cPickle.HIGHEST_PROTOCOL)
train_gender_pkl.close()
print('\nCompleted saved data')
