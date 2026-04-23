#🚁 YOLO Object Detection for Clover Drone

В этом руководстве описан процесс обучения нейросети YOLOv8 для распознавания объектов с камеры квадрокоптера Clover и интеграции модели в полётную миссию. Материал ориентирован на образовательные цели: он содержит все необходимые компоненты для самостоятельной сборки рабочей системы.

📚 Содержание

⚙️ Необходимое оборудование и ПО

📹 Сбор данных

🏷️ Разметка датасета

🧠 Обучение YOLOv8

🔍 Тестирование модели

✈️ Интеграция с Clover

🔗 Полезные ссылки

⚙️ Необходимое оборудование и ПО

Дрон COEX Clover (физический или симулятор Gazebo).

ROS + пакет clover (см. официальную документацию).

Python 3.8+ с библиотеками:

ultralytics (YOLOv8)

opencv-python

cv_bridge, tf2_geometry_msgs (доступны в ROS-окружении).

Инструмент разметки: LabelImg или Roboflow.

📹 Сбор данных

Для обучения необходимо записать видео с бортовой камеры дрона. Пример кода для захвата видео можно найти в статье на Habr: «Распознавание объектов с помощью YOLO на дроне Clover».

Базовый фрагмент для инициализации записи:

Python


import cv2


def start_video_writer(output_path='flight_video.avi', fps=15.0, frame_size=(320, 240)):

    fourcc = cv2.VideoWriter_fourcc(*'MJPG')

    return cv2.VideoWriter(output_path, fourcc, fps, frame_size)

⚠️ Важно: Для симулятора разрешение камеры обычно 320×240. В реальном дроне может быть 640×480.

Извлечение кадров

После получения видеофайла извлеките каждый 30-й кадр, чтобы избежать дублирования данных:

Python


import cv2

import os


cap = cv2.VideoCapture('flight_video.avi')

os.makedirs('dataset_frames', exist_ok=True)

frame_num, saved = 0, 0


while True:

    ret, frame = cap.read()

    if not ret:

        break

    if frame_num % 30 == 0:

        cv2.imwrite(f'dataset_frames/frame_{saved:05d}.jpg', frame)

        saved += 1

    frame_num += 1


cap.release()

print(f'Сохранено {saved} кадров')

🏷️ Разметка датасета

1. Структура папок

Создайте следующую структуру директорий:

Plaintext


dataset/

├── data.yaml

├── train/

│   ├── images/

│   └── labels/

└── val/

    ├── images/

    └── labels/

Разместите изображения: ~80% в train/images, ~20% в val/images.

2. Использование LabelImg

Запустите инструмент: labelImg.

Откройте папку train/images.

Укажите директорию сохранения (Change Save Dir) в train/labels.

Выберите формат YOLO в левой панели.

Обведите объекты и задайте имена классов (например: grebnik, brakonier, tyrist).

Повторите для папки val.

3. Файл data.yaml

YAML


train: /absolute/path/to/dataset/train/images

val: /absolute/path/to/dataset/val/images


nc: 3

names: ['grebnik', 'brakonier', 'tyrist']

📌 Используйте абсолютные пути! Например: /home/clover/dataset/train/images.

🧠 Обучение YOLOv8

Убедитесь, что библиотека установлена:

Bash


pip install ultralytics

Запустите обучение модели YOLOv8n:

Bash


yolo detect train model=yolov8n.pt \

               data=/path/to/dataset/data.yaml \

               epochs=100 \

               imgsz=320 \

               batch=8 \

               name=clover_detector

После завершения лучшая модель сохранится в:

runs/detect/clover_detector/weights/best.pt.

🔍 Тестирование модели

Проверка на отдельном изображении:

Bash


yolo predict model=/path/to/best.pt source=test_image.jpg imgsz=320

Если всё работает, скопируйте модель на дрон (или в виртуальную среду Clover):

Bash


cp runs/detect/clover_detector/weights/best.pt /home/clover/

✈️ Интеграция с Clover

Для работы модели в составе ROS-ноды используйте следующие фрагменты кода.

1. Инициализация

Python


import rospy

from sensor_msgs.msg import Image

from cv_bridge import CvBridge

from ultralytics import YOLO


rospy.init_node('yolo_detector')

bridge = CvBridge()

model = YOLO('/home/clover/best.pt')

CONFIDENCE = 0.5

2. Callback обработки кадра

Используйте @long_callback, чтобы не блокировать поток обработки изображений.

Python


from clover import long_callback


@long_callback

def image_callback(msg):

    img = bridge.imgmsg_to_cv2(msg, 'bgr8')

    results = model(img, verbose=False)

    

    for result in results:

        boxes = result.boxes

        if boxes is not None:

            for box in boxes:

                conf = float(box.conf[0])

                if conf < CONFIDENCE:

                    continue

                

                cls_id = int(box.cls[0])

                class_name = model.names[cls_id]

                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())

                # Здесь логика публикации координат

3. Преобразование координат

Для перевода пикселей в метры на карте:

Python


import image_geometry

import tf2_ros

from sensor_msgs.msg import CameraInfo


camera_model = image_geometry.PinholeCameraModel()

camera_model.fromCameraInfo(rospy.wait_for_message('main_camera/camera_info', CameraInfo))

tf_buffer = tf2_ros.Buffer()

tf_listener = tf2_ros.TransformListener(tf_buffer)


def pixel_to_map(u, v):

    ray = camera_model.projectPixelTo3dRay((u, v))

    # Далее: вычисление пересечения луча с плоскостью земли через TF

    return (map_x, map_y)

🔗 Полезные ссылки

Clover Documentation — официальная база знаний.

Ultralytics YOLOv8 — документация по модели.

Статья на Habr — подробный туториал.

LabelImg — репозиторий инструмента разметки.
