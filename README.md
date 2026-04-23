# 79517665770
Полное руководство: Обучение YOLO и интеграция с дроном Clover

Это пошаговое руководство поможет вам обучить нейросеть YOLOv8 для распознавания трёх объектов (например, grebnik, brakonier, tyrist) с использованием симулятора Gazebo + Clover и интегрировать модель в полётный код на реальном дроне или в симуляции.
Содержание

    Требования

    Настройка окружения

    Сбор данных

        Запись видео с дрона

        Извлечение кадров для обучения

    Разметка датасета

        Установка LabelImg

        Структура папок

        Процесс разметки

        Создание dataset.yaml

    Обучение модели YOLO

    Тестирование обученной модели

    Интеграция с полётным кодом Clover

        Подготовка окружения на дроне

        Полный скрипт полётной миссии с детекцией

    Часто задаваемые вопросы (FAQ)

    Заключение

Требования

    Для обучения:

        Компьютер с Python 3.8+ (можно использовать тот же, где запущен Gazebo + Clover)

        Установленный пакет ultralytics (установка описана ниже)

        Размеченные изображения трёх объектов

    Для полёта:

        Дрон Clover (реальный или в симуляторе Gazebo)

        ROS Melodic/Noetic

        Пакет clover

        OpenCV, cv_bridge, tf2 и др.

Настройка окружения
Установка Ultralytics YOLO
bash

pip install ultralytics

Примечание: Если вы работаете на виртуальной машине Clover, возможно, потребуется обновить pip:
pip install --upgrade pip
Проверка установки
bash

yolo --version

Если команда не найдена, попробуйте перезапустить терминал или выполнить python3 -m ultralytics.
Сбор данных
Запись видео с дрона

Для обучения нейросети вам понадобится видеозапись с камеры дрона, на которой присутствуют целевые объекты с разных ракурсов. В симуляторе можно разместить объекты на поле и выполнить облёт.

Пример скрипта для записи видео во время полёта (на основе вашего кода):
python

import rospy
import cv2
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
from clover import srv
import math

# ... (код инициализации, navigate_wait, start_video_recording)

# В image_callback записывайте кадры в VideoWriter

Извлечение кадров для обучения

После получения видеофайла (flight_video.avi) извлеките из него кадры с интервалом, чтобы избежать сильной избыточности. Пример скрипта:
python

import cv2
import os

video_path = 'flight_video.avi'
output_dir = 'dataset_frames'
os.makedirs(output_dir, exist_ok=True)

cap = cv2.VideoCapture(video_path)
frame_count = 0
saved = 0
interval = 30  # сохранять каждый 30-й кадр

while True:
    ret, frame = cap.read()
    if not ret:
        break
    if frame_count % interval == 0:
        cv2.imwrite(os.path.join(output_dir, f'frame_{saved:05d}.jpg'), frame)
        saved += 1
    frame_count += 1

cap.release()
print(f"Сохранено {saved} кадров")

Для небольшого датасета (3 класса, простой фон) может хватить 20–50 размеченных кадров.
Разметка датасета
Установка LabelImg

LabelImg — бесплатный инструмент для создания прямоугольных аннотаций в формате YOLO.
bash

pip install labelImg
labelImg

Структура папок

Создайте следующую иерархию:
text

my_dataset/
├── dataset.yaml
├── train/
│   ├── images/      # обучающие изображения (.jpg)
│   └── labels/      # аннотации YOLO (.txt)
└── val/
    ├── images/      # валидационные изображения
    └── labels/      # аннотации для валидации

Разделите имеющиеся кадры примерно 80% для train, 20% для val. Скопируйте файлы .jpg в соответствующие папки images.
Процесс разметки

    Запустите LabelImg.

    Нажмите Open Dir → выберите папку train/images.

    Нажмите Change Save Dir → выберите train/labels.

    В левой панели выберите формат YOLO.

    Для каждого изображения:

        Обведите рамкой объект.

        Введите имя класса (например, grebnik).

        Нажмите Save (или Ctrl+S).

    Повторите для папки val.

В результате для каждого .jpg появится .txt файл с координатами:
text

<class_id> <x_center> <y_center> <width> <height>

где все координаты нормализованы (от 0 до 1).
Создание dataset.yaml

В корне my_dataset создайте файл dataset.yaml:
yaml

train: /absolute/path/to/my_dataset/train/images
val: /absolute/path/to/my_dataset/val/images

nc: 3
names: ['grebnik', 'brakonier', 'tyrist']

Важно: использовать абсолютные пути! Например:
/home/clover/my_dataset/train/images
Обучение модели YOLO

Перейдите в терминал и выполните команду обучения. Рекомендуется начать с предобученной модели yolov8n.pt (nano) — она быстрее обучается и требует меньше ресурсов.
bash

yolo detect train model=yolov8n.pt \
               data=/home/clover/my_dataset/dataset.yaml \
               epochs=100 \
               imgsz=320 \
               batch=8 \
               name=clover_objects

Пояснение параметров:

    model — предобученная модель (можно также yolov8s.pt для более высокой точности).

    data — путь к вашему dataset.yaml.

    epochs — количество эпох (можно увеличить до 200–300, если данные разнообразны).

    imgsz — размер входного изображения (камера Clover обычно 320×240, поэтому 320 — хороший выбор).

    batch — размер батча (зависит от объёма памяти GPU/CPU; для CPU ставьте 4–8).

    name — имя эксперимента (результаты сохранятся в runs/detect/clover_objects/).

После завершения обучения вы увидите метрики (mAP@0.5). Лучшая модель будет сохранена в runs/detect/clover_objects/weights/best.pt.
Возможная ошибка с emoji

Если во время обучения появляются сообщения вида:
text

UnicodeEncodeError 'latin-1' codec can't encode character '\u2705'

это не критично. Можно либо игнорировать, либо временно настроить локаль:
bash

export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

Тестирование обученной модели

Проверьте работу модели на одном из изображений валидационной выборки:
bash

yolo predict model=/home/clover/runs/detect/clover_objects/weights/best.pt \
               source=/home/clover/my_dataset/val/images/любое_изображение.jpg \
               imgsz=320

Результат (изображение с нарисованными рамками) появится в runs/detect/predict/.

Скопируйте лучшую модель в удобное место:
bash

cp /home/clover/runs/detect/clover_objects/weights/best.pt /home/clover/

Интеграция с полётным кодом Clover
Подготовка окружения на дроне

Убедитесь, что на Raspberry Pi дрона (или в виртуальной среде) установлены:

    ROS, пакет clover

    OpenCV (pip install opencv-python)

    Ultralytics YOLO (pip install ultralytics)

    cv_bridge, tf2_geometry_msgs (обычно уже есть)

Перенесите файл best.pt на дрон (например, в /home/clover/).
Полный скрипт полётной миссии с детекцией

Ниже представлен готовый скрипт, который:

    Взлетает и выполняет облёт заданных точек.

    В реальном времени обрабатывает изображение с камеры, пропуская его через YOLO.

    Рисует рамки на изображении и публикует в топик ~mask.

    Вычисляет координаты объекта на карте и публикует в топик ~detected_object.

    Записывает видео полёта в файл flight_video.avi.

Создайте файл cv_mission_yolo.py:
python

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import rospy
import cv2
import numpy as np
from sensor_msgs.msg import Image, CameraInfo
from geometry_msgs.msg import PointStamped
from cv_bridge import CvBridge
from clover import long_callback, srv
import tf2_ros
import tf2_geometry_msgs
import image_geometry
import math
from std_srvs.srv import Trigger
import time
from ultralytics import YOLO

rospy.init_node('cv_mission_yolo')

# Сервисы Clover
get_telemetry = rospy.ServiceProxy('get_telemetry', srv.GetTelemetry)
navigate = rospy.ServiceProxy('navigate', srv.Navigate)
set_position = rospy.ServiceProxy('set_position', srv.SetPosition)
land = rospy.ServiceProxy('land', Trigger)

bridge = CvBridge()

# TF и модель камеры
tf_buffer = tf2_ros.Buffer()
tf_listener = tf2_ros.TransformListener(tf_buffer)
camera_model = image_geometry.PinholeCameraModel()
camera_model.fromCameraInfo(rospy.wait_for_message('main_camera/camera_info', CameraInfo))

# Публикация
mask_pub = rospy.Publisher('~mask', Image, queue_size=1)
point_pub = rospy.Publisher('~detected_object', PointStamped, queue_size=10)

# Загрузка обученной модели YOLO
MODEL_PATH = '/home/clover/best.pt'
model = YOLO(MODEL_PATH)
CONFIDENCE_THRESHOLD = 0.5

# Глобальные переменные для записи видео
video_writer = None
recording = False
screen = None

# Известные координаты объектов (опционально)
TARGET_OBJECTS = {
    'grebnik': (0.0, 0.5),
    'brakonier': (0.5, 0.0),
    'tyrist': (1.5, 0.0)
}

def navigate_wait(x=0, y=0, z=1.8, speed=0.5, frame_id='aruco_map', tolerance=0.2, auto_arm=False):
    res = navigate(x=x, y=y, z=z, speed=speed, frame_id=frame_id, auto_arm=auto_arm)
    if not res.success:
        return res
    while not rospy.is_shutdown():
        telem = get_telemetry(frame_id='navigate_target')
        if math.sqrt(telem.x**2 + telem.y**2 + telem.z**2) < tolerance:
            return res
        rospy.sleep(0.2)

def start_video_recording(output_path='flight_video.avi', fps=15.0, frame_size=(320, 240)):
    fourcc = cv2.VideoWriter_fourcc(*'MJPG')
    out = cv2.VideoWriter(output_path, fourcc, fps, frame_size)
    if not out.isOpened():
        rospy.logerr("Не удалось открыть VideoWriter!")
        return None
    return out

def pixel_to_map(u, v, camera_model, tf_buffer, target_frame='aruco_map'):
    """
    Преобразование пикселя в точку на плоскости земли (z=0).
    """
    ray = camera_model.projectPixelTo3dRay((u, v))
    ray = np.array(ray)
    ray = ray / np.linalg.norm(ray)

    try:
        transform = tf_buffer.lookup_transform(target_frame, camera_model.tf_frame, rospy.Time(0), rospy.Duration(1.0))
    except:
        return None

    cam_pos = np.array([transform.transform.translation.x,
                        transform.transform.translation.y,
                        transform.transform.translation.z])

    if abs(ray[2]) < 1e-6:
        return None
    t = -cam_pos[2] / ray[2]
    if t < 0:
        return None

    intersection = cam_pos + t * ray
    return intersection[:2]

@long_callback
def image_callback(msg):
    global screen, video_writer, recording

    img = bridge.imgmsg_to_cv2(msg, 'bgr8')
    screen = img

    # Детекция YOLO
    results = model(img, verbose=False)

    for result in results:
        boxes = result.boxes
        if boxes is not None:
            for box in boxes:
                conf = float(box.conf[0])
                if conf < CONFIDENCE_THRESHOLD:
                    continue

                cls_id = int(box.cls[0])
                class_name = model.names[cls_id]
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

                cx = (x1 + x2) // 2
                cy = (y1 + y2) // 2

                map_xy = pixel_to_map(cx, cy, camera_model, tf_buffer, 'aruco_map')
                if map_xy is not None:
                    point_msg = PointStamped()
                    point_msg.header.stamp = rospy.Time.now()
                    point_msg.header.frame_id = 'aruco_map'
                    point_msg.point.x = map_xy[0]
                    point_msg.point.y = map_xy[1]
                    point_msg.point.z = 0.0
                    point_pub.publish(point_msg)

                    rospy.loginfo(f"Обнаружен {class_name} в координатах: ({map_xy[0]:.2f}, {map_xy[1]:.2f})")

                label = f"{class_name} {conf:.2f}"
                cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(img, label, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    if recording and video_writer is not None:
        video_writer.write(img)

    if mask_pub.get_num_connections() > 0:
        mask_pub.publish(bridge.cv2_to_imgmsg(img, 'bgr8'))

image_sub = rospy.Subscriber('main_camera/image_raw', Image, image_callback, queue_size=1)

if __name__ == '__main__':
    try:
        rospy.loginfo("Ожидание первого кадра...")
        first_msg = rospy.wait_for_message('main_camera/image_raw', Image)
        first_frame = bridge.imgmsg_to_cv2(first_msg, 'bgr8')
        h, w = first_frame.shape[:2]
        rospy.loginfo(f"Разрешение камеры: {w}x{h}")

        video_writer = start_video_recording(
            output_path='flight_video.avi',
            fps=15.0,
            frame_size=(w, h)
        )
        if video_writer is not None:
            recording = True
            rospy.loginfo("Запись видео начата")

        # Взлёт
        navigate_wait(x=0, y=0, z=1.6, frame_id='body', auto_arm=True)

        # Облёт точек (можно заменить на автоматический поиск)
        points = [
            (0.0, 0.5, 1.8),   # над grebnik
            (0.5, 0.0, 1.8),   # над brakonier
            (1.5, 0.0, 1.8)    # над tyrist
        ]

        for x, y, z in points:
            navigate_wait(x=x, y=y, z=z, frame_id='aruco_map')
            rospy.sleep(2)  # время для детекции

        navigate_wait(x=0, y=0, z=1.5)
        land()

    finally:
        recording = False
        if video_writer is not None:
            video_writer.release()
            rospy.loginfo("Видео сохранено")
        rospy.spin()

Запуск полётной миссии
bash

python3 cv_mission_yolo.py

Во время полёта можно наблюдать изображение с аннотациями в топике /cv_mission_yolo/mask (например, через rqt_image_view).
Часто задаваемые вопросы (FAQ)
1. Как изменить имена классов после обучения?

Если вы уже обучили модель с классами axe, mushroom, backpack, но хотите переименовать их, недостаточно просто изменить dataset.yaml. Необходимо:

    Переименовать классы в dataset.yaml (например, names: ['grebnik', 'brakonier', 'tyrist']).

    Убедиться, что в файлах разметки (labels/*.txt) ID соответствуют новому порядку.

    Удалить старые файлы кэша: rm -f my_dataset/train/labels.cache my_dataset/val/labels.cache

    Переобучить модель заново с новым dataset.yaml.

2. Почему модель работает медленно на Raspberry Pi?

YOLOv8 на CPU может работать со скоростью 1–5 кадров в секунду на Raspberry Pi 4. Для ускорения:

    Используйте imgsz=320 (или даже 256).

    Экспортируйте модель в формат ONNX или TensorRT и используйте соответствующий рантайм.

    Установите torch с оптимизациями под ARM.

    Рассмотрите использование более лёгких моделей (YOLOv8n, YOLOv5n).

3. Как записать видео без падения качества?

Используйте кодек MJPG (как в примере) — он надёжен на Raspberry Pi. Если видео не создаётся, проверьте:

    Права записи в текущую папку.

    Наличие свободного места.

    Правильность разрешения (оно должно совпадать с разрешением камеры).

4. Как опубликовать координаты объекта в другой системе координат?

В функции pixel_to_map можно изменить параметр target_frame на нужный (например, "map"). Убедитесь, что трансформация существует.
Заключение

Вы прошли полный цикл разработки системы детекции объектов для дрона Clover: от сбора данных до запуска автономного полёта с распознаванием. Теперь вы можете адаптировать этот подход под любые объекты и задачи.

Сохраните этот репозиторий на GitHub, чтобы другие могли повторить ваш путь. Удачных полётов! 😊

Автор: [Ваше имя / ник]
Дата: 2026

